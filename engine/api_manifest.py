"""
TMOS13 Manifest — API Endpoints

Append-only event log. The permanent record.

GET  /api/manifest           — Query entries with filters
GET  /api/manifest/stats     — Aggregate stats for dashboard
GET  /api/manifest/{entry_id} — Get single entry
POST /api/manifest           — Log a new entry

Registered by `register_manifest_endpoints(app, manifest_service)`.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from auth import require_auth, UserProfile
from config import TMOS13_OWNER_ID
from manifest import ManifestService

logger = logging.getLogger("tmos13.manifest.api")


# ─── Pydantic Request/Response Models ──────────────────

class ManifestLogRequest(BaseModel):
    event_type: str
    category: str
    summary: str
    detail: Optional[dict] = None
    department: Optional[str] = None
    pack_id: Optional[str] = None
    session_id: Optional[str] = None
    contact_id: Optional[str] = None
    agent_name: Optional[str] = None
    tags: Optional[list[str]] = None
    importance: str = "normal"


class ManifestEntryResponse(BaseModel):
    id: str
    owner_id: str
    event_type: str
    category: str
    summary: str
    detail: dict
    department: Optional[str] = None
    pack_id: Optional[str] = None
    session_id: Optional[str] = None
    contact_id: Optional[str] = None
    agent_name: Optional[str] = None
    tags: list[str]
    importance: str
    created_at: Optional[str] = None


class ManifestQueryResponse(BaseModel):
    entries: list[dict]
    total: int
    limit: int
    offset: int


class ManifestStatsResponse(BaseModel):
    total_entries: int
    entries_today: int
    by_category: list[dict]
    by_department: list[dict]
    latest_entry_at: Optional[str] = None


# ─── Registration ──────────────────────────────────────

def register_manifest_endpoints(app, manifest_service: ManifestService):
    """Register all /api/manifest/* endpoints on the FastAPI app."""

    @app.get(
        "/api/manifest",
        response_model=ManifestQueryResponse,
        tags=["manifest"],
        summary="Query manifest entries with filters",
    )
    async def query_manifest(
        category: Optional[str] = None,
        event_type: Optional[str] = None,
        department: Optional[str] = None,
        session_id: Optional[str] = None,
        contact_id: Optional[str] = None,
        tags: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        importance: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        user: UserProfile = Depends(require_auth),
    ):
        """
        Query the manifest log with optional filters.
        Results are ordered newest-first.
        """
        # Parse tags from comma-separated string
        tag_list = [t.strip() for t in tags.split(",")] if tags else None

        # Parse datetime strings
        since_dt = datetime.fromisoformat(since) if since else None
        until_dt = datetime.fromisoformat(until) if until else None

        entries, total = manifest_service.query(
            owner_id=TMOS13_OWNER_ID,
            category=category,
            event_type=event_type,
            department=department,
            session_id=session_id,
            contact_id=contact_id,
            tags=tag_list,
            since=since_dt,
            until=until_dt,
            importance=importance,
            limit=limit,
            offset=offset,
        )

        return ManifestQueryResponse(
            entries=[e.to_dict() for e in entries],
            total=total,
            limit=limit,
            offset=offset,
        )

    @app.get(
        "/api/manifest/stats",
        response_model=ManifestStatsResponse,
        tags=["manifest"],
        summary="Aggregate manifest statistics",
    )
    async def manifest_stats(user: UserProfile = Depends(require_auth)):
        """Dashboard-ready aggregate stats for the authenticated user's manifest."""
        stats = manifest_service.stats(TMOS13_OWNER_ID)
        return ManifestStatsResponse(**stats)

    @app.get(
        "/api/manifest/{entry_id}",
        response_model=ManifestEntryResponse,
        tags=["manifest"],
        summary="Get a single manifest entry",
    )
    async def get_manifest_entry(
        entry_id: str,
        user: UserProfile = Depends(require_auth),
    ):
        """Retrieve a single manifest entry by ID. Owner-scoped."""
        entry = manifest_service.get(entry_id)
        if not entry:
            raise HTTPException(404, f"Manifest entry not found: {entry_id}")
        if entry.owner_id != TMOS13_OWNER_ID and entry.owner_id != user.user_id:
            raise HTTPException(404, f"Manifest entry not found: {entry_id}")
        return ManifestEntryResponse(**entry.to_dict())

    @app.post(
        "/api/manifest",
        response_model=ManifestEntryResponse,
        tags=["manifest"],
        summary="Log a new manifest entry",
    )
    async def log_manifest_entry(
        req: ManifestLogRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """
        Append a new entry to the manifest. owner_id is set from the JWT.
        Entries are immutable — once created, they cannot be modified or deleted.
        """
        entry = manifest_service.log(
            owner_id=user.user_id,
            event_type=req.event_type,
            category=req.category,
            summary=req.summary,
            detail=req.detail,
            department=req.department,
            pack_id=req.pack_id,
            session_id=req.session_id,
            contact_id=req.contact_id,
            agent_name=req.agent_name,
            tags=req.tags,
            importance=req.importance,
        )
        return ManifestEntryResponse(**entry.to_dict())
