-- Adds cross-source/cross-poll deduplication support.
--
-- The old UNIQUE (source, source_event_id, received_at) constraint never
-- prevented anything useful: received_at has microsecond precision, so a
-- source re-sending the exact same report on every poll just kept getting
-- a fresh timestamp and a fresh row. Real duplicate detection now happens
-- in application code (daemon/db.py), which needs each report's parsed
-- fields available without re-parsing every source's raw payload shape,
-- so those fields are stored alongside the payload here.

ALTER TABLE event_reports DROP CONSTRAINT event_reports_source_source_event_id_received_at_key;

ALTER TABLE event_reports
    ADD COLUMN origin_time    TIMESTAMPTZ,
    ADD COLUMN latitude       DOUBLE PRECISION,
    ADD COLUMN longitude      DOUBLE PRECISION,
    ADD COLUMN depth_km       DOUBLE PRECISION,
    ADD COLUMN magnitude      DOUBLE PRECISION,
    ADD COLUMN magnitude_type TEXT,
    ADD COLUMN region         TEXT;

-- Fast "latest report for this source+id" lookup (same-source dedup).
CREATE INDEX idx_event_reports_source_lookup
    ON event_reports (source, source_event_id, received_at DESC);

-- Fast "latest report per source for this event" lookup (canonical recompute).
CREATE INDEX idx_event_reports_event_source
    ON event_reports (event_id, source, received_at DESC);
