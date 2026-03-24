"""
TMOS13 DevMode — Development & Debugging Toolkit

Provides debug middleware, protocol hot-reload, state inspection,
and development-only API endpoints. Only active when DEBUG=True.

Usage in app.py:
    from devmode import register_debug_endpoints
    if DEBUG:
        register_debug_endpoints(app, sessions, assembler, db)
"""
import time
from dataclasses import asdict
from typing import Any, Optional, Union

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from config import (
    DEBUG,
    ENV,
    logger,
    ANTHROPIC_API_KEY,
    SUPABASE_URL,
    SUPABASE_ANON_KEY,
    SUPABASE_SERVICE_ROLE_KEY,
    MODEL,
    MAX_TOKENS,
    PORT,
    HOST,
    ALLOWED_ORIGINS,
    RATE_LIMIT_RPM,
    MAX_MESSAGE_LENGTH,
    MAX_SESSIONS,
    PROTOCOL_DIR,
    BASE_DIR,
    get_pack,
    get_cartridges,
    get_default_settings,
)
from state import SessionState
from assembler import Assembler


# ─── DevMode Middleware ──────────────────────────────────────


class DevModeMiddleware(BaseHTTPMiddleware):
    """
    Development middleware that wraps every request with debug info.

    Adds response headers:
        X-Debug-Response-Time: request/response timing in ms
        X-Debug-Active-Sessions: current active session count
        X-Debug-Prompt-Tokens: estimated prompt tokens (if available)
        X-Debug-Cache-Entries: number of cached protocol sections

    Also logs timing and context for every request at DEBUG level.
    """

    def __init__(
        self,
        app: ASGIApp,
        sessions: dict[str, SessionState],
        assembler: Assembler,
    ) -> None:
        super().__init__(app)
        self.sessions = sessions
        self.assembler = assembler

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()

        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        active_sessions = len(self.sessions)
        cache_entries = len(self.assembler._cache)

        # Estimate current prompt tokens from cache contents
        total_cached_chars = sum(len(v) for v in self.assembler._cache.values())
        estimated_tokens = total_cached_chars // 4

        response.headers["X-Debug-Response-Time"] = f"{elapsed_ms:.2f}ms"
        response.headers["X-Debug-Active-Sessions"] = str(active_sessions)
        response.headers["X-Debug-Prompt-Tokens"] = str(estimated_tokens)
        response.headers["X-Debug-Cache-Entries"] = str(cache_entries)

        logger.debug(
            f"[DevMode] {request.method} {request.url.path} "
            f"-> {response.status_code} in {elapsed_ms:.1f}ms "
            f"(sessions={active_sessions}, cache={cache_entries})"
        )

        return response


# ─── Protocol Hot-Reload ─────────────────────────────────────


def reload_protocols(assembler: Assembler) -> dict[str, Any]:
    """
    Clear the assembler's protocol cache so all .md files are
    re-read from disk on the next request.

    Returns a summary of what was cleared.
    """
    cleared_keys = list(assembler._cache.keys())
    count = len(cleared_keys)
    assembler._cache.clear()

    logger.info(f"[DevMode] Protocol cache cleared: {count} entries evicted")

    return {
        "cleared": count,
        "files": cleared_keys,
        "protocol_dir": str(assembler.protocol_dir),
        "message": f"Cleared {count} cached protocol sections. "
                   f"They will be re-read from {assembler.protocol_dir} on next request.",
    }


# ─── State Inspector ─────────────────────────────────────────


def inspect_session(state: SessionState) -> dict[str, Any]:
    """
    Return a full serializable dump of a session's state.

    Uses dataclasses.asdict for sub-state dataclasses and handles
    the history list and computed properties explicitly.
    """
    base = asdict(state)

    # Add session duration
    base["session_duration_seconds"] = time.time() - state.session_start

    # Add summary info
    base["summary"] = {
        "cartridges_visited": len(set(state.games_played)),
        "history_length": len(state.history),
        "is_in_cartridge": state.current_game is not None,
        "active_cartridge": state.current_game,
    }

    return base


# ─── Debug Endpoints ─────────────────────────────────────────


class StateOverride(BaseModel):
    """JSON body for injecting state overrides during testing."""
    mood: Optional[str] = None
    depth: Optional[int] = None
    current_game: Optional[str] = None
    turn_count: Optional[int] = None
    games_played: Optional[list[str]] = None
    settings: Optional[dict[str, Any]] = None


def _redact_key(value: str, visible_chars: int = 4) -> str:
    """Redact an API key, showing only the last N characters."""
    if not value:
        return "(not set)"
    if len(value) <= visible_chars:
        return "****"
    return "*" * (len(value) - visible_chars) + value[-visible_chars:]


