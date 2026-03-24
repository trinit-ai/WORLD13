"""
TMOS13 In-Chat Form — API Endpoint

POST /api/form  — Receive in-chat form submissions, store in session state,
                  and trigger alerts when contact info is collected.
"""
import logging
import time
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from errors import APIError, ErrorCode

logger = logging.getLogger("tmos13.forms")


# ─── Pydantic Models ─────────────────────────────────────

class FormSubmissionRequest(BaseModel):
    session_id: str
    form_id: str
    pack_id: str = ""
    data: dict[str, str] = {}
    submitted_at: str = ""


class FormSubmissionResponse(BaseModel):
    success: bool
    form_id: str
    message: str = ""


# ─── Endpoint Registration ───────────────────────────────

def register_form_endpoints(
    app: FastAPI,
    sessions,
    transcript_store,
    alert_classifier,
    alert_store,
    get_session_pack_fn,
    dispatch_alert_fn,
):
    """Register the /api/form endpoint on the FastAPI app."""

    @app.post(
        "/api/form",
        response_model=FormSubmissionResponse,
        tags=["forms"],
    )
    async def submit_form(req: FormSubmissionRequest):
        """
        Receive an in-chat form submission.
        Stores data in session state, records in transcript, and triggers alerts.
        """
        # ─── Validate session ─────────────────────────────
        state = sessions.get(req.session_id)
        if state is None:
            raise APIError(
                ErrorCode.NOT_FOUND,
                f"Session '{req.session_id}' not found",
                status_code=404,
            )

        # ─── Validate form data ──────────────────────────
        if not req.form_id:
            raise APIError(
                ErrorCode.VALIDATION_ERROR,
                "form_id is required",
                status_code=400,
            )

        if not req.data:
            raise APIError(
                ErrorCode.VALIDATION_ERROR,
                "Form data is empty",
                status_code=400,
            )

        # ─── Store in session state ──────────────────────
        form_entry = dict(req.data)
        form_entry["submitted_at"] = req.submitted_at or ""
        state.forms[req.form_id] = form_entry

        logger.info(
            f"Form '{req.form_id}' submitted in session {req.session_id} "
            f"({len(req.data)} field(s))"
        )

        # ─── Record in transcript ────────────────────────
        # Synthesize a structured transcript entry so the alert pipeline
        # can detect contact info even from form submissions.
        field_summary = ", ".join(f"{k}: {v}" for k, v in req.data.items())
        transcript_entry = f"[FORM:{req.form_id}] {field_summary}"

        try:
            transcript_store.record(
                session_id=req.session_id,
                role="user",
                content=transcript_entry,
                metadata={
                    "type": "form_submission",
                    "form_id": req.form_id,
                },
                pack_id=state.pack_id,
                user_id=state.user_id,
            )
        except Exception:
            logger.exception("Failed to record form submission in transcript")

        # ─── Trigger alerts ──────────────────────────────
        try:
            pack = get_session_pack_fn(state)
            if pack:
                alerts_config = pack.alerts_config
                if alerts_config and alerts_config.get("enabled"):
                    transcript = transcript_store.get_session(req.session_id)
                    if transcript:
                        fired = alert_classifier.evaluate(transcript, alerts_config)
                        if fired:
                            alert_store.add_many(fired)
                            for alert in fired:
                                dispatch_alert_fn(alert, transcript, pack)
                            logger.info(
                                f"Form submission triggered {len(fired)} alert(s) "
                                f"in session {req.session_id}"
                            )
        except Exception:
            logger.exception("Error in form alert pipeline")

        return FormSubmissionResponse(
            success=True,
            form_id=req.form_id,
            message="Form received",
        )
