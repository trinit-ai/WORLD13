"""
Contacts REST API.

Endpoints:
  GET    /api/contacts              — List contacts with filters + search
  GET    /api/contacts/:id          — Get single contact with recent touchpoints
  POST   /api/contacts              — Create contact
  PUT    /api/contacts/:id          — Update contact
  GET    /api/contacts/:id/touchpoints — Get touchpoints for contact
  POST   /api/contacts/:id/touchpoints — Add touchpoint
  POST   /api/contacts/resolve      — Entity resolution (find or return null)

Registration: register_contacts_endpoints(app, service)
"""
import logging
from typing import Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from auth import require_auth, UserProfile
from config import TMOS13_OWNER_ID
from contacts import ContactsService

logger = logging.getLogger("tmos13.contacts_api")


# ── Request Models ──────────────────────────────────────

class CreateContactRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    organization: Optional[str] = None
    entity_type: Optional[str] = "lead"
    department: Optional[str] = None
    tags: Optional[list[str]] = None
    custom_fields: Optional[dict] = None


class UpdateContactRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    organization: Optional[str] = None
    entity_type: Optional[str] = None
    status: Optional[str] = None
    department: Optional[str] = None
    tags: Optional[list[str]] = None
    custom_fields: Optional[dict] = None
    assigned_agent: Optional[str] = None


class AddTouchpointRequest(BaseModel):
    touchpoint_type: str
    source_id: Optional[str] = None
    summary: str
    detail: Optional[dict] = None


class ResolveContactRequest(BaseModel):
    email: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None


# ── Response Models ─────────────────────────────────────

class ContactResponse(BaseModel):
    id: str
    owner_id: str
    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    organization: Optional[str]
    entity_type: str
    status: str
    department: Optional[str]
    total_sessions: int
    total_manifest_entries: int
    total_feed_events: int
    total_deliverables: int
    total_emails: int
    total_invoices: int
    lifetime_value_usd: float
    tags: list[str]
    custom_fields: dict
    assigned_agent: Optional[str]
    source: Optional[str]
    first_touch_at: Optional[str]
    last_touch_at: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


class ContactDetailResponse(ContactResponse):
    recent_touchpoints: list[dict] = []


class ContactListResponse(BaseModel):
    contacts: list[ContactResponse]
    total: int


class TouchpointResponse(BaseModel):
    id: str
    contact_id: str
    touchpoint_type: str
    source_id: Optional[str]
    summary: str
    detail: dict
    created_at: Optional[str]


class TouchpointListResponse(BaseModel):
    touchpoints: list[TouchpointResponse]
    total: int


# ── Helpers ─────────────────────────────────────────────

def _contact_response(contact) -> ContactResponse:
    """Convert Contact dataclass to response model."""
    return ContactResponse(
        id=contact.id,
        owner_id=contact.owner_id,
        name=contact.name,
        email=contact.email,
        phone=contact.phone,
        organization=contact.organization,
        entity_type=contact.entity_type,
        status=contact.status,
        department=contact.department,
        total_sessions=contact.total_sessions,
        total_manifest_entries=contact.total_manifest_entries,
        total_feed_events=contact.total_feed_events,
        total_deliverables=contact.total_deliverables,
        total_emails=contact.total_emails,
        total_invoices=contact.total_invoices,
        lifetime_value_usd=contact.lifetime_value_usd,
        tags=contact.tags,
        custom_fields=contact.custom_fields,
        assigned_agent=contact.assigned_agent,
        source=contact.source,
        first_touch_at=contact.first_touch_at,
        last_touch_at=contact.last_touch_at,
        created_at=contact.created_at,
        updated_at=contact.updated_at,
    )


def _touchpoint_response(tp) -> TouchpointResponse:
    """Convert ContactTouchpoint dataclass to response model."""
    return TouchpointResponse(
        id=tp.id,
        contact_id=tp.contact_id,
        touchpoint_type=tp.touchpoint_type,
        source_id=tp.source_id,
        summary=tp.summary,
        detail=tp.detail,
        created_at=tp.created_at,
    )


def _verify_contact_owner(contact, user: UserProfile):
    """Verify the authenticated user can access this contact.

    All deployer contacts use TMOS13_OWNER_ID as owner.
    Any authenticated dashboard user may view them.
    """
    if contact.owner_id != TMOS13_OWNER_ID and contact.owner_id != user.user_id:
        raise HTTPException(404, "Contact not found")


# ── Registration ────────────────────────────────────────

