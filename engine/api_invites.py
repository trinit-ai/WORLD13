"""
TMOS13 Invite API — Session Access Code Management

Endpoints:
  POST   /api/invites          — Create a new invite
  GET    /api/invites          — List invites (optionally by pack)
  DELETE /api/invites/{id}     — Revoke an invite
  POST   /api/invites/redeem   — Redeem an invite code
"""

import logging
from typing import Optional
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from invites import get_invite_store

logger = logging.getLogger("tmos13.api.invites")


# ─── Request / Response Models ───────────────────────────

class InviteCreateRequest(BaseModel):
    pack_id: str
    email: str | None = None
    max_uses: int = 1
    expires_in_hours: float | None = None


class InviteResponse(BaseModel):
    id: str
    code: str
    pack_id: str
    created_by: str
    email: str | None = None
    max_uses: int
    uses: int
    status: str
    expires_at: str | None = None
    created_at: str


class InviteListResponse(BaseModel):
    invites: list[InviteResponse]


class InviteRedeemRequest(BaseModel):
    code: str
    session_id: str | None = None


class InviteRedeemResponse(BaseModel):
    valid: bool
    pack_id: str | None = None
    message: str | None = None


# ─── Helpers ─────────────────────────────────────────────

def _ts_to_iso(ts: Optional[float]) -> Optional[str]:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _invite_to_response(inv) -> InviteResponse:
    return InviteResponse(
        id=inv.id,
        code=inv.code,
        pack_id=inv.pack_id,
        created_by=inv.created_by,
        email=inv.email,
        max_uses=inv.max_uses,
        uses=inv.uses,
        status=inv.status,
        expires_at=_ts_to_iso(inv.expires_at),
        created_at=_ts_to_iso(inv.created_at) or "",
    )


# ─── Registration ────────────────────────────────────────

def register_invite_endpoints(app: FastAPI) -> None:
    """Register invite management API endpoints."""

    @app.post(
        "/api/invites",
        response_model=InviteResponse,
        tags=["invites"],
    )
    async def create_invite(req: InviteCreateRequest):
        """Create a new invite code for a gated session."""
        store = get_invite_store()

        invite = store.create(
            pack_id=req.pack_id,
            created_by="system",  # TODO: Extract from auth
            email=req.email,
            max_uses=req.max_uses,
            expires_in_hours=req.expires_in_hours,
        )

        return _invite_to_response(invite)

    @app.get(
        "/api/invites",
        response_model=InviteListResponse,
        tags=["invites"],
    )
    async def list_invites(pack_id: str | None = None):
        """List invites, optionally filtered by pack."""
        store = get_invite_store()

        if pack_id:
            invites = store.list_by_pack(pack_id)
        else:
            invites = list(store._invites.values())

        return InviteListResponse(
            invites=[_invite_to_response(inv) for inv in invites],
        )

    @app.delete(
        "/api/invites/{invite_id}",
        tags=["invites"],
    )
    async def revoke_invite(invite_id: str):
        """Revoke an invite by ID."""
        store = get_invite_store()
        revoked = store.revoke(invite_id)

        if not revoked:
            raise HTTPException(status_code=404, detail="Invite not found")

        return {"revoked": True}

    @app.post(
        "/api/invites/redeem",
        response_model=InviteRedeemResponse,
        tags=["invites"],
    )
    async def redeem_invite(req: InviteRedeemRequest):
        """
        Redeem an invite code. Returns whether the code is valid
        and the pack it grants access to.
        """
        store = get_invite_store()

        result = store.redeem(
            code=req.code,
            session_id=req.session_id,
        )

        return InviteRedeemResponse(
            valid=result.valid,
            pack_id=result.pack_id,
            message=result.message,
        )
