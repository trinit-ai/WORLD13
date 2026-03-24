"""
TMOS13 Abuse Shield — Dashboard API Endpoints

GET    /account/security/profile              — effective profile for authenticated account
PUT    /account/security/profile              — update account-level protection overrides
GET    /account/security/profile/{pack_id}    — pack-specific overrides for account
PUT    /account/security/profile/{pack_id}    — update pack-specific overrides
GET    /account/security/events               — paginated abuse event log
GET    /account/security/stats                — summary stats
"""
import logging
from typing import Optional

from fastapi import FastAPI, Depends
from pydantic import BaseModel

from errors import APIError, ErrorCode

logger = logging.getLogger("tmos13.abuse_shield.api")


# ─── Pydantic Models ─────────────────────────────────────

class ProfileResponse(BaseModel):
    profile: dict
    sources: dict


class ProfileUpdateRequest(BaseModel):
    require_turnstile: Optional[bool] = None
    allow_automated_clients: Optional[bool] = None
    require_email_after_n_turns: Optional[int] = None
    max_messages_per_minute: Optional[int] = None
    max_messages_per_session: Optional[int] = None
    max_sessions_per_ip_per_hour: Optional[int] = None
    max_daily_tokens_per_ip: Optional[int] = None
    enable_timing_analysis: Optional[bool] = None
    enable_coherence_scoring: Optional[bool] = None
    min_inter_message_ms: Optional[int] = None
    bot_response_mode: Optional[str] = None
    session_token_budget: Optional[int] = None
    daily_account_spend_cap_cents: Optional[int] = None


class EventListResponse(BaseModel):
    events: list[dict]
    total: int


class StatsResponse(BaseModel):
    stats: dict


# ─── Registration ─────────────────────────────────────────

def register_abuse_endpoints(app: FastAPI) -> None:
    """Register /account/security/* endpoints on the FastAPI app."""
    from auth import require_auth, UserProfile
    import abuse_shield

    # ─── GET /account/security/profile ─────────────────────

    @app.get(
        "/account/security/profile",
        response_model=ProfileResponse,
        tags=["security"],
    )
    async def get_security_profile(user: UserProfile = Depends(require_auth)):
        """Get the fully-resolved protection profile for the authenticated account."""
        # Use the user's default pack or tmos13_site
        result = abuse_shield.get_profile_with_sources(
            pack_id="guest",
            account_id=user.user_id,
        )
        return ProfileResponse(
            profile=result["profile"],
            sources=result["sources"],
        )

    # ─── PUT /account/security/profile ─────────────────────

    @app.put(
        "/account/security/profile",
        response_model=ProfileResponse,
        tags=["security"],
    )
    async def update_security_profile(
        req: ProfileUpdateRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """Update account-level protection overrides."""
        overrides = {k: v for k, v in req.model_dump().items() if v is not None}

        if "bot_response_mode" in overrides:
            valid_modes = {"allow", "throttle", "challenge", "block", "tarpit"}
            if overrides["bot_response_mode"] not in valid_modes:
                raise APIError(
                    ErrorCode.VALIDATION_ERROR,
                    f"Invalid bot_response_mode. Must be one of: {', '.join(valid_modes)}",
                    400,
                )

        abuse_shield.set_account_overrides(user.user_id, overrides)

        result = abuse_shield.get_profile_with_sources(
            pack_id="guest",
            account_id=user.user_id,
        )
        return ProfileResponse(
            profile=result["profile"],
            sources=result["sources"],
        )

    # ─── GET /account/security/profile/{pack_id} ──────────

    @app.get(
        "/account/security/profile/{pack_id}",
        response_model=ProfileResponse,
        tags=["security"],
    )
    async def get_pack_security_profile(
        pack_id: str,
        user: UserProfile = Depends(require_auth),
    ):
        """Get pack-specific protection profile for the authenticated account."""
        result = abuse_shield.get_profile_with_sources(
            pack_id=pack_id,
            account_id=user.user_id,
        )
        return ProfileResponse(
            profile=result["profile"],
            sources=result["sources"],
        )

    # ─── PUT /account/security/profile/{pack_id} ──────────

    @app.put(
        "/account/security/profile/{pack_id}",
        response_model=ProfileResponse,
        tags=["security"],
    )
    async def update_pack_security_profile(
        pack_id: str,
        req: ProfileUpdateRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """Update pack-specific protection overrides for the authenticated account."""
        overrides = {k: v for k, v in req.model_dump().items() if v is not None}

        if "bot_response_mode" in overrides:
            valid_modes = {"allow", "throttle", "challenge", "block", "tarpit"}
            if overrides["bot_response_mode"] not in valid_modes:
                raise APIError(
                    ErrorCode.VALIDATION_ERROR,
                    f"Invalid bot_response_mode. Must be one of: {', '.join(valid_modes)}",
                    400,
                )

        abuse_shield.set_account_pack_overrides(user.user_id, pack_id, overrides)

        result = abuse_shield.get_profile_with_sources(
            pack_id=pack_id,
            account_id=user.user_id,
        )
        return ProfileResponse(
            profile=result["profile"],
            sources=result["sources"],
        )

    # ─── GET /account/security/events ──────────────────────

    @app.get(
        "/account/security/events",
        response_model=EventListResponse,
        tags=["security"],
    )
    async def get_security_events(
        limit: int = 50,
        event_type: Optional[str] = None,
        pack_id: Optional[str] = None,
        user: UserProfile = Depends(require_auth),
    ):
        """Get paginated abuse event log."""
        events = abuse_shield.get_events(
            limit=limit,
            event_type=event_type,
            pack_id=pack_id,
        )
        return EventListResponse(
            events=events,
            total=len(events),
        )

    # ─── GET /account/security/stats ──────────────────────

    @app.get(
        "/account/security/stats",
        response_model=StatsResponse,
        tags=["security"],
    )
    async def get_security_stats(user: UserProfile = Depends(require_auth)):
        """Get abuse shield summary statistics."""
        stats = abuse_shield.get_stats()
        return StatsResponse(stats=stats)

    logger.info("Abuse Shield API endpoints registered: /account/security/*")