def register_debug_endpoints(
    app: FastAPI,
    sessions: dict[str, SessionState],
    assembler: Assembler,
    db: Any,
) -> None:
    """
    Register development-only debug endpoints on the FastAPI app.

    These routes are only intended for use when DEBUG=True.
    They expose internal state and should NEVER be active in production.
    """

    if not DEBUG:
        logger.warning(
            "[DevMode] register_debug_endpoints called but DEBUG is False — skipping"
        )
        return

    logger.info("[DevMode] Registering debug endpoints (/dev/*)")

    # ─── GET /dev/sessions ───────────────────────────────

    @app.get("/dev/sessions")
    async def dev_list_sessions() -> list[dict[str, Any]]:
        """List all active session IDs with summary info."""
        result = []
        now = time.time()
        for sid, state in sessions.items():
            result.append({
                "session_id": sid,
                "user_id": state.user_id,
                "current_game": state.current_game,
                "depth": state.depth,
                "turn_count": state.turn_count,
                "mood": state.mood,
                "games_played": state.games_played,
                "history_length": len(state.history),
                "session_age_seconds": round(now - state.session_start, 1),
            })
        return result

    # ─── GET /dev/sessions/{session_id} ──────────────────

    @app.get("/dev/sessions/{session_id}")
    async def dev_get_session(session_id: str) -> JSONResponse:
        """Full state dump for a specific session."""
        state = sessions.get(session_id)
        if state is None:
            return JSONResponse(
                status_code=404,
                content={"error": f"Session '{session_id}' not found"},
            )
        return JSONResponse(content=inspect_session(state))

    # ─── POST /dev/reload-protocols ──────────────────────

    @app.post("/dev/reload-protocols")
    async def dev_reload_protocols() -> dict[str, Any]:
        """Trigger protocol hot-reload (clear cache, re-read from disk)."""
        return reload_protocols(assembler)

    # ─── GET /dev/config ─────────────────────────────────

    @app.get("/dev/config")
    async def dev_get_config() -> dict[str, Any]:
        """Return current configuration with API keys redacted."""
        return {
            "env": ENV,
            "debug": DEBUG,
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            "host": HOST,
            "port": PORT,
            "allowed_origins": ALLOWED_ORIGINS,
            "rate_limit_rpm": RATE_LIMIT_RPM,
            "max_message_length": MAX_MESSAGE_LENGTH,
            "max_sessions": MAX_SESSIONS,
            "protocol_dir": str(get_pack().protocol_dir if get_pack() else PROTOCOL_DIR),
            "base_dir": str(BASE_DIR),
            "cartridges": get_cartridges(),
            "default_settings": get_default_settings(),
            # Redacted secrets
            "anthropic_api_key": _redact_key(ANTHROPIC_API_KEY),
            "supabase_url": SUPABASE_URL or "(not set)",
            "supabase_anon_key": _redact_key(SUPABASE_ANON_KEY),
            "supabase_service_role_key": _redact_key(SUPABASE_SERVICE_ROLE_KEY),
        }

    # ─── GET /dev/prompt-preview/{session_id} ────────────

    @app.get("/dev/prompt-preview/{session_id}")
    async def dev_prompt_preview(session_id: str) -> JSONResponse:
        """Show the full system prompt that would be assembled for a session."""
        state = sessions.get(session_id)
        if state is None:
            return JSONResponse(
                status_code=404,
                content={"error": f"Session '{session_id}' not found"},
            )

        prompt = assembler.build_system_prompt(state)
        token_estimate = assembler.estimate_tokens(prompt)

        return JSONResponse(content={
            "session_id": session_id,
            "current_game": state.current_game,
            "prompt": prompt,
            "char_count": len(prompt),
            "token_estimate": token_estimate,
            "cache_entries": len(assembler._cache),
        })

    # ─── POST /dev/inject-state/{session_id} ─────────────

    @app.post("/dev/inject-state/{session_id}")
    async def dev_inject_state(
        session_id: str, override: StateOverride
    ) -> JSONResponse:
        """
        Override specific state fields for a session (testing purposes).

        Accepts a JSON body with optional fields. Only provided fields
        are applied; everything else is left unchanged.
        """
        state = sessions.get(session_id)
        if state is None:
            return JSONResponse(
                status_code=404,
                content={"error": f"Session '{session_id}' not found"},
            )

        applied: list[str] = []

        # Top-level fields
        if override.mood is not None:
            state.mood = override.mood
            applied.append("mood")
        if override.depth is not None:
            state.depth = override.depth
            applied.append("depth")
        if override.current_game is not None:
            state.current_game = override.current_game
            applied.append("current_game")
        if override.turn_count is not None:
            state.turn_count = override.turn_count
            applied.append("turn_count")
        if override.games_played is not None:
            state.games_played = override.games_played
            applied.append("games_played")
        if override.settings is not None:
            state.settings.update(override.settings)
            applied.append("settings")

        logger.info(
            f"[DevMode] State injection for session {session_id}: "
            f"{', '.join(applied) if applied else 'no changes'}"
        )

        return JSONResponse(content={
            "session_id": session_id,
            "fields_applied": applied,
            "current_state": inspect_session(state),
        })
