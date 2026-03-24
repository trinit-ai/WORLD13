"""
TMOS13 Contact Inquiry — API Endpoint

POST /api/contact  — Receive a contact form submission from the DataRail,
                     create/resolve a contact record, and log to the owner's inbox.
"""
import logging
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from errors import APIError, ErrorCode

logger = logging.getLogger("tmos13.contact")


# ─── Pydantic Models ─────────────────────────────────────

class ContactInquiryRequest(BaseModel):
    name: str = ""
    email: str
    company: str = ""
    role: str = ""
    message: str = ""
    pack_id: str = ""
    session_id: str = ""


class ContactInquiryResponse(BaseModel):
    success: bool
    message: str = ""


# ─── Endpoint Registration ───────────────────────────────

def register_contact_inquiry_endpoints(app: FastAPI):
    """Register the /api/contact endpoint on the FastAPI app."""

    @app.post(
        "/api/contact",
        response_model=ContactInquiryResponse,
        tags=["contact"],
    )
    async def submit_contact_inquiry(req: ContactInquiryRequest):
        """
        Receive a contact inquiry from the DataRail.
        Creates/resolves a contact, creates an inbox entry, and logs to manifest.
        """
        if not req.email or not req.email.strip():
            raise APIError(
                ErrorCode.VALIDATION_ERROR,
                "Email is required",
                status_code=400,
            )

        email = req.email.strip().lower()
        name = req.name.strip() or None
        company = req.company.strip() or None
        role = req.role.strip() or None
        message = req.message.strip() or None

        # ─── Resolve / create contact ─────────────────────
        contact_id = None
        try:
            from contacts import get_contacts_service
            contacts_svc = get_contacts_service()
            contact = contacts_svc.resolve_or_create(
                owner_id=_get_owner_id(),
                email=email,
                name=name,
                organization=company,
                source="data_rail",
                department="sales",
            )
            contact_id = contact.id
            contacts_svc.add_touchpoint(
                contact_id=contact.id,
                touchpoint_type="inquiry",
                summary=f"Contact inquiry via DataRail ({req.pack_id or 'guest'})",
                detail={
                    "role": role,
                    "message": message,
                    "pack_id": req.pack_id,
                    "session_id": req.session_id,
                },
            )
            logger.info(f"Contact resolved: {contact.id} ({email})")
        except Exception:
            logger.debug("Contact service unavailable, skipping contact creation", exc_info=True)

        # ─── Create inbox entry ───────────────────────────
        try:
            from inbox import get_inbox_service
            inbox_svc = get_inbox_service()

            summary_parts = []
            if name:
                summary_parts.append(name)
            if company:
                summary_parts.append(f"({company})")
            if role:
                summary_parts.append(f"— {role}")
            if message:
                summary_parts.append(f": {message[:120]}")
            summary = " ".join(summary_parts) or f"Contact inquiry from {email}"

            inbox_svc.record(
                owner_id=_get_owner_id(),
                deployment_id=req.pack_id or "guest",
                deployment_name="TMOS13",
                pack_id=req.pack_id or "guest",
                visitor_name=name,
                visitor_email=email,
                session_id=req.session_id or None,
                transcript=[{
                    "role": "user",
                    "content": f"[CONTACT INQUIRY] Name: {name or 'N/A'}, Email: {email}, "
                               f"Company: {company or 'N/A'}, Role: {role or 'N/A'}, "
                               f"Message: {message or 'N/A'}",
                }],
                classification="inquiry",
                summary=summary,
                priority="normal",
                status="needs_review",
            )
            logger.info(f"Inbox entry created for contact inquiry from {email}")
        except Exception:
            logger.debug("Inbox service unavailable, skipping inbox entry", exc_info=True)

        # ─── Sync to Resend audience ──────────────────────
        try:
            from email_service import sync_to_resend_contacts
            name_parts = (name or "").split(None, 1)
            sync_to_resend_contacts(
                email=email,
                first_name=name_parts[0] if name_parts else "",
                last_name=name_parts[1] if len(name_parts) > 1 else "",
            )
        except Exception:
            logger.debug("Resend contact sync unavailable", exc_info=True)

        # ─── Manifest event ───────────────────────────────
        try:
            from manifest import get_manifest_service
            manifest_svc = get_manifest_service()
            manifest_svc.log(
                owner_id=_get_owner_id(),
                event_type="contact_inquiry",
                category="contact",
                importance="normal",
                summary=f"Contact inquiry from {email}",
                detail={
                    "name": name,
                    "email": email,
                    "company": company,
                    "role": role,
                    "message": message,
                    "pack_id": req.pack_id,
                    "contact_id": contact_id,
                },
                pack_id=req.pack_id or "guest",
                session_id=req.session_id or None,
            )
        except Exception:
            logger.debug("Manifest service unavailable", exc_info=True)

        # ─── Notification email ──────────────────────────
        try:
            from email_service import send_contact_form
            from config import TMOS13_CONTACT_EMAIL
            email_result = send_contact_form(
                to=TMOS13_CONTACT_EMAIL,
                name=name or "",
                sender_email=email,
                company=company or "",
                message=message or "",
                role=role or "",
                session_id=req.session_id or "",
            )
            if email_result is None:
                logger.debug(f"Contact email not sent (Resend not configured): {email}")
        except Exception:
            logger.debug("Email service unavailable", exc_info=True)

        return ContactInquiryResponse(
            success=True,
            message="Thanks \u2014 we'll be in touch.",
        )


def _get_owner_id() -> str:
    """Get the system owner ID for demo/public submissions."""
    try:
        from config import TMOS13_OWNER_ID
        return TMOS13_OWNER_ID
    except ImportError:
        return "a9b2591c-a66d-4ad7-97b2-166a160dbbdd"
