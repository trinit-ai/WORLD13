"""Profile management API — extended user identity fields.

Endpoints:
  GET   /profile            — full profile for authenticated user
  PUT   /profile            — update profile fields
  POST  /profile/onboard    — mark onboarding complete
  GET   /profile/variables   — profile variables for assembler injection
  GET   /api/me             — workspace profile card (profile + org)
  PATCH /api/me             — update workspace profile fields
  POST  /api/me/avatar      — upload avatar image
  POST  /api/me/org-logo    — upload organization logo
"""
import logging
import time
from typing import Optional

from fastapi import Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from auth import UserProfile, require_auth, get_auth_service

logger = logging.getLogger("tmos13.profile")

# ─── Request / Response Models ─────────────────────────

PROFILE_FIELDS = {
    "preferred_name", "title", "organization", "org_name", "org_logo_url",
    "timezone", "language", "communication_style", "industry", "use_case",
    "display_name", "avatar_url", "bio",
}

VALID_STYLES = {"concise", "balanced", "detailed"}


class ProfileUpdateRequest(BaseModel):
    preferred_name: Optional[str] = None
    title: Optional[str] = None
    organization: Optional[str] = None
    org_logo_url: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    communication_style: Optional[str] = None
    industry: Optional[str] = None
    use_case: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None


class OnboardCompleteRequest(BaseModel):
    preferred_name: Optional[str] = None
    title: Optional[str] = None
    organization: Optional[str] = None
    industry: Optional[str] = None
    use_case: Optional[str] = None
    communication_style: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None


class ProfileVariables(BaseModel):
    """Variables available for assembler prompt injection."""
    preferred_name: Optional[str] = None
    title: Optional[str] = None
    organization: Optional[str] = None
    industry: Optional[str] = None
    use_case: Optional[str] = None
    communication_style: str = "balanced"
    timezone: str = "UTC"
    language: str = "en"
    is_onboarded: bool = False


# ─── Endpoint Registration ─────────────────────────────

MAX_IMAGE_BYTES = 2 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_LOGO_TYPES = {"image/jpeg", "image/png", "image/webp", "image/svg+xml"}


