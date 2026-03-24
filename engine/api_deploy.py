"""
Deploy REST API — save, deploy, and manage pack deployments.

Endpoints:
  POST   /api/deploy/save            — Save generated pack from Pack Builder session
  POST   /api/deploy/create          — Create deployment for a saved pack
  GET    /api/deploy/list            — List user's deployments
  PATCH  /api/deploy/:id             — Update deployment settings
  DELETE /api/deploy/:id             — Deactivate deployment
  GET    /api/deploy/resolve/:slug   — Public: resolve slug → pack + deployment config

Registration: register_deploy_endpoints(app, deploy_service, sessions, llm_provider)
"""
import logging
from typing import Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from auth import require_auth, UserProfile
from deploy_service import DeployService

logger = logging.getLogger("tmos13.deploy_api")


# ── Request Models ──────────────────────────────────────

class SavePackRequest(BaseModel):
    session_id: str


class CreateDeploymentRequest(BaseModel):
    user_pack_id: str
    slug: Optional[str] = None
    display_name: Optional[str] = None
    policy: str = "open"
    style_preset: str = "dark"


class UpdateDeploymentRequest(BaseModel):
    slug: Optional[str] = None
    display_name: Optional[str] = None
    policy: Optional[str] = None
    style_preset: Optional[str] = None
    custom_theme: Optional[dict] = None
    active: Optional[bool] = None


# ── Response Models ─────────────────────────────────────

class SavePackResponse(BaseModel):
    user_pack_id: str
    pack_id: str
    name: str


class DeploymentResponse(BaseModel):
    id: str
    user_pack_id: str
    owner_id: str
    slug: str
    display_name: Optional[str] = None
    policy: str
    style_preset: Optional[str] = None
    custom_theme: Optional[dict] = None
    active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    public_url: Optional[str] = None
    user_packs: Optional[dict] = None


class ResolveResponse(BaseModel):
    deployment_id: str
    slug: str
    display_name: Optional[str] = None
    policy: str
    style_preset: Optional[str] = None
    custom_theme: Optional[dict] = None
    owner_id: str
    pack_id: Optional[str] = None
    manifest: Optional[dict] = None
    user_pack_id: str


def _deployment_response(record: dict) -> DeploymentResponse:
    """Convert DB record to response model."""
    resp = DeploymentResponse(
        id=record["id"],
        user_pack_id=record["user_pack_id"],
        owner_id=record["owner_id"],
        slug=record["slug"],
        display_name=record.get("display_name"),
        policy=record["policy"],
        style_preset=record.get("style_preset"),
        custom_theme=record.get("custom_theme"),
        active=record["active"],
        created_at=str(record.get("created_at", "")),
        updated_at=str(record.get("updated_at", "")),
        public_url=f"/go/{record['slug']}",
    )
    if "user_packs" in record:
        resp.user_packs = record["user_packs"]
    return resp


def register_deploy_endpoints(app, deploy_service: DeployService, sessions, llm_provider_fn):
    """Register all deploy endpoints. Called in app.py lifespan."""

    @app.post("/api/deploy/save", response_model=SavePackResponse, tags=["deploy"])
    async def save_pack(req: SavePackRequest, user: UserProfile = Depends(require_auth)):
        """Save generated pack from Pack Builder session state."""
        # Get session from active sessions
        state = sessions.get(req.session_id)
        if not state:
            raise HTTPException(404, f"Session {req.session_id} not found or expired")

        # Verify session belongs to the requesting user
        if state.user_id != user.user_id and state.user_id != "anonymous":
            raise HTTPException(403, "Session does not belong to this user")

        # Check that pack_spec has data
        spec = state.pack_spec
        if not spec or not spec.pack_name:
            raise HTTPException(
                400,
                "No pack specification found in session. Complete the Pack Builder flow first.",
            )

        # Generate pack from session
        from pack_generator import generate_pack_from_session

        llm = llm_provider_fn()
        transcript = [
            {"role": m.get("role", "user"), "content": m.get("content", "")}
            for m in state.history
        ]

        generated = await generate_pack_from_session(
            session_state=state,
            transcript=transcript,
            llm_provider=llm,
            owner_id=user.user_id,
        )

        # Save pack
        user_pack_id = await deploy_service.save_pack(user.user_id, generated)
        return SavePackResponse(
            user_pack_id=user_pack_id,
            pack_id=generated.pack_id,
            name=generated.name,
        )

    @app.post("/api/deploy/create", response_model=DeploymentResponse, tags=["deploy"])
    async def create_deployment(req: CreateDeploymentRequest, user: UserProfile = Depends(require_auth)):
        """Create a deployment for a saved pack."""
        # Auto-generate slug if not provided
        slug = req.slug
        if not slug:
            # Look up pack name for slug generation
            try:
                pack_result = (
                    deploy_service._db.table("user_packs")
                    .select("name")
                    .eq("id", req.user_pack_id)
                    .eq("owner_id", user.user_id)
                    .limit(1)
                    .execute()
                )
                if not pack_result.data:
                    raise HTTPException(404, "Pack not found or not owned by user")
                slug = await deploy_service.generate_unique_slug(pack_result.data[0]["name"])
            except HTTPException:
                raise
            except Exception:
                slug = await deploy_service.generate_unique_slug("my-pack")

        try:
            record = await deploy_service.create_deployment(
                user_pack_id=req.user_pack_id,
                owner_id=user.user_id,
                slug=slug,
                display_name=req.display_name,
                policy=req.policy,
                style_preset=req.style_preset,
            )
        except Exception as e:
            if "unique_deployment_slug" in str(e).lower() or "duplicate" in str(e).lower():
                raise HTTPException(409, f"Slug '{slug}' is already taken")
            raise HTTPException(400, str(e))

        return _deployment_response(record)

    @app.get("/api/deploy/list", tags=["deploy"])
    async def list_deployments(user: UserProfile = Depends(require_auth)):
        """List all deployments for the authenticated user."""
        deployments = await deploy_service.list_deployments(user.user_id)
        return {
            "deployments": [_deployment_response(d) for d in deployments],
            "total": len(deployments),
        }

    @app.patch("/api/deploy/{deployment_id}", response_model=DeploymentResponse, tags=["deploy"])
    async def update_deployment(
        deployment_id: str,
        req: UpdateDeploymentRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """Update deployment settings."""
        try:
            updates = req.model_dump(exclude_none=True)
            record = await deploy_service.update_deployment(
                deployment_id, user.user_id, **updates
            )
        except ValueError as e:
            raise HTTPException(400, str(e))
        return _deployment_response(record)

    @app.delete("/api/deploy/{deployment_id}", tags=["deploy"])
    async def deactivate_deployment(
        deployment_id: str,
        user: UserProfile = Depends(require_auth),
    ):
        """Soft-deactivate a deployment."""
        success = await deploy_service.deactivate_deployment(deployment_id, user.user_id)
        if not success:
            raise HTTPException(404, "Deployment not found or not owned by user")
        return {"deactivated": True, "id": deployment_id}

    @app.get("/api/deploy/resolve/{slug}", response_model=ResolveResponse, tags=["deploy"])
    async def resolve_deployment(slug: str):
        """Public endpoint — resolve a deployment slug to pack + config."""
        resolved = await deploy_service.resolve_by_slug(slug)
        if not resolved:
            raise HTTPException(404, f"No active deployment found for slug '{slug}'")
        return ResolveResponse(**resolved)
