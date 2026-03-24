"""
TMOS13 DataRail API — Secure Structured Data Capture

Endpoints:
  POST /api/datarail/submit             — Pack-tab form submission (contact capture + email)
  POST /api/sessions/{session_id}/rail  — Submit structured data to a rail
  GET  /api/sessions/{session_id}/rail  — Get rail submissions for a session
  GET  /api/rail/status                 — Get rail status (legacy compat)
"""

import logging
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger("tmos13.api.rail")


# ─── Request / Response Models ───────────────────────────

class RailSubmitRequest(BaseModel):
    rail_id: str = "default"
    cartridge_id: str
    fields: dict[str, str | int | float | bool]


class RailSubmitResponse(BaseModel):
    receipt_token: str
    status: str = "completed"


class RailStatusResponse(BaseModel):
    status: str  # idle | active | submitting | submitted | error
    activeSchema: Optional[dict] = None
    receiptToken: Optional[str] = None
    error: Optional[str] = None


class DataRailSubmitRequest(BaseModel):
    """Generic pack-tab form submission from DataRailDemo.tsx."""
    session_id: str = ""
    pack_id: str = ""
    # All remaining fields are dynamic — passed via **extra
    model_config = {"extra": "allow"}


class DataRailSubmitResponse(BaseModel):
    success: bool
    contact_id: Optional[str] = None
    message: str = ""


# ─── Contact Field Mapping ────────────────────────────────

# Map common data-rail field IDs to contact fields.
# Pack manifests use varied field names — this normalises them.
_CONTACT_FIELD_MAP = {
    # name
    "client_name": "name", "name": "name", "full_name": "name",
    "contact_name": "name", "your_name": "name",
    "patient_name": "name", "applicant_name": "name",
    # email
    "client_email": "email", "email": "email", "contact_email": "email",
    "patient_email": "email", "applicant_email": "email",
    # phone
    "client_phone": "phone", "phone": "phone", "contact_phone": "phone",
    "patient_phone": "phone", "applicant_phone": "phone",
    # org
    "company": "organization", "organization": "organization",
    "firm": "organization", "org": "organization",
}


def _extract_contact_fields(data: dict) -> dict:
    """Pull name/email/phone/organization from arbitrary form data."""
    contact = {}
    for field_id, value in data.items():
        if not value or not isinstance(value, str):
            continue
        mapped = _CONTACT_FIELD_MAP.get(field_id)
        if mapped and mapped not in contact:
            contact[mapped] = value.strip()
    return contact


# ─── Registration ────────────────────────────────────────