def register_profile_endpoints(app, auth_service, storage=None):
    """Register /profile/* and /api/me endpoints on the FastAPI app."""

    def _update_profile_fields(user_id: str, data: dict) -> UserProfile:
        """Write arbitrary profile columns and return refreshed profile."""
        if not auth_service._admin_client:
            raise HTTPException(503, "Database unavailable")

        update_data = {"updated_at": time.time()}
        for key, value in data.items():
            if key in PROFILE_FIELDS and value is not None:
                update_data[key] = value

        if len(update_data) <= 1:
            # Nothing to update beyond timestamp
            return auth_service.get_profile(user_id)

        try:
            auth_service._admin_client.table("profiles").update(
                update_data
            ).eq("user_id", user_id).execute()
        except Exception as e:
            logger.error(f"Profile update failed for {user_id}: {e}")
            raise HTTPException(500, "Failed to update profile")

        return auth_service.get_profile(user_id)

    @app.get("/profile", response_model=UserProfile, tags=["profile"])
    async def get_profile(user: UserProfile = Depends(require_auth)):
        """Get the authenticated user's full profile."""
        return auth_service.get_profile(user.user_id)

    @app.put("/profile", response_model=UserProfile, tags=["profile"])
    async def update_profile(
        req: ProfileUpdateRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """Update profile fields. Only non-null fields are written."""
        if req.communication_style and req.communication_style not in VALID_STYLES:
            raise HTTPException(400, f"communication_style must be one of: {', '.join(VALID_STYLES)}")
        data = req.model_dump(exclude_none=True)
        return _update_profile_fields(user.user_id, data)

    @app.post("/profile/onboard", response_model=UserProfile, tags=["profile"])
    async def onboard_complete(
        req: OnboardCompleteRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """Mark onboarding as complete and save profile fields collected during onboarding."""
        if req.communication_style and req.communication_style not in VALID_STYLES:
            raise HTTPException(400, f"communication_style must be one of: {', '.join(VALID_STYLES)}")

        data = req.model_dump(exclude_none=True)

        if not auth_service._admin_client:
            raise HTTPException(503, "Database unavailable")

        try:
            update_data = {
                "updated_at": time.time(),
                "onboarded_at": "now()",
            }
            for key, value in data.items():
                if key in PROFILE_FIELDS:
                    update_data[key] = value

            # Use raw SQL for now() or set Python-side timestamp
            # Supabase client doesn't support now() in update, use ISO string
            from datetime import datetime, timezone
            update_data["onboarded_at"] = datetime.now(timezone.utc).isoformat()

            auth_service._admin_client.table("profiles").update(
                update_data
            ).eq("user_id", user.user_id).execute()
            logger.info(f"Onboarding complete for user {user.user_id}")
        except Exception as e:
            logger.error(f"Onboarding completion failed for {user.user_id}: {e}")
            raise HTTPException(500, "Failed to complete onboarding")

        return auth_service.get_profile(user.user_id)

    @app.get("/profile/variables", response_model=ProfileVariables, tags=["profile"])
    async def get_profile_variables(user: UserProfile = Depends(require_auth)):
        """Get profile variables used for assembler prompt injection."""
        return ProfileVariables(
            preferred_name=user.preferred_name,
            title=user.title,
            organization=user.organization,
            industry=user.industry,
            use_case=user.use_case,
            communication_style=user.communication_style or "balanced",
            timezone=user.timezone or "UTC",
            language=user.language or "en",
            is_onboarded=user.onboarded_at is not None,
        )

    # ─── Workspace Profile Card: /api/me ────────────────

    def _profile_response(profile: UserProfile) -> dict:
        """Shape a UserProfile into the /api/me response format."""
        return {
            "user_id": profile.user_id,
            "email": profile.email,
            "display_name": profile.display_name,
            "avatar_url": profile.avatar_url,
            "title": profile.title,
            "bio": profile.bio,
            "preferred_name": profile.preferred_name,
            "tier": profile.tier,
            "role": profile.role,
            "timezone": profile.timezone or "UTC",
            "org": {
                "name": profile.organization,
                "logo_url": profile.org_logo_url,
            } if (profile.organization or profile.org_logo_url) else None,
        }

    @app.get("/api/me", tags=["profile"])
    async def api_get_me(user: UserProfile = Depends(require_auth)):
        """Workspace profile card: current user + org info."""
        profile = auth_service.get_profile(user.user_id)
        return _profile_response(profile)

    class WorkspaceProfileUpdate(BaseModel):
        display_name: Optional[str] = None
        title: Optional[str] = None
        bio: Optional[str] = None
        timezone: Optional[str] = None
        org_name: Optional[str] = None
        org_logo_url: Optional[str] = ""  # "" sentinel = not sent; None = clear
        avatar_url: Optional[str] = ""

    @app.patch("/api/me", tags=["profile"])
    async def api_update_me(
        body: WorkspaceProfileUpdate,
        user: UserProfile = Depends(require_auth),
    ):
        """Update workspace profile fields."""
        data = {}
        if body.display_name is not None:
            data["display_name"] = body.display_name
        if body.title is not None:
            data["title"] = body.title
        if body.bio is not None:
            data["bio"] = body.bio
        if body.timezone is not None:
            data["timezone"] = body.timezone
        if body.org_name is not None:
            data["org_name"] = body.org_name
        # org_logo_url / avatar_url: "" means not sent, None means clear
        if body.org_logo_url != "":
            data["org_logo_url"] = body.org_logo_url
        if body.avatar_url != "":
            data["avatar_url"] = body.avatar_url

        if not data:
            raise HTTPException(400, "No fields to update")

        updated = _update_profile_fields(user.user_id, data)
        return _profile_response(updated)

    @app.post("/api/me/avatar", tags=["profile"])
    async def api_upload_avatar(
        file: UploadFile = File(...),
        user: UserProfile = Depends(require_auth),
    ):
        """Upload avatar image. Max 2MB, jpg/png/webp only."""
        if not storage or not auth_service._admin_client:
            raise HTTPException(503, "Storage not available")

        if file.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                400,
                f"Image type not allowed. Use: {', '.join(ALLOWED_IMAGE_TYPES)}",
            )

        data = await file.read()
        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(400, "Image too large. Max 2MB")

        ext = file.content_type.split("/")[-1]
        if ext == "jpeg":
            ext = "jpg"
        filename = f"{user.user_id}/avatar.{ext}"

        try:
            url = await storage.upload_profile_image(filename, data, file.content_type)
            auth_service._admin_client.table("profiles") \
                .update({"avatar_url": url}) \
                .eq("user_id", user.user_id) \
                .execute()
            logger.info(f"Avatar uploaded for {user.user_id}")
            return {"avatar_url": url}
        except Exception as e:
            logger.error(f"Avatar upload failed for {user.user_id}: {e}")
            raise HTTPException(500, "Avatar upload failed")

    @app.post("/api/me/org-logo", tags=["profile"])
    async def api_upload_org_logo(
        file: UploadFile = File(...),
        user: UserProfile = Depends(require_auth),
    ):
        """Upload organization logo. Max 2MB, jpg/png/webp/svg."""
        if not storage or not auth_service._admin_client:
            raise HTTPException(503, "Storage not available")

        if file.content_type not in ALLOWED_LOGO_TYPES:
            raise HTTPException(
                400,
                f"Image type not allowed. Use: {', '.join(ALLOWED_LOGO_TYPES)}",
            )

        data = await file.read()
        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(400, "Image too large. Max 2MB")

        ext = file.content_type.split("/")[-1]
        if ext == "jpeg":
            ext = "jpg"
        elif ext == "svg+xml":
            ext = "svg"
        filename = f"{user.user_id}/org_logo.{ext}"

        try:
            url = await storage.upload_profile_image(filename, data, file.content_type)
            auth_service._admin_client.table("profiles") \
                .update({"org_logo_url": url}) \
                .eq("user_id", user.user_id) \
                .execute()
            logger.info(f"Org logo uploaded for {user.user_id}")
            return {"logo_url": url}
        except Exception as e:
            logger.error(f"Org logo upload failed for {user.user_id}: {e}")
            raise HTTPException(500, "Logo upload failed")

    logger.info("Profile endpoints registered: /profile/*, /api/me")
