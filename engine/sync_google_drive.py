"""
Google Drive Sync for TMOS13 Vault.

OAuth connect → select folders → delta pull new/modified files.

Uses Google Drive API v3:
- OAuth 2.0 for authorization
- Files.list for folder contents
- Files.get for downloading

Singleton: init_google_drive_sync(vault, supabase) → get_google_drive_sync()
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional
import logging
import urllib.parse

logger = logging.getLogger("tmos13.sync.google_drive")

# Google OAuth endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_DRIVE_API = "https://www.googleapis.com/drive/v3"
GOOGLE_SCOPES = "https://www.googleapis.com/auth/drive.readonly"


@dataclass
class SyncConnection:
    id: str = ""
    owner_id: str = ""
    provider: str = ""
    status: str = "connected"
    watched_folders: list[dict] = field(default_factory=list)
    last_sync_at: Optional[str] = None
    files_synced: int = 0
    storage_used_bytes: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict) -> "SyncConnection":
        return cls(
            id=str(row["id"]),
            owner_id=str(row["owner_id"]),
            provider=row["provider"],
            status=row.get("status", "connected"),
            watched_folders=row.get("watched_folders") or [],
            last_sync_at=row.get("last_sync_at"),
            files_synced=row.get("files_synced", 0),
            storage_used_bytes=row.get("storage_used_bytes", 0),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )


class GoogleDriveSyncService:
    """
    Delta sync from Google Drive.
    OAuth connect → watch folders → pull new/modified files to Vault.
    """

    def __init__(self, vault_service, supabase_client):
        self.vault = vault_service
        self._db = supabase_client
        self._table = "vault_sync_connections"

        try:
            from config import _env
            self.client_id = _env("GOOGLE_DRIVE_CLIENT_ID", "TMOS13_GOOGLE_DRIVE_CLIENT_ID", "")
            self.client_secret = _env("GOOGLE_DRIVE_CLIENT_SECRET", "TMOS13_GOOGLE_DRIVE_CLIENT_SECRET", "")
            self.redirect_uri = _env(
                "GOOGLE_DRIVE_REDIRECT_URI", "TMOS13_GOOGLE_DRIVE_REDIRECT_URI",
                "https://tmos13.ai/api/vault/sync/callback",
            )
        except ImportError:
            self.client_id = ""
            self.client_secret = ""
            self.redirect_uri = ""

        logger.info("GoogleDriveSyncService initialized")

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    async def initiate_oauth(self, owner_id: str) -> str:
        """Generate OAuth URL for Google Drive connection."""
        if not self.client_id:
            raise RuntimeError("Google Drive OAuth not configured (missing client ID)")

        state = urllib.parse.quote(owner_id)
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": GOOGLE_SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"

    async def handle_callback(self, code: str, state: str) -> SyncConnection:
        """Exchange auth code for tokens, create/update sync connection."""
        import httpx

        owner_id = urllib.parse.unquote(state)

        async with httpx.AsyncClient() as client:
            resp = await client.post(GOOGLE_TOKEN_URL, data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri,
            })
            resp.raise_for_status()
            tokens = resp.json()

        row = {
            "owner_id": owner_id,
            "provider": "google_drive",
            "status": "connected",
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token"),
            "token_expires_at": datetime.now(timezone.utc).isoformat(),
            "scopes": GOOGLE_SCOPES.split(" "),
        }

        # Upsert: check if connection exists
        existing = (
            self._db.table(self._table)
            .select("id")
            .eq("owner_id", owner_id)
            .eq("provider", "google_drive")
            .limit(1)
            .execute()
        )
        if existing.data:
            result = (
                self._db.table(self._table)
                .update(row)
                .eq("id", existing.data[0]["id"])
                .execute()
            )
        else:
            result = self._db.table(self._table).insert(row).execute()

        return SyncConnection.from_row(result.data[0])

    async def get_connections(self, owner_id: str) -> list[SyncConnection]:
        """Get all sync connections for an owner."""
        result = (
            self._db.table(self._table)
            .select("*")
            .eq("owner_id", owner_id)
            .execute()
        )
        return [SyncConnection.from_row(row) for row in result.data]

    async def set_watched_folders(self, connection_id: str, folders: list[dict]) -> SyncConnection:
        """Configure which Drive folders to sync."""
        result = (
            self._db.table(self._table)
            .update({
                "watched_folders": folders,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("id", connection_id)
            .execute()
        )
        if not result.data:
            raise ValueError(f"Connection not found: {connection_id}")
        return SyncConnection.from_row(result.data[0])

    async def sync(self, connection_id: str) -> dict:
        """Delta sync: list files in watched folders, pull new/modified."""
        import httpx

        conn_result = (
            self._db.table(self._table)
            .select("*")
            .eq("id", connection_id)
            .execute()
        )
        if not conn_result.data:
            raise ValueError(f"Connection not found: {connection_id}")

        conn_row = conn_result.data[0]
        access_token = conn_row["access_token"]
        owner_id = conn_row["owner_id"]
        watched_folders = conn_row.get("watched_folders") or []

        if not watched_folders:
            return {"synced": 0, "errors": 0, "skipped": 0}

        synced = 0
        errors = 0
        skipped = 0

        async with httpx.AsyncClient() as client:
            for folder in watched_folders:
                folder_id = folder.get("id")
                if not folder_id:
                    continue

                try:
                    resp = await client.get(
                        f"{GOOGLE_DRIVE_API}/files",
                        params={
                            "q": f"'{folder_id}' in parents and trashed=false",
                            "fields": "files(id,name,mimeType,size,modifiedTime)",
                            "pageSize": 100,
                        },
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                    resp.raise_for_status()
                    files = resp.json().get("files", [])

                    for file_info in files:
                        try:
                            # Skip Google-native formats
                            if file_info.get("mimeType", "").startswith("application/vnd.google-apps."):
                                skipped += 1
                                continue

                            dl_resp = await client.get(
                                f"{GOOGLE_DRIVE_API}/files/{file_info['id']}",
                                params={"alt": "media"},
                                headers={"Authorization": f"Bearer {access_token}"},
                            )
                            dl_resp.raise_for_status()
                            file_data = dl_resp.content

                            storage_path = f"vault/{owner_id}/gdrive/{file_info['id']}/{file_info['name']}"

                            await self.vault.register_synced(
                                owner_id=owner_id,
                                filename=file_info["name"],
                                storage_path=storage_path,
                                source="google_drive",
                                source_id=file_info["id"],
                                source_path=f"{folder.get('path', '')}/{file_info['name']}",
                                size_bytes=int(file_info.get("size", 0)),
                                mime_type=file_info.get("mimeType"),
                                sync_source_modified_at=file_info.get("modifiedTime"),
                                file_data=file_data,
                            )
                            synced += 1
                        except Exception as e:
                            logger.warning(f"Failed to sync file {file_info.get('name')}: {e}")
                            errors += 1

                except Exception as e:
                    logger.warning(f"Failed to list folder {folder_id}: {e}")
                    errors += 1

        # Update connection metadata
        self._db.table(self._table).update({
            "last_sync_at": datetime.now(timezone.utc).isoformat(),
            "files_synced": (conn_row.get("files_synced", 0) + synced),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", connection_id).execute()

        logger.info(f"Google Drive sync complete: {synced} synced, {errors} errors, {skipped} skipped")
        return {"synced": synced, "errors": errors, "skipped": skipped}

    async def disconnect(self, connection_id: str) -> dict:
        """Remove connection + all synced files from that source."""
        conn_result = (
            self._db.table(self._table)
            .select("owner_id")
            .eq("id", connection_id)
            .execute()
        )
        if not conn_result.data:
            raise ValueError(f"Connection not found: {connection_id}")

        owner_id = conn_result.data[0]["owner_id"]

        deleted = (
            self._db.table("vault_items")
            .delete()
            .eq("owner_id", owner_id)
            .eq("source", "google_drive")
            .execute()
        )
        files_removed = len(deleted.data) if deleted.data else 0

        self._db.table(self._table).delete().eq("id", connection_id).execute()

        logger.info(f"Google Drive disconnected: {files_removed} files removed")
        return {"disconnected": True, "files_removed": files_removed}


# ── Singleton ───────────────────────────────────────────

_gdrive_sync: GoogleDriveSyncService | None = None


def init_google_drive_sync(vault_service, supabase_client) -> GoogleDriveSyncService:
    global _gdrive_sync
    _gdrive_sync = GoogleDriveSyncService(vault_service, supabase_client)
    return _gdrive_sync


def get_google_drive_sync() -> GoogleDriveSyncService:
    if _gdrive_sync is None:
        raise RuntimeError("GoogleDriveSyncService not initialized.")
    return _gdrive_sync
