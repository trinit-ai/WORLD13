"""
TMOS13 Pack Install API (Fibonacci Plume Node 12)

Authenticated endpoints for managing pack installations.

Endpoints:
  POST /api/packs/install           — Install a pack
  POST /api/packs/uninstall         — Uninstall a pack
  POST /api/packs/{pack_id}/activate — Resume paused install
  POST /api/packs/{pack_id}/pause   — Pause installed pack
  GET  /api/packs/installed         — List user's installed packs
  GET  /api/packs/{pack_id}/install-status — Check install status
  POST /api/packs/{pack_id}/checkout — Create Stripe checkout for paid pack
"""
import logging

from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel

from pack_install_service import get_pack_install_service

logger = logging.getLogger("tmos13.api_pack_install")


class PackInstallRequest(BaseModel):
    pack_id: str


def register_pack_install_endpoints(app: FastAPI, auth_service) -> None:
    """Register pack install endpoints. Must be called BEFORE parameterized /api/packs/{pack_id} routes."""

    from auth import require_auth, UserProfile

    @app.post("/api/packs/install")
    async def install_pack(req: PackInstallRequest, user: UserProfile = Depends(require_auth)):
        """Install a pack for the authenticated user."""
        svc = get_pack_install_service()
        if not svc or not svc.enabled:
            raise HTTPException(503, "Pack install service unavailable")
        try:
            result = svc.install(user.user_id, req.pack_id)
            return result
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.post("/api/packs/uninstall")
    async def uninstall_pack(req: PackInstallRequest, user: UserProfile = Depends(require_auth)):
        """Uninstall a pack for the authenticated user."""
        svc = get_pack_install_service()
        if not svc or not svc.enabled:
            raise HTTPException(503, "Pack install service unavailable")
        ok = svc.uninstall(user.user_id, req.pack_id)
        if not ok:
            raise HTTPException(500, "Failed to uninstall pack")
        return {"pack_id": req.pack_id, "status": "uninstalled"}

    @app.get("/api/packs/installed")
    async def list_installed_packs(
        status: str = None,
        user: UserProfile = Depends(require_auth),
    ):
        """List all installed packs for the authenticated user."""
        svc = get_pack_install_service()
        if not svc or not svc.enabled:
            return {"installs": [], "count": 0}
        installs = svc.get_user_installs(user.user_id, status_filter=status)
        return {"installs": installs, "count": len(installs)}

    @app.post("/api/packs/{pack_id}/activate")
    async def activate_pack(pack_id: str, user: UserProfile = Depends(require_auth)):
        """Resume a paused pack installation."""
        svc = get_pack_install_service()
        if not svc or not svc.enabled:
            raise HTTPException(503, "Pack install service unavailable")
        ok = svc.activate(user.user_id, pack_id)
        if not ok:
            raise HTTPException(400, "Failed to activate pack")
        return {"pack_id": pack_id, "status": "active"}

    @app.post("/api/packs/{pack_id}/pause")
    async def pause_pack(pack_id: str, user: UserProfile = Depends(require_auth)):
        """Pause an active pack installation."""
        svc = get_pack_install_service()
        if not svc or not svc.enabled:
            raise HTTPException(503, "Pack install service unavailable")
        ok = svc.pause(user.user_id, pack_id)
        if not ok:
            raise HTTPException(400, "Failed to pause pack")
        return {"pack_id": pack_id, "status": "paused"}

    @app.get("/api/packs/{pack_id}/install-status")
    async def pack_install_status(pack_id: str, user: UserProfile = Depends(require_auth)):
        """Check installation status of a specific pack."""
        svc = get_pack_install_service()
        if not svc or not svc.enabled:
            return {"pack_id": pack_id, "status": None, "installed": False}
        status = svc.get_install_status(user.user_id, pack_id)
        return {
            "pack_id": pack_id,
            "status": status,
            "installed": status in ("active", "paused"),
        }

    @app.post("/api/packs/{pack_id}/checkout")
    async def pack_checkout(pack_id: str, user: UserProfile = Depends(require_auth)):
        """Create a Stripe checkout session for a paid pack."""
        from billing import _billing_service
        if not _billing_service or not _billing_service.enabled:
            raise HTTPException(503, "Billing service unavailable")

        from billing import CheckoutRequest
        checkout_req = CheckoutRequest(
            price_id="",  # Will be resolved from pack manifest pricing
            mode="payment",
            success_url=f"https://tmos13.ai/packs/{pack_id}?checkout=success",
            cancel_url=f"https://tmos13.ai/packs/{pack_id}",
        )

        # Look up pack price from registry
        from pack_loader import load_pack_info
        info = load_pack_info(pack_id)
        library = info.get("library", {})
        price = library.get("price")
        stripe_price_id = library.get("stripe_price_id")

        if not stripe_price_id:
            raise HTTPException(400, "This pack does not have a configured price")

        checkout_req.price_id = stripe_price_id

        # Add pack_id to checkout metadata
        result = _billing_service.create_checkout(user.user_id, user.email or "", checkout_req)
        return {
            "checkout_url": result.checkout_url,
            "session_id": result.session_id,
            "pack_id": pack_id,
        }

    logger.info("Pack install endpoints registered: /api/packs/install, installed, activate, pause, checkout")
