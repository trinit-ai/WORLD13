"""
TMOS13 TimeKeeper — API Endpoints (Fibonacci Plume Node 11)

GET /api/packs/{pack_id}/schedule         — Schedule entries for a pack
GET /api/session/{session_id}/schedule/next — Next upcoming schedule events for a session
"""
import logging
from datetime import datetime, timezone

from fastapi import FastAPI

from errors import APIError, ErrorCode

logger = logging.getLogger("tmos13.timekeeper.api")


def register_timekeeper_endpoints(app: FastAPI, sessions) -> None:
    """Register TimeKeeper read-only endpoints on the FastAPI application."""

    @app.get(
        "/api/packs/{pack_id}/schedule",
        tags=["timekeeper"],
        summary="Get schedule entries for a pack",
    )
    async def get_pack_schedule(pack_id: str):
        from schedule_cache import get_schedule_cache
        cache = get_schedule_cache()
        if cache is None:
            return {"pack_id": pack_id, "entries": [], "enabled": False}

        entries = cache.get_entries_for_pack(pack_id)
        return {
            "pack_id": pack_id,
            "entries": [
                {
                    "entry_id": e.entry_id,
                    "action": e.action,
                    "pattern": e.pattern.raw,
                    "timezone": e.timezone,
                    "reason": e.reason,
                    "enabled": e.enabled,
                }
                for e in entries
            ],
            "enabled": True,
        }

    @app.get(
        "/api/session/{session_id}/schedule/next",
        tags=["timekeeper"],
        summary="Next upcoming schedule events for active session",
    )
    async def get_session_schedule_next(session_id: str):
        state = sessions.get(session_id)
        if not state:
            raise APIError(ErrorCode.SESSION_NOT_FOUND, f"Session {session_id} not found", 404)

        from schedule_cache import get_schedule_cache
        cache = get_schedule_cache()
        if cache is None:
            return {"session_id": session_id, "pack_id": state.pack_id, "upcoming": []}

        now = datetime.now(timezone.utc)
        upcoming = cache.get_upcoming(state.pack_id, now, limit=3)

        return {
            "session_id": session_id,
            "pack_id": state.pack_id,
            "upcoming": upcoming,
        }
