"""
TMOS13 Storage Layer

Supabase Storage integration for protocol files and generated assets.
Falls back to local filesystem storage when Supabase is not configured.

Buckets:
  - protocols: Protocol .md files
  - assets:    Generated/uploaded binary assets (images, audio, etc.)
  - exports:   Session state exports (JSON)
"""
import asyncio
import json
import time
from pathlib import Path
from typing import Union

from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, BASE_DIR, logger


# ─── Supabase Storage Client ────────────────────────────────

class StorageClient:
    """Supabase Storage integration for protocol files and generated assets."""

    PROTOCOLS_BUCKET = "protocols"
    ASSETS_BUCKET = "assets"
    EXPORTS_BUCKET = "exports"
    PROFILES_BUCKET = "profiles"

    def __init__(self, supabase_url: str, supabase_key: str):
        from supabase import create_client
        self.client = create_client(supabase_url, supabase_key)
        self._storage = self.client.storage
        logger.info("Supabase storage client initialized")

    # ─── Protocols ───────────────────────────────────────────

    async def upload_protocol(self, filename: str, content: str) -> str:
        """Upload a protocol .md file and return its public URL."""
        data = content.encode("utf-8")

        def _upload():
            self._storage.from_(self.PROTOCOLS_BUCKET).upload(
                filename, data, {"content-type": "text/plain; charset=utf-8"}
            )
            return self._storage.from_(self.PROTOCOLS_BUCKET).get_public_url(filename)

        url = await asyncio.to_thread(_upload)
        logger.info(f"Uploaded protocol: {filename}")
        return url

    async def download_protocol(self, filename: str) -> str:
        """Download protocol text content by filename."""
        def _download():
            response = self._storage.from_(self.PROTOCOLS_BUCKET).download(filename)
            return response.decode("utf-8")

        content = await asyncio.to_thread(_download)
        logger.debug(f"Downloaded protocol: {filename}")
        return content

    async def list_protocols(self) -> list[dict]:
        """List all protocols in the bucket with name, size, and updated metadata."""
        def _list():
            files = self._storage.from_(self.PROTOCOLS_BUCKET).list()
            return [
                {
                    "name": f.get("name", ""),
                    "size": f.get("metadata", {}).get("size", 0),
                    "updated": f.get("updated_at", ""),
                }
                for f in files
                if f.get("name")
            ]

        return await asyncio.to_thread(_list)

    # ─── Assets ──────────────────────────────────────────────

    async def upload_asset(self, filename: str, data: bytes, content_type: str) -> str:
        """Upload a binary asset (image, audio, etc.) and return its public URL."""
        def _upload():
            self._storage.from_(self.ASSETS_BUCKET).upload(
                filename, data, {"content-type": content_type}
            )
            return self._storage.from_(self.ASSETS_BUCKET).get_public_url(filename)

        url = await asyncio.to_thread(_upload)
        logger.info(f"Uploaded asset: {filename} ({content_type})")
        return url

    async def upload_profile_image(self, filename: str, data: bytes, content_type: str) -> str:
        """Upload a profile image (avatar/logo) to the profiles bucket. Upserts."""
        def _upload():
            try:
                self._storage.from_(self.PROFILES_BUCKET).remove([filename])
            except Exception:
                pass  # File may not exist yet
            self._storage.from_(self.PROFILES_BUCKET).upload(
                filename, data, {"content-type": content_type}
            )
            return self._storage.from_(self.PROFILES_BUCKET).get_public_url(filename)

        url = await asyncio.to_thread(_upload)
        logger.info(f"Uploaded profile image: {filename} ({content_type})")
        return url

    # ─── Signed URLs ─────────────────────────────────────────

    async def get_signed_url(self, bucket: str, path: str, expires_in: int = 3600) -> str:
        """Generate a signed URL for private file access."""
        def _sign():
            result = self._storage.from_(bucket).create_signed_url(path, expires_in)
            return result.get("signedURL", "")

        url = await asyncio.to_thread(_sign)
        logger.debug(f"Signed URL for {bucket}/{path} (expires in {expires_in}s)")
        return url

    # ─── Exports ─────────────────────────────────────────────

    async def export_session(self, session_id: str, data: dict) -> str:
        """Export session state as JSON to the exports bucket, return URL."""
        filename = f"{session_id}.json"
        payload = json.dumps(data, indent=2, default=str).encode("utf-8")

        def _upload():
            self._storage.from_(self.EXPORTS_BUCKET).upload(
                filename, payload, {"content-type": "application/json"}
            )
            return self._storage.from_(self.EXPORTS_BUCKET).get_public_url(filename)

        url = await asyncio.to_thread(_upload)
        logger.info(f"Exported session: {session_id}")
        return url

    # ─── User Packs ───────────────────────────────────────────

    USER_PACKS_PREFIX = "user-packs"

    async def upload_user_pack_file(
        self, owner_id: str, pack_id: str, filename: str, content: str
    ) -> str:
        """Upload a user pack protocol file to scoped storage."""
        path = f"{self.USER_PACKS_PREFIX}/{owner_id}/{pack_id}/{filename}"
        data = content.encode("utf-8")

        def _upload():
            # Upsert: remove existing then upload
            try:
                self._storage.from_(self.PROTOCOLS_BUCKET).remove([path])
            except Exception:
                pass  # File may not exist yet
            self._storage.from_(self.PROTOCOLS_BUCKET).upload(
                path, data, {"content-type": "text/plain; charset=utf-8"}
            )
            return path

        result = await asyncio.to_thread(_upload)
        logger.info(f"Uploaded user pack file: {result}")
        return result

    async def download_user_pack_file(
        self, storage_prefix: str, filename: str
    ) -> str:
        """Download a single protocol file from user pack storage."""
        path = f"{storage_prefix}{filename}"

        def _download():
            response = self._storage.from_(self.PROTOCOLS_BUCKET).download(path)
            return response.decode("utf-8")

        content = await asyncio.to_thread(_download)
        logger.debug(f"Downloaded user pack file: {path}")
        return content

    async def delete_user_pack_files(self, storage_prefix: str) -> None:
        """Delete all files under a user pack storage prefix."""
        def _delete():
            files = self._storage.from_(self.PROTOCOLS_BUCKET).list(storage_prefix)
            if files:
                paths = [f"{storage_prefix}{f['name']}" for f in files if f.get('name')]
                if paths:
                    self._storage.from_(self.PROTOCOLS_BUCKET).remove(paths)

        await asyncio.to_thread(_delete)
        logger.info(f"Deleted user pack files at: {storage_prefix}")


