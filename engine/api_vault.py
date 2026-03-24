"""
Vault REST API.

Endpoints:
  GET    /api/vault                  — List items with filters
  GET    /api/vault/stats            — Aggregate stats
  GET    /api/vault/:id              — Get single item
  GET    /api/vault/:id/download     — Download file
  POST   /api/vault/upload           — Upload file (multipart)
  DELETE /api/vault/:id              — Delete (upload/synced only)
  GET    /api/vault/sync             — List sync connections
  POST   /api/vault/sync/connect     — Initiate OAuth
  GET    /api/vault/sync/callback    — OAuth callback
  PUT    /api/vault/sync/:id/folders — Configure watched folders
  POST   /api/vault/sync/:id/trigger — Force sync
  DELETE /api/vault/sync/:id         — Disconnect

Registration: register_vault_endpoints(app, vault_service, gdrive_sync)
"""
import logging
from typing import Optional

from fastapi import Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel

from auth import require_auth, UserProfile
from config import TMOS13_OWNER_ID
from errors import APIError, ErrorCode

logger = logging.getLogger("tmos13.vault.api")


# ── Pydantic Models ──────────────────────────────────────

class VaultListResponse(BaseModel):
    items: list[dict]
    total: int
    storage_used_bytes: int
    by_tier: list[dict]


class VaultStatsResponse(BaseModel):
    total_items: int
    storage_used_bytes: int
    by_tier: list[dict]
    by_department: list[dict]
    rag_indexed: int
    sync_connections: int


class SyncConnectRequest(BaseModel):
    provider: str = "google_drive"


class SyncFoldersRequest(BaseModel):
    watched_folders: list[dict]


class SyncConnectionsResponse(BaseModel):
    connections: list[dict]
    total_synced_files: int


# ── Registration ─────────────────────────────────────────

