"""
TMOS13 Pack API — Expose pack metadata to frontend

Provides endpoints for the frontend to discover available packs,
get current pack info, and switch packs at runtime.

Endpoints:
  GET  /api/packs            — list all deployable packs (includes user packs if authenticated)
  GET  /api/packs/{pack_id}  — get detailed info for a specific pack
  GET  /api/pack             — get current default pack info
  POST /api/pack             — switch pack (returns new pack info)
"""
from typing import Optional
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from auth import get_current_user, UserProfile
from pack_loader import (
    list_available_packs, load_pack_info, list_user_packs, PACKS_DIR,
    _is_deployable, get_available_packs,
)
from pack_registry import get_pack_registry
from config import logger, TMOS13_PACK, get_pack


class PackSwitchRequest(BaseModel):
    pack_id: str


def register_pack_endpoints(app: FastAPI) -> None:
    """Register pack discovery endpoints on the FastAPI application."""

    @app.get("/api/packs/catalog")
    async def api_pack_catalog(
        category: str = None,
        verb_type: str = None,
        tag: str = None,
        user: Optional[UserProfile] = Depends(get_current_user),
    ):
        """Public pack catalog with tier-aware access metadata."""
        authenticated = bool(user)
        user_tier = user.tier if user else None
        user_role = user.role if user else None

        # Try registry first (Supabase) — enrich with tier info
        registry = get_pack_registry()
        if registry and registry.is_synced:
            try:
                entries = await registry.get_catalog(
                    category=category, verb_type=verb_type, tag=tag,
                )
                if entries:
                    # Filter internal packs from catalog
                    entries = [e for e in entries if e.get("visibility") != "internal"]
                    # Enrich registry entries with tier-aware locked status
                    from pack_loader import tier_meets_minimum
                    from auth import role_at_least
                    is_privileged = bool(user_role and role_at_least(user_role, "admin"))
                    for entry in entries:
                        access = entry.get("access", "paid")
                        tier_gate = entry.get("tier_gate") or entry.get("tier_minimum") or "S1"
                        if access != "paid":
                            entry["locked"] = False
                        elif is_privileged:
                            entry["locked"] = False
                        elif user_tier and tier_meets_minimum(user_tier, tier_gate):
                            entry["locked"] = False
                        else:
                            entry["locked"] = True
                            entry["tier_required"] = tier_gate
                    return {"packs": entries, "source": "registry"}
            except Exception as e:
                logger.warning(f"Catalog registry query failed, falling back to tier-aware: {e}")

        # Tier-aware filesystem fallback
        packs = get_available_packs(user_tier=user_tier, authenticated=authenticated, user_role=user_role)
        # Apply library-level filters
        filtered = []
        for info in packs:
            if info.get("visibility") == "internal":
                continue
            library = info.get("library", {})
            if not library.get("visible", True):
                continue
            if category and library.get("category") != category:
                continue
            if verb_type and library.get("verb_type") != verb_type:
                continue
            if tag and tag not in library.get("tags", []):
                continue
            info["source"] = "repo"
            filtered.append(info)

        return {"packs": filtered, "source": "filesystem"}

    @app.get("/api/packs")
    async def api_list_packs(
        include_internal: bool = False,
        user: Optional[UserProfile] = Depends(get_current_user),
    ):
        """Return all deployable packs with metadata. Includes user packs if authenticated."""
        # Repo packs (always available)
        pack_ids = list_available_packs()
        packs = []
        for pid in pack_ids:
            info = load_pack_info(pid)
            if "error" not in info:
                # Filter out internal packs (e.g. welcome, guest) from browse lists
                if not include_internal and info.get("visibility") == "internal":
                    continue
                info["source"] = "repo"
                packs.append(info)

        # User packs (if authenticated)
        user_id = user.user_id if user else None
        if user_id:
            try:
                user_pack_list = await list_user_packs(user_id, status="active")
                for up in user_pack_list:
                    manifest = up.get("manifest", {}) if "manifest" in up else {}
                    # Extract cartridge info from manifest
                    carts = manifest.get("cartridges", [])
                    cart_count = len(carts) if isinstance(carts, (list, dict)) else 0
                    cart_list = []
                    if isinstance(carts, list):
                        for i, c in enumerate(carts):
                            cart_list.append({
                                "key": c.get("id", f"cart_{i}"),
                                "name": c.get("name", ""),
                                "description": c.get("description", ""),
                            })
                    elif isinstance(carts, dict):
                        for k, v in sorted(carts.items(), key=lambda kv: kv[1].get("number", 999)):
                            cart_list.append({
                                "key": k,
                                "name": v.get("name", ""),
                                "description": v.get("description", ""),
                            })

                    packs.append({
                        "pack_id": up["pack_id"],
                        "name": up["name"],
                        "version": up.get("version", "1.0.0"),
                        "description": up.get("description", ""),
                        "category": up.get("category", "custom"),
                        "icon": up.get("icon", "\U0001F4E6"),
                        "tagline": up.get("tagline", ""),
                        "theme": manifest.get("theme", {}),
                        "cartridge_count": cart_count,
                        "cartridges": cart_list,
                        "personality_summary": manifest.get("personality", {}).get("tone", ""),
                        "source": "user",
                        "status": up.get("status"),
                        "deployed_as": up.get("deployed_as"),
                    })
            except Exception as e:
                logger.warning(f"Failed to list user packs for {user_id}: {e}")

        return {"packs": packs}

    @app.get("/api/pack")
    async def api_get_current_pack():
        """Return metadata for the current default pack."""
        pack = get_pack()
        if not pack:
            raise HTTPException(status_code=500, detail=f"Failed to load default pack '{TMOS13_PACK}'")
        return pack.to_public_info()

    @app.post("/api/pack")
    async def api_switch_pack(req: PackSwitchRequest):
        """
        Validate and return info for a pack switch.

        The actual session switch happens when the frontend sends the pack_id
        with its next WebSocket message or chat request. This endpoint just
        validates the pack exists and returns its metadata so the frontend
        can update the UI immediately.
        """
        pack_id = req.pack_id
        pack_dir = PACKS_DIR / pack_id
        if not pack_dir.exists() or not (pack_dir / "manifest.json").exists():
            raise HTTPException(status_code=404, detail=f"Pack '{pack_id}' not found")
        if not _is_deployable(pack_id):
            raise HTTPException(status_code=403, detail=f"Pack '{pack_id}' is not available")
        pack = get_pack(pack_id)
        if not pack:
            raise HTTPException(status_code=500, detail=f"Failed to load pack '{pack_id}'")
        return pack.to_public_info()

    @app.get("/api/packs/{pack_id}")
    async def api_get_pack_info(pack_id: str):
        """Return full pack metadata for a specific vertical."""
        pack_dir = PACKS_DIR / pack_id
        if not pack_dir.exists() or not (pack_dir / "manifest.json").exists():
            raise HTTPException(status_code=404, detail=f"Pack '{pack_id}' not found")
        pack = get_pack(pack_id)
        if not pack:
            raise HTTPException(status_code=500, detail=f"Failed to load pack '{pack_id}'")
        return pack.to_public_info()
