"""
TMOS13 Identity Gate — API Endpoints

GET  /api/identity/gate     — Check if user has completed identity gate
PUT  /api/identity/profile  — Save identity fields

The identity gate requires authenticated users to provide display_name, title,
and organization before accessing non-guest packs. This ensures meaningful
user profiles for the User Identity system (Fibonacci Plume Node 6).

Admin and owner roles bypass the gate entirely.
"""
import logging
from typing import Optional

from fastapi import FastAPI, Depends
from pydantic import BaseModel

from auth import require_auth, UserProfile, role_at_least
from errors import APIError, ErrorCode

logger = logging.getLogger("tmos13.identity")


# ─── Pydantic Models ─────────────────────────────────────

class GateResponse(BaseModel):
    complete: bool
    profile: Optional[dict] = None


class ProfileUpdateRequest(BaseModel):
    full_name: str
    title: str
    company: str
    bio: str
    email: Optional[str] = None
    industry: Optional[str] = None


class ProfileUpdateResponse(BaseModel):
    ok: bool
    profile: dict


# ─── Registration ─────────────────────────────────────────

def register_identity_endpoints(app: FastAPI, db) -> None:
    """Register /api/identity/* endpoints on the FastAPI app."""

    @app.get(
        "/api/identity/gate",
        response_model=GateResponse,
        tags=["identity"],
    )
    async def get_identity_gate(user: UserProfile = Depends(require_auth)):
        """Check if user has completed identity gate (full_name + title + organization)."""
        profile = _fetch_profile(db, user.user_id)
        complete = _is_gate_complete(profile)
        return GateResponse(complete=complete, profile=profile)

    @app.put(
        "/api/identity/profile",
        response_model=ProfileUpdateResponse,
        tags=["identity"],
    )
    async def put_identity_profile(
        req: ProfileUpdateRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """Save identity fields to profiles table."""
        if not req.full_name or not req.full_name.strip():
            raise APIError(ErrorCode.VALIDATION_ERROR, "full_name is required", 400)
        if not req.title or not req.title.strip():
            raise APIError(ErrorCode.VALIDATION_ERROR, "title is required", 400)
        if not req.company or not req.company.strip():
            raise APIError(ErrorCode.VALIDATION_ERROR, "company is required", 400)
        if not req.bio or not req.bio.strip():
            raise APIError(ErrorCode.VALIDATION_ERROR, "bio is required", 400)

        row = {
            "user_id": user.user_id,
            "display_name": req.full_name.strip(),
            "title": req.title.strip(),
            "organization": req.company.strip(),
            "bio": req.bio.strip(),
        }
        if req.industry:
            row["industry"] = req.industry.strip()

        if db and hasattr(db, "client"):
            try:
                db.client.table("profiles").upsert(
                    row, on_conflict="user_id",
                ).execute()
            except Exception as e:
                logger.error(f"Failed to upsert profile for {user.user_id}: {e}")
                raise APIError(ErrorCode.INTERNAL_ERROR, "Failed to save profile", 500)

        profile = _fetch_profile(db, user.user_id)
        return ProfileUpdateResponse(ok=True, profile=profile or row)

    logger.info("Identity Gate endpoints registered: /api/identity/*")


# ─── Helpers ─────────────────────────────────────────────

def _fetch_profile(db, user_id: str) -> Optional[dict]:
    """Fetch profile row from Supabase."""
    if not db or not hasattr(db, "client"):
        return None
    try:
        result = (
            db.client.table("profiles")
            .select("display_name, title, organization, bio, industry")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        return result.data if result.data else None
    except Exception:
        return None


def _is_gate_complete(profile: Optional[dict]) -> bool:
    """Check if profile has all required identity fields."""
    if not profile:
        return False
    return bool(
        profile.get("display_name")
        and profile.get("title")
        and profile.get("organization")
        and profile.get("bio")
    )


async def check_identity_gate(db, user_id: str, user_role: str = "user") -> bool:
    """Public helper: check if user has completed identity gate.

    Admin and owner roles bypass the gate entirely.
    """
    if role_at_least(user_role, "admin"):
        return True
    profile = _fetch_profile(db, user_id)
    return _is_gate_complete(profile)