def register_vault_endpoints(app, vault_service, gdrive_sync=None) -> None:
    """Register vault endpoints on the FastAPI application."""

    # ── GET /api/vault ─────────────────────────────────

    @app.get("/api/vault", tags=["vault"], response_model=VaultListResponse)
    async def vault_list(
        tier: Optional[str] = None,
        department: Optional[str] = None,
        source: Optional[str] = None,
        search: Optional[str] = None,
        tags: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        user: UserProfile = Depends(require_auth),
    ):
        """List vault items with filters."""
        tag_list = [t.strip() for t in tags.split(",")] if tags else None
        limit = min(limit, 100)

        items, total = await vault_service.list(
            owner_id=user.user_id,
            tier=tier,
            source=source,
            department=department,
            search=search,
            tags=tag_list,
            limit=limit,
            offset=offset,
        )

        # Compute tier breakdown for the response
        by_tier: dict[str, dict] = {}
        storage_used = 0
        for item in items:
            t = item.tier
            if t not in by_tier:
                by_tier[t] = {"tier": t, "count": 0, "bytes": 0}
            by_tier[t]["count"] += 1
            by_tier[t]["bytes"] += item.size_bytes
            storage_used += item.size_bytes

        return VaultListResponse(
            items=[i.to_dict() for i in items],
            total=total,
            storage_used_bytes=storage_used,
            by_tier=list(by_tier.values()),
        )

    # ── GET /api/vault/stats ───────────────────────────

    @app.get("/api/vault/stats", tags=["vault"], response_model=VaultStatsResponse)
    async def vault_stats(user: UserProfile = Depends(require_auth)):
        """Aggregate vault stats for dashboard."""
        return await vault_service.stats(user.user_id)

    # ── GET /api/vault/sync ────────────────────────────

    @app.get("/api/vault/sync", tags=["vault"], response_model=SyncConnectionsResponse)
    async def vault_sync_list(user: UserProfile = Depends(require_auth)):
        """List sync connections."""
        if not gdrive_sync:
            return SyncConnectionsResponse(connections=[], total_synced_files=0)

        connections = await gdrive_sync.get_connections(user.user_id)
        total_synced = sum(c.files_synced for c in connections)
        return SyncConnectionsResponse(
            connections=[c.to_dict() for c in connections],
            total_synced_files=total_synced,
        )

    # ── POST /api/vault/sync/connect ───────────────────

    @app.post("/api/vault/sync/connect", tags=["vault"])
    async def vault_sync_connect(
        req: SyncConnectRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """Initiate OAuth for a sync provider."""
        if req.provider != "google_drive":
            raise APIError(ErrorCode.VALIDATION_ERROR, f"Unsupported provider: {req.provider}", 400)
        if not gdrive_sync or not gdrive_sync.configured:
            raise APIError(ErrorCode.VALIDATION_ERROR, "Google Drive sync not configured", 400)

        auth_url = await gdrive_sync.initiate_oauth(user.user_id)
        return {"auth_url": auth_url}

    # ── GET /api/vault/sync/callback ───────────────────

    @app.get("/api/vault/sync/callback", tags=["vault"])
    async def vault_sync_callback(code: str, state: str):
        """OAuth callback — exchanges code for tokens."""
        if not gdrive_sync:
            raise HTTPException(500, "Google Drive sync not configured")

        try:
            connection = await gdrive_sync.handle_callback(code, state)
            # Redirect to dashboard after successful OAuth
            return RedirectResponse("/dashboard?sync=connected")
        except Exception as e:
            logger.error(f"OAuth callback failed: {e}")
            return RedirectResponse(f"/dashboard?sync=error&message={str(e)}")

    # ── GET /api/vault/:id ─────────────────────────────
    # Registered after /sync routes to avoid path conflict

    @app.get("/api/vault/{item_id}", tags=["vault"])
    async def vault_get(
        item_id: str,
        user: UserProfile = Depends(require_auth),
    ):
        """Get a single vault item."""
        item = await vault_service.get(item_id)
        if not item or item.owner_id != user.user_id:
            raise HTTPException(404, "Vault item not found")
        return item.to_dict()

    # ── GET /api/vault/:id/download ────────────────────

    @app.get("/api/vault/{item_id}/download", tags=["vault"])
    async def vault_download(
        item_id: str,
        user: UserProfile = Depends(require_auth),
    ):
        """Download a vault file."""
        item = await vault_service.get(item_id)
        if not item or item.owner_id != user.user_id:
            raise HTTPException(404, "Vault item not found")

        file_data, mime_type, filename = await vault_service.download(item_id)
        return Response(
            content=file_data,
            media_type=mime_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # ── POST /api/vault/upload ─────────────────────────

    @app.post("/api/vault/upload", tags=["vault"], status_code=201)
    async def vault_upload(
        file: UploadFile = File(...),
        department: Optional[str] = Form(None),
        tags: Optional[str] = Form(None),
        pack_id: Optional[str] = Form(None),
        user: UserProfile = Depends(require_auth),
    ):
        """Upload a file to the vault."""
        file_data = await file.read()
        if not file_data:
            raise APIError(ErrorCode.VALIDATION_ERROR, "File is empty", 400)

        tag_list = [t.strip() for t in tags.split(",")] if tags else None

        item = await vault_service.upload(
            owner_id=user.user_id,
            file_data=file_data,
            filename=file.filename or "unnamed",
            mime_type=file.content_type,
            department=department,
            tags=tag_list,
            pack_id=pack_id,
        )
        return item.to_dict()

    # ── PATCH /api/vault/:id/department ─────────────────

    @app.patch("/api/vault/{item_id}/department", tags=["vault"])
    async def vault_refile(
        item_id: str,
        req: dict,
        user: UserProfile = Depends(require_auth),
    ):
        """Update the department on a vault item (refile)."""
        department = req.get("department")
        if not department:
            raise APIError(ErrorCode.VALIDATION_ERROR, "department is required", 400)
        result = await vault_service.refile(item_id, department)
        if not result:
            raise HTTPException(404, "Vault item not found")
        return {"id": item_id, "department": department}

    # ── DELETE /api/vault/:id ──────────────────────────

    @app.delete("/api/vault/{item_id}", tags=["vault"])
    async def vault_delete(
        item_id: str,
        user: UserProfile = Depends(require_auth),
    ):
        """Delete a vault item. Outputs are immutable."""
        item = await vault_service.get(item_id)
        if not item or item.owner_id != user.user_id:
            raise HTTPException(404, "Vault item not found")

        try:
            await vault_service.delete(item_id)
            return {"deleted": True, "id": item_id}
        except ValueError as e:
            raise APIError(ErrorCode.VALIDATION_ERROR, str(e), 400)

    # ── PUT /api/vault/sync/:id/folders ────────────────

    @app.put("/api/vault/sync/{connection_id}/folders", tags=["vault"])
    async def vault_sync_folders(
        connection_id: str,
        req: SyncFoldersRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """Configure watched folders for a sync connection."""
        if not gdrive_sync:
            raise HTTPException(500, "Sync not configured")

        try:
            conn = await gdrive_sync.set_watched_folders(connection_id, req.watched_folders)
            return conn.to_dict()
        except ValueError as e:
            raise HTTPException(404, str(e))

    # ── POST /api/vault/sync/:id/trigger ───────────────

    @app.post("/api/vault/sync/{connection_id}/trigger", tags=["vault"])
    async def vault_sync_trigger(
        connection_id: str,
        user: UserProfile = Depends(require_auth),
    ):
        """Force a sync for a connection."""
        if not gdrive_sync:
            raise HTTPException(500, "Sync not configured")

        try:
            result = await gdrive_sync.sync(connection_id)
            return result
        except ValueError as e:
            raise HTTPException(404, str(e))

    # ── DELETE /api/vault/sync/:id ─────────────────────

    @app.delete("/api/vault/sync/{connection_id}", tags=["vault"])
    async def vault_sync_disconnect(
        connection_id: str,
        user: UserProfile = Depends(require_auth),
    ):
        """Disconnect a sync connection and remove synced files."""
        if not gdrive_sync:
            raise HTTPException(500, "Sync not configured")

        try:
            result = await gdrive_sync.disconnect(connection_id)
            return result
        except ValueError as e:
            raise HTTPException(404, str(e))
