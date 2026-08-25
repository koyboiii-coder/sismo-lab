from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import traceback

from config import load_config
from connectors import csn, emsc, usgs
from db import Writer

logger = logging.getLogger(__name__)

CONNECTORS = {
    "EMSC": emsc.run,
    "USGS": usgs.run,
    "CSN": csn.run,
}


RESTART_BACKOFF_INITIAL_S = 1
RESTART_BACKOFF_MAX_S = 60
# A connector that ran at least this long before dying gets its restart
# backoff reset, so a source that fails once every few hours doesn't slide
# into an ever-growing wait.
RESTART_BACKOFF_RESET_AFTER_S = 60


async def _run_connector(name, coro_fn, config, writer, stop_event) -> None:
    """Supervises one connector for the daemon's whole lifetime.

    Per the graceful-degradation rule, a connector must never be able to
    disappear silently -- whether it raises, or its polling loop exits
    cleanly (which it never should, but a bug that makes it happen must
    still be visible and self-healing rather than a task that quietly stops
    producing log lines). Any exit while the daemon isn't shutting down is
    logged as an ERROR and followed by a restart with exponential backoff.
    """
    loop = asyncio.get_running_loop()
    backoff = RESTART_BACKOFF_INITIAL_S

    while not stop_event.is_set():
        started_at = loop.time()
        try:
            await coro_fn(config, writer, stop_event)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("[%s] connector crashed", name)
        else:
            if stop_event.is_set():
                return
            logger.error(
                "[%s] connector task returned without being asked to stop "
                "-- this should never happen, treating it as a failure",
                name,
            )

        if stop_event.is_set():
            return

        if loop.time() - started_at >= RESTART_BACKOFF_RESET_AFTER_S:
            backoff = RESTART_BACKOFF_INITIAL_S

        logger.error("[%s] restarting connector in %ss", name, backoff)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=backoff)
            return  # stop_event was set while waiting to restart
        except asyncio.TimeoutError:
            pass
        backoff = min(backoff * 2, RESTART_BACKOFF_MAX_S)


def _dump_task_stacks() -> None:
    """SIGUSR1 handler: log every task's current stack.

    For a stuck connector this points at the exact `await` it never came
    back from -- send the signal (`kill -USR1 <pid>`) once a source has
    gone quiet and check the logs for its task name.
    """
    tasks = asyncio.all_tasks()
    logger.warning("SIGUSR1 received: dumping stacks for %d task(s)", len(tasks))
    for task in tasks:
        stack = task.get_stack()
        if not stack:
            logger.warning(
                "[task %s] no frame captured (not currently suspended on an await)",
                task.get_name(),
            )
            continue
        frame_lines = [
            f'  File "{frame.f_code.co_filename}", line {frame.f_lineno}, '
            f"in {frame.f_code.co_name}"
            for frame in stack
        ]
        logger.warning(
            "[task %s] stack (most recent await last):\n%s",
            task.get_name(),
            "\n".join(frame_lines),
        )


async def main_async(dry_run: bool) -> None:
    config = load_config()
    logging.basicConfig(
        level=config.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    writer = Writer(
        config.database_url,
        dry_run=dry_run,
        command_timeout_s=config.db_command_timeout_s,
    )
    await writer.connect()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)
    loop.add_signal_handler(signal.SIGUSR1, _dump_task_stacks)

    tasks = [
        asyncio.create_task(_run_connector(name, fn, config, writer, stop_event), name=name)
        for name, fn in CONNECTORS.items()
    ]

    await stop_event.wait()
    logger.info("shutting down, stopping connectors...")
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await writer.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Sismos ingestion daemon")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print parsed reports to stdout instead of writing to Postgres",
    )
    args = parser.parse_args()
    asyncio.run(main_async(args.dry_run))


if __name__ == "__main__":
    main()
