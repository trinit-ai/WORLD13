"""
Inbound Email Webhook — Resend webhook receiver.

POST /api/webhook/email — receives email.received events from Resend.
Verifies signature, parses payload, triggers async processing.
"""

import json
import logging
import time
from typing import Optional

from fastapi import FastAPI, Request, BackgroundTasks, Depends
from auth import require_role
from fastapi.responses import JSONResponse

import config
from resend_inbound import ResendInboundClient
from email_exchange import EmailExchangeBridge

logger = logging.getLogger("tmos13.inbound.api")

# ─── Module-level counters ───────────────────────────────────

_emails_processed: int = 0
_last_received: Optional[str] = None


def _track_received():
    """Increment the processed counter and update timestamp."""
    global _emails_processed, _last_received
    _emails_processed += 1
    _last_received = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ─── Background processing wrapper ──────────────────────────


async def _process_email_background(bridge: EmailExchangeBridge, email):
    """Run bridge.process_inbound in the background, track metrics."""
    try:
        result = await bridge.process_inbound(email)
        _track_received()
        logger.info(
            f"Inbound email processed: email_id={email.email_id} "
            f"from={email.from_email} reply_sent={result.get('reply_sent', False)}"
        )
    except Exception as e:
        _track_received()
        logger.exception(f"Background email processing failed: {e}")


# ─── Endpoint Registration ───────────────────────────────────


def register_inbound_endpoints(
    app: FastAPI,
    bridge: EmailExchangeBridge,
    inbound_client: ResendInboundClient,
):
    """Register inbound email webhook endpoints on the FastAPI app."""
    from email_exchange import _ADDRESS_REGISTRY

    @app.post("/api/webhook/email", tags=["inbound"])
    async def receive_email_webhook(request: Request, background_tasks: BackgroundTasks):
        """
        Receive Resend email.received webhook events.

        Verifies signature (if configured), parses the payload,
        fetches email body, and schedules async processing.
        """
        # 1. Read raw body for signature verification
        try:
            body_bytes = await request.body()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "detail": "Could not read request body"},
            )

        # 2. Parse JSON
        try:
            payload = json.loads(body_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"status": "error", "detail": "Invalid JSON"},
            )

        # 3. Signature verification
        webhook_secret = config.TMOS13_RESEND_WEBHOOK_SECRET
        if not webhook_secret:
            # In production, reject webhooks when no secret is configured
            if config.ENV == "production":
                logger.error("Webhook rejected: no signing secret configured in production")
                return JSONResponse(
                    status_code=500,
                    content={"status": "error", "detail": "Webhook verification not configured"},
                )
            logger.warning("Webhook received without signature verification (no secret configured — dev only)")
        else:
            svix_id = request.headers.get("svix-id", "")
            svix_timestamp = request.headers.get("svix-timestamp", "")
            svix_signature = request.headers.get("svix-signature", "")

            if not svix_id or not svix_timestamp or not svix_signature:
                return JSONResponse(
                    status_code=401,
                    content={"status": "error", "detail": "Missing signature headers"},
                )

            # Reject stale webhooks (> 5 minutes old) to prevent replay attacks
            try:
                ts = int(svix_timestamp)
                if abs(int(time.time()) - ts) > 300:
                    logger.warning("Webhook rejected: timestamp too old (possible replay)")
                    return JSONResponse(
                        status_code=401,
                        content={"status": "error", "detail": "Webhook timestamp expired"},
                    )
            except (ValueError, TypeError):
                return JSONResponse(
                    status_code=401,
                    content={"status": "error", "detail": "Invalid timestamp"},
                )

            if not inbound_client.verify_signature(
                body_bytes, svix_id, svix_timestamp, svix_signature, webhook_secret
            ):
                logger.warning("Webhook signature verification failed")
                return JSONResponse(
                    status_code=401,
                    content={"status": "error", "detail": "Invalid signature"},
                )

        # 4. Parse webhook payload
        email = await inbound_client.parse_webhook(payload)
        if email is None:
            return JSONResponse(
                status_code=200,
                content={"status": "ignored", "reason": "Not an email.received event"},
            )

        # 5. Fetch email body (hydrate)
        await inbound_client.fetch_and_hydrate(email)

        # 6. Schedule background processing
        background_tasks.add_task(_process_email_background, bridge, email)

        logger.info(f"Webhook accepted: email_id={email.email_id} from={email.from_email}")
        return JSONResponse(
            status_code=200,
            content={"status": "accepted", "email_id": email.email_id},
        )

    @app.get("/api/webhook/email/status", tags=["inbound"])
    async def inbound_status(user=Depends(require_role("admin"))):
        """Health check for inbound email system."""
        return {
            "enabled": config.TMOS13_INBOUND_ENABLED,
            "inbound_configured": inbound_client is not None,
            "signature_verification": bool(config.TMOS13_RESEND_WEBHOOK_SECRET),
            "addresses_registered": len(_ADDRESS_REGISTRY),
            "emails_processed": _emails_processed + bridge.emails_processed,
            "last_received": _last_received or bridge.last_received,
        }

    logger.info("Inbound email endpoints registered: POST /api/webhook/email, GET /api/webhook/email/status")