def register_rail_endpoints(app: FastAPI) -> None:
    """Register DataRail API endpoints."""

    # ── POST /api/datarail/submit ─────────────────────────
    # Public endpoint (no auth required) — called from DataRailDemo
    # when a user submits a pack-type Data Rail tab.

    @app.post(
        "/api/datarail/submit",
        response_model=DataRailSubmitResponse,
        tags=["datarail"],
    )
    async def datarail_submit(req: DataRailSubmitRequest):
        """
        Accept a pack-tab Data Rail form submission.

        1. Extracts contact fields from form data.
        2. Updates the session transcript's contact_info.
        3. Sends an email notification to the workspace alert address.
        4. Creates/resolves a contact if the contacts service is available.
        5. Returns { success: true }.
        """
        # Gather all submitted fields (explicit + extra)
        form_data = {}
        if req.model_extra:
            form_data.update(req.model_extra)

        contact_fields = _extract_contact_fields(form_data)
        if not contact_fields:
            return DataRailSubmitResponse(
                success=False,
                message="No contact information found in submission.",
            )

        session_id = req.session_id
        pack_id = req.pack_id

        # ── 1. Update transcript contact_info ──────────────
        try:
            from app import transcript_store
            if transcript_store and session_id:
                transcript = transcript_store.get(session_id)
                if transcript:
                    if transcript.contact_info:
                        transcript.contact_info.update(contact_fields)
                    else:
                        transcript.contact_info = dict(contact_fields)
                    transcript_store._persist_transcript(transcript)
                    logger.info("DataRail submit: updated transcript contact_info session=%s", session_id)
        except Exception as e:
            logger.warning("DataRail submit: transcript update failed: %s", e)

        # ── 2. Send email notification ─────────────────────
        try:
            from email_service import send_contact_form
            alert_email = os.environ.get("TMOS13_ALERT_EMAIL", "owner@tmos13.ai")
            send_contact_form(
                to=alert_email,
                name=contact_fields.get("name", "Unknown"),
                sender_email=contact_fields.get("email", ""),
                subject=f"Data Rail submission — {pack_id}",
                company=contact_fields.get("organization", ""),
                message=form_data.get("summary", ""),
                session_id=session_id,
            )
        except Exception as e:
            logger.warning("DataRail submit: email notification failed: %s", e)

        # ── 3. Create/resolve contact ──────────────────────
        contact_id = None
        try:
            from contacts import get_contacts_service
            contacts_svc = get_contacts_service()

            # Determine owner: session user if authenticated, else deployer owner
            owner_id = None
            try:
                from app import sessions
                state = sessions.get(session_id) if session_id else None
                if state and state.user_id and state.user_id != "anonymous":
                    owner_id = state.user_id
                else:
                    owner_id = os.environ.get("TMOS13_OWNER_ID")
            except Exception:
                owner_id = os.environ.get("TMOS13_OWNER_ID")

            # Pull correlation_id from session state for reconciliation
            _corr_id = getattr(state, "correlation_id", None) if state else None

            if owner_id and contact_fields.get("email"):
                contact = contacts_svc.resolve_or_create(
                    owner_id=owner_id,
                    email=contact_fields.get("email"),
                    name=contact_fields.get("name"),
                    phone=contact_fields.get("phone"),
                    organization=contact_fields.get("organization"),
                    source="form",
                    department=pack_id,
                    correlation_id=_corr_id,
                    session_id=session_id,
                )
                if contact:
                    contact_id = contact.id
                    # Form data is authoritative — overwrite stale fields
                    form_updates = {}
                    if contact_fields.get("name") and contact.name != contact_fields["name"]:
                        form_updates["name"] = contact_fields["name"]
                    if contact_fields.get("phone") and contact.phone != contact_fields["phone"]:
                        form_updates["phone"] = contact_fields["phone"]
                    if contact_fields.get("organization") and contact.organization != contact_fields["organization"]:
                        form_updates["organization"] = contact_fields["organization"]
                    if form_updates:
                        contacts_svc.update(contact.id, **form_updates)
                    # Add a "form" touchpoint
                    contacts_svc.add_touchpoint(
                        contact_id=contact.id,
                        touchpoint_type="form",
                        summary=f"Data Rail submission ({pack_id})",
                        source_id=session_id,
                        detail=form_data,
                    )
                    logger.info("DataRail submit: contact resolved id=%s", contact.id)
        except Exception as e:
            logger.debug("DataRail submit: contact creation skipped: %s", e)

        # ── 4. Add receipt token + write form data to session state ──
        # This unlocks the data rail gate so the session can proceed.
        # Writing to state.forms ensures _record_inbox_turn() picks up
        # contact info on subsequent turns (primary lookup path).
        try:
            from app import sessions as _sessions
            _state = _sessions.get(session_id) if session_id else None
            if _state:
                import secrets
                rail_id = form_data.get("_rail_id") or pack_id or "form"
                token = f"rail:{rail_id}:{secrets.token_hex(6)}"
                _state.receipt_tokens.append(token)
                # Write form data to state.forms so inbox upsert finds it
                _state.forms[f"datarail:{rail_id}"] = dict(form_data)
                logger.info("DataRail submit: receipt token added session=%s token=%s", session_id, token)

                # ── 5. Snapshot transcript on contact provision ────
                try:
                    import asyncio
                    from transcripts import log_transcript_for_contact
                    asyncio.get_event_loop().create_task(
                        asyncio.to_thread(log_transcript_for_contact, session_id, "rail")
                    )
                except Exception as snap_err:
                    logger.debug("DataRail submit: transcript snapshot skipped: %s", snap_err)
        except Exception as e:
            logger.debug("DataRail submit: receipt token skipped: %s", e)

        # ── 5b. Patch inbox row immediately ────────────────
        # Don't wait for next chat turn — update visitor_email/name now
        # so the inbox shows the contact info right away.
        try:
            from inbox import get_inbox_service
            inbox_svc = get_inbox_service()
            _email = contact_fields.get("email")
            _name = contact_fields.get("name")
            if inbox_svc and session_id and (_email or _name):
                patch = {"updated_at": __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ).isoformat()}
                if _email:
                    patch["visitor_email"] = _email
                if _name:
                    patch["visitor_name"] = _name
                if contact_id:
                    patch["contact_id"] = contact_id
                inbox_svc._db.table(inbox_svc._table).update(
                    patch
                ).eq("session_id", session_id).execute()
                logger.info("DataRail submit: inbox patched session=%s email=%s", session_id, _email)
        except Exception as e:
            logger.debug("DataRail submit: inbox patch skipped: %s", e)

        return DataRailSubmitResponse(
            success=True,
            contact_id=contact_id,
            message="Contact information saved.",
        )

    @app.post(
        "/api/sessions/{session_id}/rail",
        response_model=RailSubmitResponse,
        tags=["datarail"],
    )
    async def submit_rail(session_id: str, req: RailSubmitRequest, request: Request):
        """
        Submit structured data to a DataRail.

        Data is stored in Supabase with PII separation and never sent to the LLM.
        A receipt token is returned for injection into the session context.
        """
        from data_rail import get_data_rail_service, RailFieldDef
        from pack_loader import PackLoader

        # Get the session to validate it exists and find the pack
        from app import sessions
        state = sessions.get(session_id)
        if not state:
            raise HTTPException(status_code=404, detail="Session not found")

        # Get the pack and rail schema for field definitions
        pack = None
        field_defs = []
        try:
            pack = PackLoader(state.pack_id)
            schema = pack.get_rail_schema(req.cartridge_id, req.rail_id)
            if schema:
                field_defs = [
                    RailFieldDef(
                        id=f["id"],
                        type=f["type"],
                        label=f["label"],
                        required=f.get("required", True),
                        pii=f.get("pii", False),
                        options=f.get("options", []),
                        validation=f.get("validation"),
                    )
                    for f in schema.get("fields", [])
                ]
        except Exception:
            pass  # pack/schema not available — submit without PII separation

        try:
            service = get_data_rail_service()
            result = await service.submit(
                session_id=session_id,
                pack_id=state.pack_id,
                cartridge_id=req.cartridge_id,
                rail_id=req.rail_id,
                fields=req.fields,
                field_defs=field_defs,
            )

            # Add receipt token to session state
            if result.get("receipt_token"):
                state.receipt_tokens.append(result["receipt_token"])

            logger.info(
                "Rail submission: rail=%s session=%s cart=%s fields=%d pii=%d",
                req.rail_id, session_id, req.cartridge_id,
                result.get("field_count", 0), result.get("pii_field_count", 0),
            )

            return RailSubmitResponse(
                receipt_token=result["receipt_token"],
                status="completed",
            )

        except Exception as e:
            logger.error("Rail submission failed: %s", e)
            # Fallback: in-memory submission when Supabase not configured
            import secrets
            receipt_token = f"rail:{req.cartridge_id}:{req.rail_id}:{secrets.token_hex(6)}"
            state.receipt_tokens.append(receipt_token)
            return RailSubmitResponse(
                receipt_token=receipt_token,
                status="completed",
            )

    @app.get(
        "/api/sessions/{session_id}/rail",
        tags=["datarail"],
    )
    async def get_rail_submissions(session_id: str):
        """Get all rail submissions for a session."""
        try:
            from data_rail import get_data_rail_service
            service = get_data_rail_service()
            tokens = await service.get_receipt_tokens(session_id)
            return {"session_id": session_id, "receipt_tokens": tokens}
        except Exception:
            from app import sessions
            state = sessions.get(session_id)
            tokens = state.receipt_tokens if state else []
            return {"session_id": session_id, "receipt_tokens": tokens}

    @app.get(
        "/api/rail/status",
        response_model=RailStatusResponse,
        tags=["datarail"],
    )
    async def get_rail_status(rail_id: str, session_id: str):
        """Get the current rail status for a session (legacy compatibility)."""
        from app import sessions
        state = sessions.get(session_id)

        if not state:
            return RailStatusResponse(status="idle")

        # Check if there's a pending rail request
        pending = getattr(state, "_pending_rail_id", None)
        if pending and (pending == rail_id or rail_id == "default"):
            return RailStatusResponse(status="active")

        # Check if rail was recently submitted
        for token in state.receipt_tokens:
            if f":{rail_id}:" in token:
                return RailStatusResponse(
                    status="submitted",
                    receiptToken=token,
                )

        return RailStatusResponse(status="idle")

    @app.get(
        "/api/rail/contact/{contact_id}/submissions",
        tags=["datarail"],
    )
    async def get_contact_submissions(contact_id: str):
        """Get all rail submissions linked to a contact."""
        from data_rail import get_data_rail_service
        service = get_data_rail_service()
        submissions = await service.get_contact_submissions(contact_id)
        return {"contact_id": contact_id, "submissions": submissions}
