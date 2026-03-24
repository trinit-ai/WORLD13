"""
TMOS13 PlayStop — API Endpoints (Transport Rail)

POST /api/session/{session_id}/play       — Resume (PAUSE→PLAY or STOP→PLAY)
POST /api/session/{session_id}/pause      — Pause (PLAY→PAUSE)
POST /api/session/{session_id}/stop       — Stop (PLAY/PAUSE→STOP)
GET  /api/session/{session_id}/transport  — Unified transport dashboard
"""
import logging
import time
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from errors import APIError, ErrorCode

logger = logging.getLogger("tmos13.playstop.api")


# ─── Pydantic Models ─────────────────────────────────────────

class PlayRequest(BaseModel):
    actor: str = "user"
    reason: str = ""
    restartable: bool = False


class PauseRequest(BaseModel):
    actor: str = "user"
    reason: str = ""


class StopRequest(BaseModel):
    actor: str = "user"
    reason: str = ""
    stop_reason: str = "completed"  # completed | cancelled | rejected | timeout | error | external


class TransportResponse(BaseModel):
    state: str
    session_id: str
    transition: Optional[dict] = None


class TransportDashboard(BaseModel):
    session_id: str
    user_id: str
    transport_state: str
    subsystems: dict


# ─── WebSocket Event Helper ──────────────────────────────────

async def _emit_playstop_event(state, new_state: str, transition) -> None:
    """Emit a playstop event over the session's WebSocket if connected."""
    ws = getattr(state, "_ws", None)
    if not ws:
        return
    try:
        await ws.send_json({
            "type": "playstop",
            "target": "session",
            "target_id": state.session_id,
            "state": new_state,
            "from": transition.from_state.value,
            "actor": transition.actor,
            "reason": transition.reason,
            "timestamp": time.time(),
        })
    except Exception as e:
        logger.debug("Failed to emit playstop WS event: %s", e)


# ─── Registration ─────────────────────────────────────────────

def register_playstop_endpoints(app: FastAPI, sessions, playstop_machine) -> None:
    """Register transport rail endpoints on the FastAPI application."""

    from playstop import (
        PlayStopState, StopReason, build_unified_status,
    )

    def _get_state(session_id: str):
        """Fetch session state or raise 404."""
        state = sessions.get(session_id)
        if not state:
            raise APIError(ErrorCode.SESSION_NOT_FOUND, f"Session {session_id} not found", 404)
        return state

    @app.post(
        "/api/session/{session_id}/play",
        response_model=TransportResponse,
        tags=["transport"],
        summary="Resume session (PAUSE→PLAY or restart STOP→PLAY)",
    )
    async def play_session(session_id: str, req: PlayRequest):
        state = _get_state(session_id)
        try:
            transition = playstop_machine.play(
                state,
                actor=req.actor,
                reason=req.reason,
                restartable=req.restartable,
            )
        except ValueError as e:
            raise APIError(ErrorCode.FORBIDDEN, str(e), 403)

        sessions.persist(state)
        await _emit_playstop_event(state, PlayStopState.PLAY.value, transition)

        return {
            "state": PlayStopState.PLAY.value,
            "session_id": session_id,
            "transition": transition.to_dict(),
        }

    @app.post(
        "/api/session/{session_id}/pause",
        response_model=TransportResponse,
        tags=["transport"],
        summary="Pause session (PLAY→PAUSE)",
    )
    async def pause_session(session_id: str, req: PauseRequest):
        state = _get_state(session_id)
        try:
            transition = playstop_machine.pause(
                state,
                actor=req.actor,
                reason=req.reason,
            )
        except ValueError as e:
            raise APIError(ErrorCode.FORBIDDEN, str(e), 403)

        sessions.persist(state)
        await _emit_playstop_event(state, PlayStopState.PAUSE.value, transition)

        return {
            "state": PlayStopState.PAUSE.value,
            "session_id": session_id,
            "transition": transition.to_dict(),
        }

    @app.post(
        "/api/session/{session_id}/stop",
        response_model=TransportResponse,
        tags=["transport"],
        summary="Stop session (PLAY/PAUSE→STOP)",
    )
    async def stop_session(session_id: str, req: StopRequest):
        state = _get_state(session_id)

        # Parse stop_reason
        try:
            sr = StopReason(req.stop_reason)
        except ValueError:
            sr = StopReason.COMPLETED

        try:
            transition = playstop_machine.stop(
                state,
                actor=req.actor,
                reason=req.reason,
                stop_reason=sr,
            )
        except ValueError as e:
            raise APIError(ErrorCode.FORBIDDEN, str(e), 403)

        sessions.persist(state)
        await _emit_playstop_event(state, PlayStopState.STOP.value, transition)

        return {
            "state": PlayStopState.STOP.value,
            "session_id": session_id,
            "transition": transition.to_dict(),
        }

    @app.get(
        "/api/session/{session_id}/transport",
        response_model=TransportDashboard,
        tags=["transport"],
        summary="Unified transport status dashboard",
    )
    async def transport_dashboard(session_id: str):
        state = _get_state(session_id)

        # Fetch service singletons at request time (same pattern as _finalize_session)
        from pipeline_service import get_pipeline_service
        from delivery_service import get_delivery_service

        pipeline_svc = get_pipeline_service()
        delivery_svc = get_delivery_service()

        # Ambassador service is optional
        ambassador_svc = None
        try:
            from ambassador_service import get_ambassador_service
            ambassador_svc = get_ambassador_service()
        except Exception:
            pass

        dashboard = build_unified_status(
            state,
            pipeline_service=pipeline_svc,
            delivery_service=delivery_svc,
            ambassador_service=ambassador_svc,
        )
        return dashboard
