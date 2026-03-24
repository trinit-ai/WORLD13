"""
13TMOS Manifest Archive — Version Preservation

Old manifest versions must be retrievable for audit compliance.
When a manifest is updated, the previous version is automatically
archived before the update is written.

Structure:
    protocols/packs/{pack_id}/versions/
    +-- 1.0.md
    +-- 1.1.md
    +-- current -> ../MANIFEST.md (symlink)
"""
import logging
import shutil
from pathlib import Path

logger = logging.getLogger("13tmos.manifest_archive")

ROOT_DIR = Path(__file__).resolve().parent.parent
PACKS_DIR = ROOT_DIR / "protocols" / "packs"


class ManifestArchive:
    """Manages manifest version history for audit compliance."""

    def __init__(self, packs_dir: Path = None):
        self.packs_dir = packs_dir or PACKS_DIR

    def archive_current(self, pack_id: str) -> str | None:
        """Copy current MANIFEST.md to versions/ before updating.

        Returns archived path, or None if no manifest exists.
        """
        pack_dir = self.packs_dir / pack_id
        manifest_path = pack_dir / "MANIFEST.md"

        if not manifest_path.exists():
            logger.warning("No MANIFEST.md to archive for %s", pack_id)
            return None

        versions_dir = pack_dir / "versions"
        versions_dir.mkdir(exist_ok=True)

        # Determine version from manifest.json or header.yaml
        version = self._get_current_version(pack_id)
        if not version:
            # Fallback: count existing versions + 1
            existing = self.list_versions(pack_id)
            version = f"{len(existing) + 1}.0"

        archive_path = versions_dir / f"{version}.md"

        # Don't overwrite an existing archive
        if archive_path.exists():
            logger.info("Version %s already archived for %s", version, pack_id)
            return str(archive_path)

        shutil.copy2(manifest_path, archive_path)
        logger.info("Archived %s MANIFEST.md as version %s", pack_id, version)

        # Update current symlink
        current_link = versions_dir / "current"
        if current_link.exists() or current_link.is_symlink():
            current_link.unlink()
        current_link.symlink_to("../MANIFEST.md")

        return str(archive_path)

    def retrieve_version(self, pack_id: str, version: str) -> str | None:
        """Return manifest content for a specific version.

        Checks versions/ directory first, then falls back to current
        MANIFEST.md if the version matches the current version.
        """
        pack_dir = self.packs_dir / pack_id
        versions_dir = pack_dir / "versions"

        # Try exact version file
        version_path = versions_dir / f"{version}.md"
        if version_path.exists():
            return version_path.read_text()

        # Try with minor version variations
        # e.g., "1.0.0" -> try "1.0.md", "1.0.0.md"
        for variant in [version, version.rsplit(".", 1)[0] if "." in version else version]:
            vp = versions_dir / f"{variant}.md"
            if vp.exists():
                return vp.read_text()

        # Fall back to current MANIFEST.md if version matches
        current_version = self._get_current_version(pack_id)
        if current_version and (version == current_version or
                                version == current_version.rsplit(".", 1)[0]):
            manifest_path = pack_dir / "MANIFEST.md"
            if manifest_path.exists():
                return manifest_path.read_text()

        return None

    def list_versions(self, pack_id: str) -> list[str]:
        """List all archived versions for a pack, sorted."""
        pack_dir = self.packs_dir / pack_id
        versions_dir = pack_dir / "versions"

        if not versions_dir.exists():
            return []

        versions = []
        for path in versions_dir.glob("*.md"):
            if path.name == "current":
                continue
            versions.append(path.stem)

        # Sort by version number
        def version_key(v):
            try:
                parts = v.split(".")
                return tuple(int(p) for p in parts)
            except ValueError:
                return (0,)

        versions.sort(key=version_key)
        return versions

    def _get_current_version(self, pack_id: str) -> str | None:
        """Get current version from manifest.json."""
        manifest_json = self.packs_dir / pack_id / "manifest.json"
        if manifest_json.exists():
            try:
                import json
                data = json.loads(manifest_json.read_text())
                return data.get("version")
            except Exception:
                pass

        # Try header.yaml
        header_path = self.packs_dir / pack_id / "header.yaml"
        if header_path.exists():
            try:
                import yaml
                data = yaml.safe_load(header_path.read_text())
                return data.get("version")
            except Exception:
                pass

        return None

    def ensure_current_archived(self, pack_id: str) -> str | None:
        """Archive current version if not already archived. Idempotent."""
        version = self._get_current_version(pack_id)
        if not version:
            return None

        versions_dir = self.packs_dir / pack_id / "versions"
        archive_path = versions_dir / f"{version}.md"

        if archive_path.exists():
            return str(archive_path)

        return self.archive_current(pack_id)
