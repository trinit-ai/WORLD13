"""
Manifest: Append-only event log for TMOS13.

The permanent record. Every significant system event writes an entry here.
Entries are immutable — created once, never modified, never deleted.

Usage:
    manifest = get_manifest_service()
    manifest.log(
        owner_id="uuid",
        event_type="session_started",
        category="session",
        summary="New legal intake session started",
        department="legal",
        pack_id="legal_intake",
        session_id="sess_abc123"
    )

Singleton pattern: init_manifest_service(supabase_client) → get_manifest_service()
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional
import logging
import uuid

from fastapi import HTTPException

logger = logging.getLogger("tmos13.manifest")

# ─── Valid Values ────────────────────────────────────────

VALID_EVENT_TYPES = {
    "session_started",
    "session_resolved",
    "deliverable_produced",
    "contact_captured",
    "alert_triggered",
    "pack_loaded",
    "pack_unloaded",
    "agent_action",
    "normalization_applied",
    "inbox_received",
    "escalation",
    "form_submitted",
    "file_uploaded",
    "file_synced",
    "file_exported",
    "system_event",
    "session_initiated",
    "chain_triggered",
    "ambassador_send",
    "message_promoted",
}

VALID_CATEGORIES = {
    "session",
    "deliverable",
    "contact",
    "alert",
    "pack",
    "agent",
    "normalization",
    "inbox",
    "vault",
    "system",
    "desk",
}

VALID_IMPORTANCE = {"low", "normal", "high", "critical"}


def extract_entity_refs(summary: str, detail: dict | None = None, **kwargs) -> list[dict]:
    """
    Extract lightweight entity references from manifest entry text.

    Returns list of {type, name} dicts. Types: decision, service, person, system, event.
    Heuristic extraction — no LLM call. Designed for speed at write time.
    """
    refs = []
    text = (summary or "").lower()

    # Pull structured refs from detail dict if provided
    if detail and isinstance(detail, dict):
        for key in ("service", "system", "component", "module"):
            val = detail.get(key)
            if val and isinstance(val, str):
                refs.append({"type": "service", "name": val})
        for key in ("person", "contact", "user", "visitor"):
            val = detail.get(key)
            if val and isinstance(val, str):
                refs.append({"type": "person", "name": val})
        for key in ("decision", "resolution", "outcome"):
            val = detail.get(key)
            if val and isinstance(val, str):
                refs.append({"type": "decision", "name": val[:80]})

    # Pull from kwargs (pack_id, department, etc.)
    pack_id = kwargs.get("pack_id")
    if pack_id:
        refs.append({"type": "system", "name": pack_id})
    department = kwargs.get("department")
    if department:
        refs.append({"type": "system", "name": department})
    event_type = kwargs.get("event_type")
    if event_type:
        refs.append({"type": "event", "name": event_type})

    # Deduplicate by (type, name)
    seen = set()
    unique = []
    for ref in refs:
        key = (ref["type"], ref["name"])
        if key not in seen:
            seen.add(key)
            unique.append(ref)
    return unique


# ─── Dataclass ───────────────────────────────────────────

@dataclass
class ManifestEntry:
    id: str
    owner_id: str
    event_type: str
    category: str
    summary: str
    detail: dict = field(default_factory=dict)
    department: Optional[str] = None
    pack_id: Optional[str] = None
    session_id: Optional[str] = None
    contact_id: Optional[str] = None
    agent_name: Optional[str] = None
    tags: list = field(default_factory=list)
    importance: str = "normal"
    created_at: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize for API responses."""
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict) -> "ManifestEntry":
        """Create from Supabase row dict."""
        return cls(
            id=str(row["id"]),
            owner_id=str(row["owner_id"]),
            event_type=row["event_type"],
            category=row["category"],
            summary=row["summary"],
            detail=row.get("detail") or {},
            department=row.get("department"),
            pack_id=row.get("pack_id"),
            session_id=row.get("session_id"),
            contact_id=str(row["contact_id"]) if row.get("contact_id") else None,
            agent_name=row.get("agent_name"),
            tags=row.get("tags") or [],
            importance=row.get("importance", "normal"),
            created_at=row.get("created_at"),
        )


# ─── Service ────────────────────────────────────────────

