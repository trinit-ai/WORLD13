"""
TMOS13 Session Policy API — Access Control Endpoints

Endpoints:
  GET  /api/policy/check   — Check policy for a session
  GET  /api/policy/config   — Get policy config for a pack
"""

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from session_policy import get_policy_enforcer, get_policy_config_from_manifest

logger = logging.getLogger("tmos13.api.policy")


# ─── Response Models ─────────────────────────────────────

class PolicyCheckResponse(BaseModel):
    action: str
    reason: str | None = None
    remaining_turns: int | None = None
    remaining_tokens: int | None = None
    auth_url: str | None = None


class MeteringConfigResponse(BaseModel):
    free_turns: int
    free_tokens: int
    overage_action: str


class PolicyConfigResponse(BaseModel):
    policy_type: str
    deferred_auth: dict | None = None
    max_anonymous_turns: int = 0
    require_invite: bool = False
    invite_codes_enabled: bool = False
    metering: MeteringConfigResponse | None = None


# ─── Registration ────────────────────────────────────────

def register_policy_endpoints(app: FastAPI) -> None:
    """Register Session Policy API endpoints."""

    @app.get(
        "/api/policy/check",
        response_model=PolicyCheckResponse,
        tags=["session_policy"],
    )
    async def check_policy(session_id: str):
        """
        Check the session policy for a given session. Returns the
        enforcement action (allow, prompt_auth, require_invite, etc).
        """
        from config import get_pack

        enforcer = get_policy_enforcer()

        pack = get_pack()
        manifest = pack.manifest if pack else {}
        config = get_policy_config_from_manifest(manifest)

        result = enforcer.check(
            session_id=session_id,
            config=config,
            is_authenticated=False,
        )

        return PolicyCheckResponse(
            action=result.action,
            reason=result.reason,
            remaining_turns=result.remaining_turns,
            remaining_tokens=result.remaining_tokens,
            auth_url=result.auth_url,
        )

    @app.get(
        "/api/policy/config",
        response_model=PolicyConfigResponse,
        tags=["session_policy"],
    )
    async def get_policy_config(pack_id: str | None = None):
        """Get the session policy config for a pack."""
        from config import get_pack

        pack = get_pack()
        manifest = pack.manifest if pack else {}
        config = get_policy_config_from_manifest(manifest)

        deferred = None
        if config.deferred_auth_enabled:
            deferred = {
                "enabled": True,
                "triggers": [
                    {"type": t.trigger_type, "threshold": t.threshold}
                    for t in config.deferred_auth_triggers
                ],
                "grace_message": config.deferred_auth_grace_message,
            }

        metering = None
        if config.metering:
            metering = MeteringConfigResponse(
                free_turns=config.metering.free_turns,
                free_tokens=config.metering.free_tokens,
                overage_action=config.metering.overage_action,
            )

        return PolicyConfigResponse(
            policy_type=config.policy_type,
            deferred_auth=deferred,
            max_anonymous_turns=config.max_anonymous_turns,
            require_invite=config.require_invite,
            invite_codes_enabled=config.invite_codes_enabled,
            metering=metering,
        )