# ─── Local Filesystem Fallback ───────────────────────────────

class LocalStorage:
    """Local filesystem storage for development. Same interface as StorageClient."""

    PROTOCOLS_BUCKET = "protocols"
    ASSETS_BUCKET = "assets"
    EXPORTS_BUCKET = "exports"
    PROFILES_BUCKET = "profiles"

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir / "storage"
        # Create bucket directories
        for bucket in (self.PROTOCOLS_BUCKET, self.ASSETS_BUCKET, self.EXPORTS_BUCKET, self.PROFILES_BUCKET):
            (self.base_dir / bucket).mkdir(parents=True, exist_ok=True)
        logger.info(f"Local storage initialized at {self.base_dir}")

    def _bucket_path(self, bucket: str) -> Path:
        return self.base_dir / bucket

    @staticmethod
    def _safe_filename(filename: str) -> str:
        """Validate filename to prevent path traversal attacks."""
        import os
        # Strip directory components — only allow bare filenames
        basename = os.path.basename(filename)
        if not basename or basename.startswith(".") or ".." in basename:
            raise ValueError(f"Invalid filename: {filename!r}")
        return basename

    def _file_url(self, bucket: str, filename: str) -> str:
        """Return a file:// URL for local files."""
        return f"file://{self._bucket_path(bucket) / filename}"

    # ─── Protocols ───────────────────────────────────────────

    async def upload_protocol(self, filename: str, content: str) -> str:
        """Write a protocol file to local storage."""
        filename = self._safe_filename(filename)
        path = self._bucket_path(self.PROTOCOLS_BUCKET) / filename
        await asyncio.to_thread(path.write_text, content, "utf-8")
        logger.info(f"Local: saved protocol {filename}")
        return self._file_url(self.PROTOCOLS_BUCKET, filename)

    async def download_protocol(self, filename: str) -> str:
        """Read a protocol file from local storage."""
        filename = self._safe_filename(filename)
        path = self._bucket_path(self.PROTOCOLS_BUCKET) / filename
        content = await asyncio.to_thread(path.read_text, "utf-8")
        logger.debug(f"Local: read protocol {filename}")
        return content

    async def list_protocols(self) -> list[dict]:
        """List all protocol files in local storage."""
        bucket_dir = self._bucket_path(self.PROTOCOLS_BUCKET)

        def _list():
            results = []
            for f in sorted(bucket_dir.iterdir()):
                if f.is_file():
                    stat = f.stat()
                    results.append({
                        "name": f.name,
                        "size": stat.st_size,
                        "updated": time.strftime(
                            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat.st_mtime)
                        ),
                    })
            return results

        return await asyncio.to_thread(_list)

    # ─── Assets ──────────────────────────────────────────────

    async def upload_asset(self, filename: str, data: bytes, content_type: str) -> str:
        """Write a binary asset to local storage."""
        filename = self._safe_filename(filename)
        path = self._bucket_path(self.ASSETS_BUCKET) / filename
        await asyncio.to_thread(path.write_bytes, data)
        logger.info(f"Local: saved asset {filename} ({content_type})")
        return self._file_url(self.ASSETS_BUCKET, filename)

    async def upload_profile_image(self, filename: str, data: bytes, content_type: str) -> str:
        """Write a profile image to local storage (profiles bucket)."""
        path = self._bucket_path(self.PROFILES_BUCKET) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)
        logger.info(f"Local: saved profile image {filename} ({content_type})")
        return self._file_url(self.PROFILES_BUCKET, filename)

    # ─── Signed URLs ─────────────────────────────────────────

    async def get_signed_url(self, bucket: str, path: str, expires_in: int = 3600) -> str:
        """Return a local file URL (no signing needed in dev)."""
        return self._file_url(bucket, path)

    # ─── Exports ─────────────────────────────────────────────

    async def export_session(self, session_id: str, data: dict) -> str:
        """Export session state as JSON to local storage."""
        filename = f"{session_id}.json"
        path = self._bucket_path(self.EXPORTS_BUCKET) / filename
        payload = json.dumps(data, indent=2, default=str)
        await asyncio.to_thread(path.write_text, payload, "utf-8")
        logger.info(f"Local: exported session {session_id}")
        return self._file_url(self.EXPORTS_BUCKET, filename)

    # ─── User Packs ───────────────────────────────────────────

    USER_PACKS_PREFIX = "user-packs"

    async def upload_user_pack_file(
        self, owner_id: str, pack_id: str, filename: str, content: str
    ) -> str:
        """Write a user pack protocol file to local scoped storage."""
        path = (
            self._bucket_path(self.PROTOCOLS_BUCKET)
            / self.USER_PACKS_PREFIX / owner_id / pack_id / filename
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_text, content, "utf-8")
        logger.info(f"Local: saved user pack file {path}")
        return str(path)

    async def download_user_pack_file(
        self, storage_prefix: str, filename: str
    ) -> str:
        """Read a single protocol file from local user pack storage."""
        path = self._bucket_path(self.PROTOCOLS_BUCKET) / storage_prefix / filename
        content = await asyncio.to_thread(path.read_text, "utf-8")
        return content

    async def delete_user_pack_files(self, storage_prefix: str) -> None:
        """Delete all files under a local user pack storage prefix."""
        import shutil
        path = self._bucket_path(self.PROTOCOLS_BUCKET) / storage_prefix
        if path.exists():
            await asyncio.to_thread(shutil.rmtree, str(path))
        logger.info(f"Local: deleted user pack files at {path}")