class ManifestService:
    """
    Append-only event log. Write from anywhere. Read from dashboard.

    IMMUTABILITY CONTRACT:
    - log() creates entries
    - query() and get() read entries
    - There is NO update method
    - There is NO delete method
    - This is intentional and must not be changed
    """

    def __init__(self, supabase_client):
        self._db = supabase_client
        self._table = "manifest_entries"
        logger.info("ManifestService initialized")

    def log(
        self,
        owner_id: str,
        event_type: str,
        category: str,
        summary: str,
        detail: dict | None = None,
        department: str | None = None,
        pack_id: str | None = None,
        session_id: str | None = None,
        contact_id: str | None = None,
        agent_name: str | None = None,
        tags: list[str] | None = None,
        importance: str = "normal",
    ) -> ManifestEntry:
        """
        Append one entry to the manifest. Returns the created ManifestEntry.

        Raises:
            ValueError: If event_type, category, or importance is invalid
            ValueError: If owner_id or summary is empty
        """
        # Check feature flag
        try:
            from config import TMOS13_MANIFEST_ENABLED
            if not TMOS13_MANIFEST_ENABLED:
                # Return stub entry without persisting
                return ManifestEntry(
                    id=str(uuid.uuid4()),
                    owner_id=owner_id,
                    event_type=event_type,
                    category=category,
                    summary=summary,
                    detail=detail or {},
                    department=department,
                    pack_id=pack_id,
                    session_id=session_id,
                    contact_id=contact_id,
                    agent_name=agent_name,
                    tags=tags or [],
                    importance=importance,
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
        except ImportError:
            pass

        # Validate required fields
        if not owner_id:
            raise ValueError("owner_id is required")
        if not summary:
            raise ValueError("summary is required")

        # Validate enum values
        if event_type not in VALID_EVENT_TYPES:
            raise ValueError(f"Invalid event_type: {event_type}. Must be one of {VALID_EVENT_TYPES}")
        if category not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category: {category}. Must be one of {VALID_CATEGORIES}")
        if importance not in VALID_IMPORTANCE:
            raise ValueError(f"Invalid importance: {importance}. Must be one of {VALID_IMPORTANCE}")

        now = datetime.now(timezone.utc).isoformat()
        entity_refs = extract_entity_refs(
            summary, detail,
            pack_id=pack_id, department=department, event_type=event_type,
        )
        row = {
            "id": str(uuid.uuid4()),
            "owner_id": owner_id,
            "event_type": event_type,
            "category": category,
            "summary": summary,
            "detail": detail or {},
            "department": department,
            "pack_id": pack_id,
            "session_id": session_id,
            "contact_id": contact_id,
            "agent_name": agent_name,
            "tags": tags or [],
            "importance": importance,
            "entity_refs": entity_refs,
            "created_at": now,
        }

        result = self._db.table(self._table).insert(row).execute()
        entry = ManifestEntry.from_row(result.data[0])
        logger.info(f"Manifest: [{category}] {event_type} — {summary}")
        return entry

    def query(
        self,
        owner_id: str,
        category: str | None = None,
        event_type: str | None = None,
        department: str | None = None,
        session_id: str | None = None,
        contact_id: str | None = None,
        tags: list[str] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        importance: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ManifestEntry], int]:
        """
        Query entries with filters. Returns (entries, total_count).
        Results are ordered by created_at DESC (newest first).
        """
        query = self._db.table(self._table).select("*", count="exact")
        query = query.eq("owner_id", owner_id)

        if category:
            query = query.eq("category", category)
        if event_type:
            query = query.eq("event_type", event_type)
        if department:
            query = query.eq("department", department)
        if session_id:
            query = query.eq("session_id", session_id)
        if contact_id:
            query = query.eq("contact_id", contact_id)
        if importance:
            query = query.eq("importance", importance)
        if tags:
            for tag in tags:
                query = query.contains("tags", [tag])
        if since:
            query = query.gte("created_at", since.isoformat())
        if until:
            query = query.lte("created_at", until.isoformat())

        query = query.order("created_at", desc=True)
        query = query.range(offset, offset + limit - 1)

        result = query.execute()
        entries = [ManifestEntry.from_row(row) for row in result.data]
        total = result.count if hasattr(result, "count") and result.count is not None else len(entries)

        return entries, total

    def get(self, entry_id: str) -> ManifestEntry | None:
        """Get single entry by ID."""
        result = (
            self._db.table(self._table)
            .select("*")
            .eq("id", entry_id)
            .execute()
        )
        if not result.data:
            return None
        return ManifestEntry.from_row(result.data[0])

    def stats(self, owner_id: str) -> dict:
        """
        Aggregate stats for dashboard display.

        Returns:
            {
                total_entries: int,
                entries_today: int,
                by_category: [{ category, count }],
                by_department: [{ department, count }],
                latest_entry_at: str | None
            }
        """
        # All entries for this owner
        all_result = (
            self._db.table(self._table)
            .select("*")
            .eq("owner_id", owner_id)
            .order("created_at", desc=True)
            .execute()
        )
        all_entries = all_result.data or []
        total_entries = len(all_entries)

        # Today's count
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat()
        entries_today = sum(
            1 for e in all_entries
            if e.get("created_at", "") >= today_start
        )

        # Latest entry
        latest_entry_at = all_entries[0]["created_at"] if all_entries else None

        # Category breakdown
        cat_counts: dict[str, int] = {}
        for row in all_entries:
            c = row["category"]
            cat_counts[c] = cat_counts.get(c, 0) + 1
        by_category = [
            {"category": k, "count": v}
            for k, v in sorted(cat_counts.items(), key=lambda x: -x[1])
        ]

        # Department breakdown (skip None departments)
        dept_counts: dict[str, int] = {}
        for row in all_entries:
            d = row.get("department")
            if d:
                dept_counts[d] = dept_counts.get(d, 0) + 1
        by_department = [
            {"department": k, "count": v}
            for k, v in sorted(dept_counts.items(), key=lambda x: -x[1])
        ]

        return {
            "total_entries": total_entries,
            "entries_today": entries_today,
            "by_category": by_category,
            "by_department": by_department,
            "latest_entry_at": latest_entry_at,
        }


# ─── Singleton ───────────────────────────────────────────

_manifest_service: ManifestService | None = None


def init_manifest_service(supabase_client) -> ManifestService:
    """Initialize the ManifestService singleton. Call once in app lifespan."""
    global _manifest_service
    _manifest_service = ManifestService(supabase_client)
    return _manifest_service


def get_manifest_service() -> ManifestService:
    """Get the ManifestService singleton."""
    if _manifest_service is None:
        raise HTTPException(503, "ManifestService not initialized")
    return _manifest_service
