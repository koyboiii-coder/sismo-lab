from __future__ import annotations

import os

from fastapi import APIRouter

router = APIRouter()


@router.get("/version")
async def version():
    return {
        "git_sha": os.environ.get("GIT_SHA", "unknown"),
        "built_at": os.environ.get("BUILT_AT", "unknown"),
    }
