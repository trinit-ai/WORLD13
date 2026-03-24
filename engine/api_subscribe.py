"""
TMOS13 Email Subscribe — API Endpoint

POST /api/subscribe  — Receive an email subscription from the DataRail.
                       Upserts into the subscribers table (dedup on email).
"""
import logging
from datetime import datetime, timezone

from fastapi import FastAPI
from pydantic import BaseModel

from errors import APIError, ErrorCode

logger = logging.getLogger("tmos13.subscribe")


# ─── Pydantic Models ─────────────────────────────────────

class SubscribeRequest(BaseModel):
    email: str
    name: str = ""
    pack_id: str = ""
    session_id: str = ""


class SubscribeResponse(BaseModel):
    success: bool
    message: str = ""


# ─── Endpoint Registration ───────────────────────────────

def register_subscribe_endpoints(app: FastAPI, supabase_client=None):
    """Register the /api/subscribe endpoint on the FastAPI app."""

    @app.post(
        "/api/subscribe",
        response_model=SubscribeResponse,
        tags=["subscribe"],
    )
    async def subscribe(req: SubscribeRequest):
        """
        Subscribe an email address. Deduplicates on email (upsert).
        """
        if not req.email or not req.email.strip():
            raise APIError(
                ErrorCode.VALIDATION_ERROR,
                "Email is required",
                status_code=400,
            )

        email = req.email.strip().lower()
        now = datetime.now(timezone.utc).isoformat()

        # ─── Upsert into subscribers table ────────────────
        stored = False
        if supabase_client:
            try:
                row = {
                    "email": email,
                    "subscribed_at": now,
                    "source_pack": req.pack_id or "guest",
                    "source_session": req.session_id or None,
                    "status": "active",
                }
                if req.name and req.name.strip():
                    row["name"] = req.name.strip()
                supabase_client.table("subscribers").upsert(
                    row,
                    on_conflict="email",
                ).execute()
                stored = True
                logger.info(f"Subscriber upserted: {email}")
            except Exception:
                logger.exception(f"Failed to upsert subscriber {email}")
        else:
            logger.warning("No Supabase client — subscriber not persisted")

        # ─── Resolve / create contact ─────────────────────
        contact_id = None
        try:
            from contacts import get_contacts_service
            contacts_svc = get_contacts_service()
            contact = contacts_svc.resolve_or_create(
                owner_id=_get_owner_id(),
                email=email,
                name=req.name.strip() or None,
                source="data_rail",
                department="newsletter",
            )
            contact_id = contact.id
            contacts_svc.add_touchpoint(
                contact_id=contact.id,
                touchpoint_type="subscription",
                summary=f"Email subscription via {req.pack_id or 'guest'} pack",
                detail={
                    "pack_id": req.pack_id,
                    "session_id": req.session_id,
                },
            )
            logger.info(f"Contact resolved for subscriber: {contact.id} ({email})")
        except Exception:
            logger.debug("Contact service unavailable, skipping contact creation", exc_info=True)

        # ─── Create inbox entry ───────────────────────────
        try:
            from inbox import get_inbox_service
            inbox_svc = get_inbox_service()
            inbox_svc.record(
                owner_id=_get_owner_id(),
                deployment_id=req.pack_id or "guest",
                deployment_name="TMOS13",
                pack_id=req.pack_id or "guest",
                visitor_name=req.name.strip() or None,
                visitor_email=email,
                session_id=req.session_id or None,
                transcript=[{
                    "role": "user",
                    "content": f"[EMAIL SUBSCRIPTION] {email}",
                }],
                classification="subscription",
                summary=f"Email subscription: {email}",
                priority="low",
                status="needs_review",
            )
            logger.info(f"Inbox entry created for subscriber {email}")
        except Exception:
            logger.debug("Inbox service unavailable, skipping inbox entry", exc_info=True)

        # ─── Sync to Resend audience ──────────────────────
        try:
            from email_service import sync_to_resend_contacts
            name_parts = (req.name.strip() or "").split(None, 1)
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
                event_type="email_subscribed",
                category="contact",
                importance="low",
                summary=f"Email subscription: {email}",
                detail={
                    "email": email,
                    "pack_id": req.pack_id,
                    "stored": stored,
                    "contact_id": contact_id,
                },
                pack_id=req.pack_id or "guest",
                session_id=req.session_id or None,
            )
        except Exception:
            logger.debug("Manifest service unavailable", exc_info=True)

        return SubscribeResponse(
            success=True,
            message="You're on the list.",
        )


def _get_owner_id() -> str:
    """Get the system owner ID for demo/public submissions."""
    try:
        from config import TMOS13_OWNER_ID
        return TMOS13_OWNER_ID
    except ImportError:
        return "a9b2591c-a66d-4ad7-97b2-166a160dbbdd"