# ─── Factory ─────────────────────────────────────────────────

def create_storage() -> Union[StorageClient, LocalStorage]:
    """Factory: use Supabase Storage if configured, else local filesystem."""
    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        return StorageClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    logger.warning("Supabase not configured — falling back to local file storage (dev only)")
    return LocalStorage(BASE_DIR)


# ─── Storage Endpoint Registration ───────────────────────────

def register_storage_endpoints(app, storage) -> None:
    """Register /storage/ endpoints on the FastAPI app."""
    from dataclasses import asdict
    from fastapi import Depends, HTTPException
    from auth import require_auth, require_role

    @app.get("/storage/protocols", dependencies=[Depends(require_auth)])
    async def storage_list_protocols():
        """List all protocol files in cloud/local storage."""
        files = await storage.list_protocols()
        return {"bucket": "protocols", "files": files}

    @app.post("/storage/protocols/sync-up", dependencies=[Depends(require_role("admin"))])
    async def storage_sync_up():
        """Push local protocol .md files to storage. Requires admin role."""
        from config import PROTOCOL_DIR as pdir
        if not pdir.exists():
            raise HTTPException(404, "Protocol directory not found")
        uploaded = []
        for f in pdir.glob("*.md"):
            content = f.read_text(encoding="utf-8")
            url = await storage.upload_protocol(f.name, content)
            uploaded.append({"filename": f.name, "url": url})
        return {"uploaded": len(uploaded), "files": uploaded}

    @app.post("/storage/protocols/sync-down", dependencies=[Depends(require_role("admin"))])
    async def storage_sync_down():
        """Pull protocol files from storage to local directory. Requires admin role."""
        from config import PROTOCOL_DIR as pdir
        pdir.mkdir(parents=True, exist_ok=True)
        files = await storage.list_protocols()
        downloaded = []
        for f in files:
            content = await storage.download_protocol(f["name"])
            (pdir / f["name"]).write_text(content, encoding="utf-8")
            downloaded.append(f["name"])
        return {"downloaded": len(downloaded), "files": downloaded}

    @app.post("/storage/export/{session_id}", dependencies=[Depends(require_auth)])
    async def storage_export_session(session_id: str):
        """Export a session's state to storage."""
        # Import here to avoid circular import at module level
        from state import SessionState
        # The caller (app.py) will pass sessions dict — for now use a simple approach
        url = await storage.export_session(session_id, {"session_id": session_id, "exported_at": time.time()})
        return {"session_id": session_id, "url": url}
