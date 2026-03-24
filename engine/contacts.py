"""
Contacts: Unified entity directory for TMOS13.

OS-level entity graph. One canonical record per person/company/entity.
Every interaction is recorded as a touchpoint. Aggregated metrics are
denormalized on the contact record for fast dashboard queries.

Core operation: resolve_or_create(email) — finds existing or creates new.
Other services call this when they encounter an entity.

Singleton pattern: init_contacts_service(supabase_client, manifest_service) → get_contacts_service()
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException

logger = logging.getLogger("tmos13.contacts")


# ── Valid values ────────────────────────────────────────

VALID_ENTITY_TYPES = {"lead", "client", "team", "vendor", "other"}
VALID_STATUSES = {"new", "active", "inactive", "archived"}
VALID_TOUCHPOINT_TYPES = {
    "session", "email", "form", "deliverable", "invoice",
    "feed_event", "manifest_entry", "note", "ambassador_exchange",
}
VALID_SOURCES = {"session", "ambassador", "form", "manual", "inbox", "import"}


# ── Dataclasses ─────────────────────────────────────────

@dataclass
class Contact:
    id: str
    owner_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    organization: Optional[str] = None
    entity_type: str = "lead"
    status: str = "new"
    department: Optional[str] = None
    total_sessions: int = 0
    total_manifest_entries: int = 0
    total_feed_events: int = 0
    total_deliverables: int = 0
    total_emails: int = 0
    total_invoices: int = 0
    lifetime_value_usd: float = 0.0
    tags: list[str] = field(default_factory=list)
    custom_fields: dict = field(default_factory=dict)
    assigned_agent: Optional[str] = None
    source: Optional[str] = None
    correlation_id: Optional[str] = None
    session_id: Optional[str] = None
    match_status: Optional[str] = None
    first_touch_at: Optional[str] = None
    last_touch_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict) -> "Contact":
        return cls(
            id=str(row["id"]),
            owner_id=str(row["owner_id"]),
            name=row.get("name"),
            email=row.get("email"),
            phone=row.get("phone"),
            organization=row.get("organization"),
            entity_type=row.get("entity_type", "lead"),
            status=row.get("status", "new"),
            department=row.get("department"),
            total_sessions=row.get("total_sessions", 0),
            total_manifest_entries=row.get("total_manifest_entries", 0),
            total_feed_events=row.get("total_feed_events", 0),
            total_deliverables=row.get("total_deliverables", 0),
            total_emails=row.get("total_emails", 0),
            total_invoices=row.get("total_invoices", 0),
            lifetime_value_usd=float(row.get("lifetime_value_usd", 0)),
            tags=row.get("tags") or [],
            custom_fields=row.get("custom_fields") or {},
            assigned_agent=row.get("assigned_agent"),
            source=row.get("source"),
            correlation_id=row.get("correlation_id"),
            session_id=row.get("session_id"),
            match_status=row.get("match_status"),
            first_touch_at=row.get("first_touch_at"),
            last_touch_at=row.get("last_touch_at"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )


@dataclass
class ContactTouchpoint:
    id: str
    contact_id: str
    touchpoint_type: str
    source_id: Optional[str] = None
    summary: str = ""
    detail: dict = field(default_factory=dict)
    created_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict) -> "ContactTouchpoint":
        return cls(
            id=str(row["id"]),
            contact_id=str(row["contact_id"]),
            touchpoint_type=row["touchpoint_type"],
            source_id=row.get("source_id"),
            summary=row.get("summary", ""),
            detail=row.get("detail") or {},
            created_at=row.get("created_at"),
        )


# ── Service ─────────────────────────────────────────────

class ContactsService:
    """
    Unified entity directory. Resolves identities across all surfaces.
    Other services call resolve_or_create() when they encounter an entity.
    """

    def __init__(self, supabase_client, manifest_service=None):
        self._db = supabase_client
        self._manifest = manifest_service
        self._contacts_table = "contacts"
        self._touchpoints_table = "contact_touchpoints"
        logger.info("ContactsService initialized")

    # ── Core: Entity Resolution ─────────────────────────

    def resolve_or_create(
        self,
        owner_id: str,
        email: Optional[str] = None,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        organization: Optional[str] = None,
        source: str = "session",
        department: Optional[str] = None,
        correlation_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Contact:
        """
        Find existing contact by email, or create a new one.

        Resolution priority:
        1. Match by email (unique per owner)
        2. If no email, reject — email is required for dedup and data quality.

        Manifest logging is NOT automatic. Contacts are promoted to manifest
        explicitly by the deployer (promotion-only philosophy).
        """
        # Email is required — name-only contacts produce junk with no dedup
        if not email:
            raise ValueError("Email is required to create or resolve a contact")

        email_clean = email.lower().strip()
        existing = self._find_by_email(owner_id, email_clean)
        if existing:
            # Enrich: update fields that were previously null
            updates = {}
            if name and not existing.name:
                updates["name"] = name
            if phone and not existing.phone:
                updates["phone"] = phone
            if organization and not existing.organization:
                updates["organization"] = organization
            # Stamp correlation_id / session_id if not already set
            if correlation_id and not getattr(existing, "correlation_id", None):
                updates["correlation_id"] = correlation_id
            if session_id and not getattr(existing, "session_id", None):
                updates["session_id"] = session_id
            if updates:
                return self.update(existing.id, **updates)
            return existing

        # Create new contact
        contact = self.create(
            owner_id=owner_id,
            name=name,
            email=email_clean,
            phone=phone,
            organization=organization,
            source=source,
            department=department,
            correlation_id=correlation_id,
            session_id=session_id,
        )

        return contact

    # ── CRUD ────────────────────────────────────────────

    def create(
        self,
        owner_id: str,
        name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        organization: Optional[str] = None,
        entity_type: str = "lead",
        source: str = "session",
        department: Optional[str] = None,
        tags: Optional[list[str]] = None,
        custom_fields: Optional[dict] = None,
        correlation_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Contact:
        """Create a new contact."""
        if entity_type not in VALID_ENTITY_TYPES:
            raise ValueError(f"Invalid entity_type: {entity_type}")
        if source and source not in VALID_SOURCES:
            raise ValueError(f"Invalid source: {source}")

        now = datetime.now(timezone.utc).isoformat()
        row = {
            "owner_id": owner_id,
            "name": name,
            "email": email,
            "phone": phone,
            "organization": organization,
            "entity_type": entity_type,
            "status": "new",
            "department": department,
            "source": source,
            "tags": tags or [],
            "custom_fields": custom_fields or {},
            "first_touch_at": now,
            "last_touch_at": now,
            "created_at": now,
            "updated_at": now,
        }
        if correlation_id:
            row["correlation_id"] = correlation_id
        if session_id:
            row["session_id"] = session_id

        result = self._db.table(self._contacts_table).insert(row).execute()
        contact = Contact.from_row(result.data[0])
        logger.info(f"Contact created: {contact.id} ({contact.name or contact.email})")
        return contact

    def get(self, contact_id: str) -> Optional[Contact]:
        """Get single contact by ID."""
        result = (
            self._db.table(self._contacts_table)
            .select("*")
            .eq("id", contact_id)
            .execute()
        )
        if not result.data:
            return None
        return Contact.from_row(result.data[0])

    def update(self, contact_id: str, **fields) -> Contact:
        """
        Update contact fields.
        Only updates fields that are explicitly passed.
        Sets updated_at to now.
        """
        if "entity_type" in fields and fields["entity_type"] not in VALID_ENTITY_TYPES:
            raise ValueError(f"Invalid entity_type: {fields['entity_type']}")
        if "status" in fields and fields["status"] not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {fields['status']}")

        fields["updated_at"] = datetime.now(timezone.utc).isoformat()

        result = (
            self._db.table(self._contacts_table)
            .update(fields)
            .eq("id", contact_id)
            .execute()
        )
        if not result.data:
            raise ValueError(f"Contact not found: {contact_id}")
        return Contact.from_row(result.data[0])

    def delete(self, contact_id: str) -> bool:
        """Delete a contact and all its touchpoints."""
        # Delete touchpoints first
        self._db.table(self._touchpoints_table).delete().eq(
            "contact_id", contact_id
        ).execute()
        # Delete contact
        result = (
            self._db.table(self._contacts_table)
            .delete()
            .eq("id", contact_id)
            .execute()
        )
        if not result.data:
            return False
        logger.info(f"Contact deleted: {contact_id}")
        return True

    def list(
        self,
        owner_id: str,
        entity_type: Optional[str] = None,
        status: Optional[str] = None,
        department: Optional[str] = None,
        search: Optional[str] = None,
        tags: Optional[list[str]] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Contact], int]:
        """
        List contacts with filters. Returns (contacts, total_count).
        Results ordered by last_touch_at DESC (most recently active first).
        """
        query = self._db.table(self._contacts_table).select("*", count="exact")
        query = query.eq("owner_id", owner_id)

        if entity_type:
            query = query.eq("entity_type", entity_type)
        if status:
            query = query.eq("status", status)
        if department:
            query = query.eq("department", department)
        if tags:
            query = query.contains("tags", tags)
        if search:
            # PostgREST or_ filter for multi-field text search
            query = query.or_(
                f"name.ilike.%{search}%,"
                f"email.ilike.%{search}%,"
                f"organization.ilike.%{search}%,"
                f"phone.ilike.%{search}%"
            )

        query = query.order("last_touch_at", desc=True)
        query = query.range(offset, offset + limit - 1)

        result = query.execute()
        contacts = [Contact.from_row(row) for row in result.data]
        total = result.count or 0

        return contacts, total

    def search(self, owner_id: str, query: str) -> list[Contact]:
        """Convenience: search by text across name/email/org. Returns up to 20."""
        contacts, _ = self.list(owner_id, search=query, limit=20)
        return contacts

    # ── Touchpoints ─────────────────────────────────────

    def add_touchpoint(
        self,
        contact_id: str,
        touchpoint_type: str,
        summary: str,
        source_id: Optional[str] = None,
        detail: Optional[dict] = None,
    ) -> ContactTouchpoint:
        """
        Record a touchpoint and update aggregated metrics on the contact.
        Increments the appropriate counter and updates last_touch_at.
        """
        if touchpoint_type not in VALID_TOUCHPOINT_TYPES:
            raise ValueError(f"Invalid touchpoint_type: {touchpoint_type}")

        row = {
            "contact_id": contact_id,
            "touchpoint_type": touchpoint_type,
            "source_id": source_id,
            "summary": summary,
            "detail": detail or {},
        }
        result = self._db.table(self._touchpoints_table).insert(row).execute()
        touchpoint = ContactTouchpoint.from_row(result.data[0])

        # Update denormalized counters on contact
        counter_map = {
            "session": "total_sessions",
            "email": "total_emails",
            "ambassador_exchange": "total_emails",
            "deliverable": "total_deliverables",
            "invoice": "total_invoices",
            "manifest_entry": "total_manifest_entries",
            "feed_event": "total_feed_events",
        }
        counter_field = counter_map.get(touchpoint_type)

        contact = self.get(contact_id)
        if contact:
            updates = {"last_touch_at": datetime.now(timezone.utc).isoformat()}
            if counter_field:
                current = getattr(contact, counter_field, 0)
                updates[counter_field] = current + 1
            self.update(contact_id, **updates)

        logger.info(f"Touchpoint added: {touchpoint_type} for contact {contact_id}")
        return touchpoint

    def get_touchpoints(
        self,
        contact_id: str,
        touchpoint_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ContactTouchpoint], int]:
        """Get touchpoints for a contact, ordered newest first."""
        query = (
            self._db.table(self._touchpoints_table)
            .select("*", count="exact")
            .eq("contact_id", contact_id)
        )
        if touchpoint_type:
            query = query.eq("touchpoint_type", touchpoint_type)

        query = query.order("created_at", desc=True)
        query = query.range(offset, offset + limit - 1)

        result = query.execute()
        touchpoints = [ContactTouchpoint.from_row(row) for row in result.data]
        total = result.count or 0
        return touchpoints, total

    # ── Internal helpers ────────────────────────────────

    def _find_by_email(self, owner_id: str, email: str) -> Optional[Contact]:
        """Find contact by email for a given owner."""
        result = (
            self._db.table(self._contacts_table)
            .select("*")
            .eq("owner_id", owner_id)
            .eq("email", email)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        return Contact.from_row(result.data[0])


# ── Singleton ───────────────────────────────────────────

_contacts_service: Optional[ContactsService] = None


def init_contacts_service(supabase_client, manifest_service=None) -> ContactsService:
    """Initialize the ContactsService singleton. Call once in app lifespan."""
    global _contacts_service
    _contacts_service = ContactsService(supabase_client, manifest_service)
    return _contacts_service


def get_contacts_service() -> ContactsService:
    """Get the ContactsService singleton. Raises if not initialized."""
    if _contacts_service is None:
        raise HTTPException(503, "ContactsService not initialized")
    return _contacts_service