def register_contacts_endpoints(app, contacts_service: ContactsService):
    """Register all contacts endpoints. Called in app.py lifespan."""

    # ── GET /api/contacts ───────────────────────────────

    @app.get("/api/contacts", response_model=ContactListResponse, tags=["contacts"])
    async def list_contacts(
        type: Optional[str] = None,
        status: Optional[str] = None,
        department: Optional[str] = None,
        search: Optional[str] = None,
        tags: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        user: UserProfile = Depends(require_auth),
    ):
        """List contacts with filters and search."""
        limit = min(limit, 200)
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None

        contacts, total = contacts_service.list(
            owner_id=TMOS13_OWNER_ID,
            entity_type=type,
            status=status,
            department=department,
            search=search,
            tags=tag_list,
            limit=limit,
            offset=offset,
        )
        return ContactListResponse(
            contacts=[_contact_response(c) for c in contacts],
            total=total,
        )

    # ── POST /api/contacts/resolve ──────────────────────
    # Registered before /api/contacts/:id to avoid path conflict

    @app.post("/api/contacts/resolve", tags=["contacts"])
    async def resolve_contact(
        req: ResolveContactRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """
        Resolve a contact by email, name, or phone.
        Returns the contact if found, or null. Does NOT create.
        """
        if req.email:
            contact = contacts_service._find_by_email(
                TMOS13_OWNER_ID, req.email.lower().strip()
            )
            if contact:
                return {"contact": _contact_response(contact).model_dump()}

        # Search by name or phone if no email match
        if req.name or req.phone:
            query = req.name or req.phone
            results = contacts_service.search(TMOS13_OWNER_ID, query)
            if results:
                return {"contact": _contact_response(results[0]).model_dump()}

        return {"contact": None}

    # ── GET /api/contacts/:id ───────────────────────────

    @app.get("/api/contacts/{contact_id}", response_model=ContactDetailResponse, tags=["contacts"])
    async def get_contact(
        contact_id: str,
        user: UserProfile = Depends(require_auth),
    ):
        """Get a single contact with 5 most recent touchpoints."""
        contact = contacts_service.get(contact_id)
        if not contact:
            raise HTTPException(404, "Contact not found")
        _verify_contact_owner(contact, user)

        # Include 5 most recent touchpoints inline
        touchpoints, _ = contacts_service.get_touchpoints(contact_id, limit=5)
        tp_dicts = [_touchpoint_response(tp).model_dump() for tp in touchpoints]

        resp = _contact_response(contact)
        return ContactDetailResponse(
            **resp.model_dump(),
            recent_touchpoints=tp_dicts,
        )

    # ── POST /api/contacts ──────────────────────────────

    @app.post("/api/contacts", response_model=ContactResponse, status_code=201, tags=["contacts"])
    async def create_contact(
        req: CreateContactRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """Create a new contact. Returns 409 if email already exists for this owner."""
        # Check for duplicate email
        if req.email:
            existing = contacts_service._find_by_email(
                TMOS13_OWNER_ID, req.email.lower().strip()
            )
            if existing:
                raise HTTPException(
                    409,
                    f"Contact with email {req.email} already exists (id={existing.id})",
                )

        try:
            contact = contacts_service.create(
                owner_id=TMOS13_OWNER_ID,
                name=req.name,
                email=req.email.lower().strip() if req.email else None,
                phone=req.phone,
                organization=req.organization,
                entity_type=req.entity_type or "lead",
                department=req.department,
                tags=req.tags,
                custom_fields=req.custom_fields,
            )
        except ValueError as e:
            raise HTTPException(400, str(e))

        return _contact_response(contact)

    # ── PUT /api/contacts/:id ───────────────────────────

    @app.put("/api/contacts/{contact_id}", response_model=ContactResponse, tags=["contacts"])
    async def update_contact(
        contact_id: str,
        req: UpdateContactRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """Update contact fields."""
        contact = contacts_service.get(contact_id)
        if not contact:
            raise HTTPException(404, "Contact not found")
        _verify_contact_owner(contact, user)

        # Build update dict from non-None fields
        update_fields = {}
        for field_name in [
            "name", "email", "phone", "organization", "entity_type",
            "status", "department", "tags", "custom_fields", "assigned_agent",
        ]:
            val = getattr(req, field_name)
            if val is not None:
                if field_name == "email":
                    val = val.lower().strip()
                update_fields[field_name] = val

        if not update_fields:
            return _contact_response(contact)

        try:
            updated = contacts_service.update(contact_id, **update_fields)
        except ValueError as e:
            raise HTTPException(400, str(e))

        return _contact_response(updated)

    # ── DELETE /api/contacts/:id ─────────────────────────

    @app.delete("/api/contacts/{contact_id}", tags=["contacts"])
    async def delete_contact(
        contact_id: str,
        user: UserProfile = Depends(require_auth),
    ):
        """Delete a contact and all its touchpoints."""
        contact = contacts_service.get(contact_id)
        if not contact:
            raise HTTPException(404, "Contact not found")
        _verify_contact_owner(contact, user)

        deleted = contacts_service.delete(contact_id)
        if not deleted:
            raise HTTPException(500, "Failed to delete contact")
        return {"deleted": True, "id": contact_id}

    # ── GET /api/contacts/:id/touchpoints ───────────────

    @app.get(
        "/api/contacts/{contact_id}/touchpoints",
        response_model=TouchpointListResponse,
        tags=["contacts"],
    )
    async def get_contact_touchpoints(
        contact_id: str,
        type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        user: UserProfile = Depends(require_auth),
    ):
        """Get touchpoints for a contact, ordered newest first."""
        contact = contacts_service.get(contact_id)
        if not contact:
            raise HTTPException(404, "Contact not found")
        _verify_contact_owner(contact, user)

        limit = min(limit, 200)
        touchpoints, total = contacts_service.get_touchpoints(
            contact_id,
            touchpoint_type=type,
            limit=limit,
            offset=offset,
        )
        return TouchpointListResponse(
            touchpoints=[_touchpoint_response(tp) for tp in touchpoints],
            total=total,
        )

    # ── POST /api/contacts/:id/touchpoints ──────────────

    @app.post(
        "/api/contacts/{contact_id}/touchpoints",
        response_model=TouchpointResponse,
        status_code=201,
        tags=["contacts"],
    )
    async def add_contact_touchpoint(
        contact_id: str,
        req: AddTouchpointRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """Add a touchpoint to a contact."""
        contact = contacts_service.get(contact_id)
        if not contact:
            raise HTTPException(404, "Contact not found")
        _verify_contact_owner(contact, user)

        try:
            tp = contacts_service.add_touchpoint(
                contact_id=contact_id,
                touchpoint_type=req.touchpoint_type,
                summary=req.summary,
                source_id=req.source_id,
                detail=req.detail,
            )
        except ValueError as e:
            raise HTTPException(400, str(e))

        return _touchpoint_response(tp)
