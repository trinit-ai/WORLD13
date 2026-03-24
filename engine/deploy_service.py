"""
Deploy Service — orchestrates save + deploy operations for user-built packs.

Manages the lifecycle: Pack Builder session → saved pack → deployed link → public /go/{slug}.
"""
import json
import logging
import re
import uuid
from dataclasses import asdict
from typing import Optional

from pack_generator import GeneratedPack

logger = logging.getLogger("tmos13.deploy")

# Module-level singleton
_deploy_service: Optional["DeployService"] = None


def init_deploy_service(supabase_client, storage_client=None) -> "DeployService":
    """Initialize and return the global DeployService singleton."""
    global _deploy_service
    _deploy_service = DeployService(supabase_client, storage_client)
    return _deploy_service


def get_deploy_service() -> Optional["DeployService"]:
    return _deploy_service


def _slugify_for_url(name: str) -> str:
    """Generate a URL-safe slug from a display name."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:48] or "my-pack"


class DeployService:
    def __init__(self, db, storage=None):
        self._db = db
        self._storage = storage

    async def save_pack(self, owner_id: str, generated: GeneratedPack) -> str:
        """
        Save generated pack to user_packs table + upload protocol files to Storage.
        Returns user_pack_id (UUID).
        """
        pack_id = generated.pack_id
        storage_prefix = f"user_packs/{owner_id}/{pack_id}"

        # Upload protocol files to Supabase Storage
        if self._storage:
            for filename, content in generated.files.items():
                file_path = f"{storage_prefix}/{filename}"
                try:
                    self._storage.from_("protocols").upload(
                        file_path,
                        content.encode("utf-8"),
                        {"content-type": "text/markdown", "upsert": "true"},
                    )
                except Exception as e:
                    # Try update if file already exists
                    try:
                        self._storage.from_("protocols").update(
                            file_path,
                            content.encode("utf-8"),
                            {"content-type": "text/markdown"},
                        )
                    except Exception:
                        logger.warning(f"Storage upload failed for {file_path}: {e}")

        # Upsert to user_packs
        row = {
            "owner_id": owner_id,
            "pack_id": pack_id,
            "name": generated.name,
            "version": generated.version,
            "manifest": json.dumps(generated.manifest),
            "status": "active",
            "assembly_mode": generated.manifest.get("assembly_mode", "assembled"),
            "storage_prefix": storage_prefix,
            "category": generated.manifest.get("category", "custom"),
            "icon": generated.manifest.get("icon", "📦"),
            "tagline": generated.manifest.get("tagline", ""),
        }

        result = (
            self._db.table("user_packs")
            .upsert(row, on_conflict="owner_id,pack_id")
            .execute()
        )
        user_pack_id = result.data[0]["id"] if result.data else None
        logger.info(f"Pack saved: pack_id={pack_id}, user_pack_id={user_pack_id}, owner={owner_id}")
        return user_pack_id

    async def create_deployment(
        self,
        user_pack_id: str,
        owner_id: str,
        slug: str,
        display_name: str = None,
        policy: str = "open",
        style_preset: str = "dark",
    ) -> dict:
        """Create a pack_deployments row. Returns deployment record."""
        # Validate slug format
        clean_slug = re.sub(r"[^a-z0-9-]", "", slug.lower())
        if not clean_slug:
            raise ValueError("Slug must contain at least one alphanumeric character")

        row = {
            "user_pack_id": user_pack_id,
            "owner_id": owner_id,
            "slug": clean_slug,
            "display_name": display_name,
            "policy": policy,
            "style_preset": style_preset,
            "active": True,
        }

        result = self._db.table("pack_deployments").insert(row).execute()
        if not result.data:
            raise ValueError("Failed to create deployment")

        record = result.data[0]
        logger.info(f"Deployment created: slug={clean_slug}, id={record['id']}")
        return record

    async def update_deployment(self, deployment_id: str, owner_id: str, **kwargs) -> dict:
        """Update deployment settings. Only owner can update."""
        allowed_fields = {"slug", "display_name", "policy", "style_preset", "custom_theme", "active"}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields and v is not None}

        if not updates:
            raise ValueError("No valid fields to update")

        # Validate slug if being changed
        if "slug" in updates:
            updates["slug"] = re.sub(r"[^a-z0-9-]", "", updates["slug"].lower())

        result = (
            self._db.table("pack_deployments")
            .update(updates)
            .eq("id", deployment_id)
            .eq("owner_id", owner_id)
            .execute()
        )
        if not result.data:
            raise ValueError("Deployment not found or not owned by user")
        return result.data[0]

    async def deactivate_deployment(self, deployment_id: str, owner_id: str) -> bool:
        """Soft-disable a deployment."""
        result = (
            self._db.table("pack_deployments")
            .update({"active": False})
            .eq("id", deployment_id)
            .eq("owner_id", owner_id)
            .execute()
        )
        return bool(result.data)

    async def resolve_by_slug(self, slug: str) -> Optional[dict]:
        """
        Public lookup: slug → deployment + pack data.
        Used by /go/{slug} route to load a deployed pack.
        """
        # Get deployment record
        dep_result = (
            self._db.table("pack_deployments")
            .select("*, user_packs(*)")
            .eq("slug", slug)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        if not dep_result.data:
            return None

        dep = dep_result.data[0]
        user_pack = dep.get("user_packs", {})

        return {
            "deployment_id": dep["id"],
            "slug": dep["slug"],
            "display_name": dep.get("display_name"),
            "policy": dep["policy"],
            "style_preset": dep.get("style_preset", "dark"),
            "custom_theme": dep.get("custom_theme"),
            "owner_id": dep["owner_id"],
            "pack_id": user_pack.get("pack_id"),
            "manifest": user_pack.get("manifest"),
            "user_pack_id": dep["user_pack_id"],
        }

    async def list_deployments(self, owner_id: str) -> list[dict]:
        """All deployments for a user."""
        result = (
            self._db.table("pack_deployments")
            .select("*, user_packs(pack_id, name, icon, category, tagline)")
            .eq("owner_id", owner_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []

    async def generate_unique_slug(self, base_name: str) -> str:
        """Generate a unique slug from a base name, appending suffix if needed."""
        slug = _slugify_for_url(base_name)

        # Check if slug is taken
        existing = (
            self._db.table("pack_deployments")
            .select("id")
            .eq("slug", slug)
            .limit(1)
            .execute()
        )
        if not existing.data:
            return slug

        # Append short random suffix
        suffix = uuid.uuid4().hex[:6]
        return f"{slug}-{suffix}"
