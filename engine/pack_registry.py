"""
TMOS13 Pack Registry Service

Syncs pack manifests from the filesystem to the pack_registry Supabase table
on startup, and provides catalog queries for the public Pack Library.

Local mode adds library_index(), stub_count(), promote(), and list_packs()
for working with the protocols/library/ directory.

Follows pipeline_service.py singleton pattern.
"""
import hashlib
import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pack_loader import list_available_packs, load_pack_info, PACKS_DIR

LIBRARY_DIR = Path(__file__).resolve().parent.parent / "protocols" / "library"
PRIVATE_DIR = Path(__file__).resolve().parent.parent / "protocols" / "private"

logger = logging.getLogger("tmos13.pack_registry")

# ─── Config ──────────────────────────────────────────────────

PACK_REGISTRY_ENABLED = os.environ.get(
    "PACK_REGISTRY_ENABLED", "true"
).lower() in ("true", "1", "yes")


# ─── Service ─────────────────────────────────────────────────

class PackRegistryService:
    """Syncs pack manifests to the pack_registry table and serves catalog queries."""

    def __init__(self, db=None):
        self._db = db
        self._synced = False

    # ─── Sync ─────────────────────────────────────────────

    async def sync_repo_packs(self) -> int:
        """
        Scan protocols/packs/ and upsert each deployable pack into pack_registry.

        Returns the number of packs synced.
        """
        if not PACK_REGISTRY_ENABLED:
            logger.info("Pack registry: disabled via config")
            return 0

        if not self._db:
            logger.warning("Pack registry: no Supabase client — sync skipped")
            return 0

        pack_ids = list_available_packs()
        synced = 0

        for pack_id in pack_ids:
            try:
                info = load_pack_info(pack_id)
                if "error" in info:
                    logger.debug("Pack registry: skipping %s (%s)", pack_id, info["error"])
                    continue
                if info.get("visibility") == "internal":
                    logger.debug("Pack registry: skipping internal pack %s", pack_id)
                    continue

                library = info.get("library", {})
                manifest_path = PACKS_DIR / pack_id / "manifest.json"
                manifest_hash = ""
                if manifest_path.exists():
                    raw = manifest_path.read_bytes()
                    manifest_hash = hashlib.sha256(raw).hexdigest()[:16]

                row = {
                    "pack_id": pack_id,
                    "name": info.get("name", pack_id),
                    "version": info.get("version", "1.0.0"),
                    "description": info.get("description", ""),
                    "tagline": info.get("tagline", ""),
                    "icon": info.get("icon", ""),
                    "category": info.get("category", ""),
                    "author": library.get("author", "TMOS13"),
                    "author_type": "system",
                    "source": "repo",
                    "visibility": info.get("visibility", "public" if library.get("visible", True) else "internal"),
                    "status": "active",
                    "license": library.get("license", "included"),
                    "library_category": library.get("category", ""),
                    "library_tags": library.get("tags", []),
                    "verb_type": library.get("verb_type", ""),
                    "industry_tags": library.get("industry_tags", []),
                    "price_model": library.get("price", {}).get("model", "included"),
                    "tier_minimum": library.get("price", {}).get("tier_minimum"),
                    "price_cents": 0,
                    "manifest_hash": manifest_hash,
                    "cartridge_count": info.get("cartridge_count", 0),
                    "feature_flags": json.dumps(info.get("features", {})),
                    "theme": json.dumps(info.get("theme", {})),
                    "published_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }

                self._db.table("pack_registry").upsert(
                    row, on_conflict="pack_id"
                ).execute()
                synced += 1

            except Exception as e:
                logger.warning("Pack registry: failed to sync %s: %s", pack_id, e)

        self._synced = True
        logger.info("Pack registry: synced %d/%d repo packs", synced, len(pack_ids))
        return synced

    # ─── Catalog Queries ──────────────────────────────────

    async def get_catalog(
        self,
        category: Optional[str] = None,
        verb_type: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> list[dict]:
        """
        Query pack_registry for public catalog entries.

        Filters by library_category, verb_type, or tag (array contains).
        Only returns public + active packs.
        """
        if not self._db:
            return []

        try:
            query = (
                self._db.table("pack_registry")
                .select("*")
                .eq("status", "active")
                .eq("visibility", "public")
            )

            if category:
                query = query.eq("library_category", category)
            if verb_type:
                query = query.eq("verb_type", verb_type)
            if tag:
                query = query.contains("library_tags", [tag])

            result = query.order("name").execute()
            entries = result.data or []

            # Re-nest flat DB columns into the `library` object the frontend expects
            for entry in entries:
                entry["library"] = {
                    "visible": True,
                    "category": entry.pop("library_category", ""),
                    "tags": entry.pop("library_tags", []),
                    "verb_type": entry.pop("verb_type", ""),
                    "industry_tags": entry.pop("industry_tags", []),
                }

            return entries

        except Exception as e:
            logger.warning("Pack registry: catalog query failed: %s", e)
            return []

    async def get_pack_detail(self, pack_id: str) -> Optional[dict]:
        """Get full registry entry for a single pack."""
        if not self._db:
            return None

        try:
            result = (
                self._db.table("pack_registry")
                .select("*")
                .eq("pack_id", pack_id)
                .eq("status", "active")
                .maybe_single()
                .execute()
            )
            return result.data

        except Exception as e:
            logger.warning("Pack registry: detail query failed for %s: %s", pack_id, e)
            return None

    @property
    def is_synced(self) -> bool:
        """Whether the registry has been synced at least once."""
        return self._synced

    # ─── Local Library Methods ─────────────────────────────

    def library_index(self) -> dict:
        """Read protocols/library/index.yaml and return parsed structure.

        Returns dict with keys: categories, total, active, stubs.
        """
        index_path = LIBRARY_DIR / "index.yaml"
        if not index_path.exists():
            return {"categories": {}, "total": 0, "active": 0, "stubs": 0}

        # Simple YAML-like parse (avoids PyYAML dependency)
        categories = {}
        active = 0
        stubs = 0

        for cat_dir in sorted(LIBRARY_DIR.iterdir()):
            if not cat_dir.is_dir():
                continue
            cat_id = cat_dir.name
            cat_packs = []
            cat_active = 0

            for pack_dir in sorted(cat_dir.iterdir()):
                if not pack_dir.is_dir():
                    continue
                has_manifest = (pack_dir / "manifest.json").exists()
                status = "active" if has_manifest else "stub"
                if has_manifest:
                    cat_active += 1
                    active += 1
                else:
                    stubs += 1
                cat_packs.append({"id": pack_dir.name, "status": status})

            if cat_packs:
                categories[cat_id] = {
                    "total": len(cat_packs),
                    "active": cat_active,
                    "packs": cat_packs,
                }

        return {
            "categories": categories,
            "total": active + stubs,
            "active": active,
            "stubs": stubs,
        }

    def stub_count(self) -> dict:
        """Return stub counts by category.

        Returns dict: {category_id: stub_count, ...}
        """
        counts = {}
        if not LIBRARY_DIR.exists():
            return counts
        for cat_dir in sorted(LIBRARY_DIR.iterdir()):
            if not cat_dir.is_dir():
                continue
            n = sum(
                1 for p in cat_dir.iterdir()
                if p.is_dir() and (p / "header.yaml").exists()
                and not (p / "manifest.json").exists()
            )
            if n > 0:
                counts[cat_dir.name] = n
        return counts

    def promote(self, pack_id: str, category: str = None) -> str:
        """Copy a pack from protocols/library/{category}/{pack_id} to protocols/packs/.

        If category is not provided, searches all categories.
        Returns the destination path, or raises FileNotFoundError.
        """
        source = None
        if category:
            candidate = LIBRARY_DIR / category / pack_id
            if candidate.is_dir():
                source = candidate
        else:
            for cat_dir in LIBRARY_DIR.iterdir():
                if not cat_dir.is_dir():
                    continue
                candidate = cat_dir / pack_id
                if candidate.is_dir():
                    source = candidate
                    break

        if not source or not source.exists():
            raise FileNotFoundError(f"Pack '{pack_id}' not found in library")

        if not (source / "manifest.json").exists():
            raise ValueError(f"Pack '{pack_id}' is a stub — develop it first (add manifest.json + protocol files)")

        dest = PACKS_DIR / pack_id
        if dest.exists():
            raise FileExistsError(f"Pack '{pack_id}' already exists in protocols/packs/")

        shutil.copytree(source, dest)
        logger.info("Pack promoted: %s → %s", source, dest)
        return str(dest)

    def list_packs(self, library: bool = False) -> list[dict]:
        """List packs from protocols/packs/ or protocols/library/.

        Returns list of dicts with: id, name, status, category (library only).
        """
        results = []

        if library:
            for cat_dir in sorted(LIBRARY_DIR.iterdir()):
                if not cat_dir.is_dir():
                    continue
                for pack_dir in sorted(cat_dir.iterdir()):
                    if not pack_dir.is_dir():
                        continue
                    has_manifest = (pack_dir / "manifest.json").exists()
                    name = pack_dir.name
                    if has_manifest:
                        try:
                            m = json.loads((pack_dir / "manifest.json").read_text())
                            name = m.get("name", pack_dir.name)
                        except Exception:
                            pass
                    results.append({
                        "id": pack_dir.name,
                        "name": name,
                        "status": "active" if has_manifest else "stub",
                        "category": cat_dir.name,
                    })
        else:
            for pack_dir in sorted(PACKS_DIR.iterdir()):
                if not pack_dir.is_dir() or not (pack_dir / "manifest.json").exists():
                    continue
                try:
                    m = json.loads((pack_dir / "manifest.json").read_text())
                    name = m.get("name", pack_dir.name)
                except Exception:
                    name = pack_dir.name
                results.append({
                    "id": pack_dir.name,
                    "name": name,
                    "status": "active",
                })

        return results

    # ─── Private Pack Methods ──────────────────────────────

    def list_private_packs(self) -> list[dict]:
        """List packs from protocols/private/.

        Returns list of dicts with: id, name, status, auth_required.
        Names are included only for authenticated listing.
        """
        results = []
        if not PRIVATE_DIR.exists():
            return results
        for pack_dir in sorted(PRIVATE_DIR.iterdir()):
            if not pack_dir.is_dir() or pack_dir.name.startswith("."):
                continue
            # Check for header.yaml or manifest.json
            has_header = (pack_dir / "header.yaml").exists()
            has_manifest = (pack_dir / "manifest.json").exists()
            if not has_header and not has_manifest:
                continue

            name = pack_dir.name
            auth_required = False

            if has_header:
                try:
                    import yaml
                    header = yaml.safe_load((pack_dir / "header.yaml").read_text())
                    name = header.get("name", pack_dir.name)
                    auth_required = header.get("auth", {}).get("type") == "passphrase"
                except Exception:
                    pass

            results.append({
                "id": pack_dir.name,
                "name": name,
                "status": "private",
                "auth_required": auth_required,
            })
        return results

    def private_pack_count(self) -> int:
        """Return the count of private packs (without revealing names)."""
        if not PRIVATE_DIR.exists():
            return 0
        return sum(
            1 for p in PRIVATE_DIR.iterdir()
            if p.is_dir() and not p.name.startswith(".")
            and ((p / "header.yaml").exists() or (p / "manifest.json").exists())
        )

    def load_private_header(self, pack_id: str) -> dict:
        """Load header.yaml for a private pack. Returns dict or empty."""
        header_path = PRIVATE_DIR / pack_id / "header.yaml"
        if not header_path.exists():
            return {}
        try:
            import yaml
            return yaml.safe_load(header_path.read_text()) or {}
        except Exception:
            return {}

    def is_private_pack(self, pack_id: str) -> bool:
        """Check if a pack_id exists in protocols/private/."""
        return (PRIVATE_DIR / pack_id).is_dir()


# ─── Singleton ────────────────────────────────────────────────

_pack_registry: Optional[PackRegistryService] = None


def init_pack_registry(db=None) -> PackRegistryService:
    """Initialize the global pack registry service. Called during app lifespan."""
    global _pack_registry
    _pack_registry = PackRegistryService(db=db)
    return _pack_registry


def get_pack_registry() -> Optional[PackRegistryService]:
    """Get the global pack registry service instance."""
    return _pack_registry
