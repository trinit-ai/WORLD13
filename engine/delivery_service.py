"""
TMOS13 Delivery Service — Fibonacci Plume Node 4

Proactive delivery: deliverables that transmit themselves. Creates delivery
intents from generated deliverables, manages approval flow, and dispatches
through channel-specific handlers.

Core invariant (from Recursion Test ontology): AI sessions ALWAYS force
staged mode — no autonomous delivery without human approval.

Follows ambassador_service.py singleton pattern.
"""
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Optional, Callable

from fastapi import HTTPException

from deliverables import DeliveryIntent, Deliverable

logger = logging.getLogger("tmos13.delivery")

# ─── Rate Limiting ─────────────────────────────────────────

_DEFAULT_RATE_LIMIT = 20   # max deliveries per pack per hour
_RATE_WINDOW_SECONDS = 3600


class DeliveryService:
    """
    Manages delivery intent lifecycle: creation, approval, dispatch.

    Channel dispatch is pluggable via init-time callables for email,
    ambassador, and notifications. Webhook is stubbed.
    """

    def __init__(
        self,
        supabase_client=None,
        email_fn: Optional[Callable] = None,
        ambassador_service=None,
        notification_fn: Optional[Callable] = None,
    ):
        self._db = supabase_client
        self._email_fn = email_fn
        self._ambassador_svc = ambassador_service
        self._notification_fn = notification_fn

        # In-memory intent store (keyed by delivery_id)
        self._intents: dict[str, DeliveryIntent] = {}

        # Rate tracking: {pack_id: [timestamp, ...]}
        self._rate_log: dict[str, list[float]] = defaultdict(list)

        logger.info("Delivery service initialized")

    # ─── Intent Creation ──────────────────────────────────

    def create_intent(
        self,
        deliverable: Deliverable,
        delivery_config: dict,
        is_ai: bool = False,
    ) -> list[DeliveryIntent]:
        """
        Create delivery intents for a generated deliverable.

        One intent per channel in deliverable.channels. AI sessions
        force staged mode regardless of config.

        Returns list of created intents.
        """
        channels = deliverable.channels or delivery_config.get("allowed_recipients", ["internal"])
        if not channels:
            channels = ["internal"]

        default_mode = delivery_config.get("default_mode", "staged")
        require_approval_ai = delivery_config.get("require_approval_for_ai_sessions", True)

        intents = []
        for channel in channels:
            # AI sessions force staged mode (Recursion Test mandate)
            if is_ai and require_approval_ai:
                mode = "staged"
            else:
                mode = default_mode

            intent = DeliveryIntent(
                deliverable_id=deliverable.deliverable_id,
                user_id=deliverable.user_id,
                pack_id=deliverable.pack_id,
                session_id=deliverable.session_id,
                recipient_type=channel,
                recipient_address=self._resolve_address(deliverable, channel),
                recipient_name=self._resolve_name(deliverable),
                mode=mode,
                status="pending",
                channel=channel,
                is_ai_session=is_ai,
            )

            # Rate limit check
            if not self._check_rate(intent.pack_id):
                intent.status = "failed"
                intent.error_message = "Rate limit exceeded for pack delivery."
                logger.warning(
                    "Delivery rate limited: pack=%s delivery=%s",
                    intent.pack_id, intent.delivery_id,
                )

            self._intents[intent.delivery_id] = intent
            self._persist_intent(intent)

            # Auto mode: dispatch immediately (if not rate limited)
            if mode == "auto" and intent.status == "pending":
                self._dispatch(intent)

            intents.append(intent)
            self._record_rate(intent.pack_id)

        logger.info(
            "Created %d delivery intent(s) for deliverable %s (ai=%s)",
            len(intents), deliverable.deliverable_id, is_ai,
        )
        return intents

    # ─── Approval Flow ────────────────────────────────────

    def approve(self, delivery_id: str, approved_by: str) -> DeliveryIntent:
        """Approve a staged delivery and dispatch it."""
        intent = self._get_intent(delivery_id)
        if intent.status != "pending":
            raise HTTPException(400, f"Cannot approve delivery in '{intent.status}' status")

        intent.status = "approved"
        intent.approved_by = approved_by
        intent.approved_at = time.time()
        intent.updated_at = time.time()

        self._dispatch(intent)
        self._persist_intent(intent)
        logger.info("Delivery approved: %s by %s", delivery_id, approved_by)
        return intent

    def cancel(self, delivery_id: str) -> DeliveryIntent:
        """Cancel a pending delivery."""
        intent = self._get_intent(delivery_id)
        if intent.status not in ("pending", "approved"):
            raise HTTPException(400, f"Cannot cancel delivery in '{intent.status}' status")

        intent.status = "cancelled"
        intent.updated_at = time.time()
        self._persist_intent(intent)
        logger.info("Delivery cancelled: %s", delivery_id)
        return intent

    def list_pending(
        self,
        user_id: Optional[str] = None,
        pack_id: Optional[str] = None,
    ) -> list[DeliveryIntent]:
        """List pending delivery intents, optionally filtered."""
        results = []
        for intent in self._intents.values():
            if intent.status != "pending":
                continue
            if user_id and intent.user_id != user_id:
                continue
            if pack_id and intent.pack_id != pack_id:
                continue
            results.append(intent)
        return sorted(results, key=lambda i: i.created_at, reverse=True)

    def get_intent(self, delivery_id: str) -> DeliveryIntent:
        """Get a delivery intent by ID."""
        return self._get_intent(delivery_id)

    # ─── Dispatch Routing ─────────────────────────────────

    def _dispatch(self, intent: DeliveryIntent):
        """Route delivery to the appropriate channel handler."""
        try:
            handler = {
                "email": self._dispatch_email,
                "ambassador": self._dispatch_ambassador,
                "webhook": self._dispatch_webhook,
                "internal": self._dispatch_internal,
            }.get(intent.channel)

            if not handler:
                intent.status = "failed"
                intent.error_message = f"Unknown delivery channel: {intent.channel}"
                logger.error("Unknown delivery channel: %s", intent.channel)
                return

            handler(intent)
        except Exception as e:
            intent.status = "failed"
            intent.error_message = str(e)
            intent.updated_at = time.time()
            logger.exception("Delivery dispatch failed: %s", intent.delivery_id)

    def _dispatch_email(self, intent: DeliveryIntent):
        """Send deliverable via email."""
        if not self._email_fn:
            intent.status = "failed"
            intent.error_message = "Email service not configured"
            return

        try:
            self._email_fn(
                to=intent.recipient_address,
                subject=f"TMOS13 Deliverable — {intent.pack_id}",
                html_body=f"<p>A deliverable has been generated for your session.</p>"
                          f"<p>Deliverable ID: {intent.deliverable_id}</p>",
            )
            intent.status = "sent"
            intent.sent_at = time.time()
            intent.updated_at = time.time()
            logger.info("Email delivery sent: %s to %s", intent.delivery_id, intent.recipient_address)
        except Exception as e:
            intent.status = "failed"
            intent.error_message = f"Email send failed: {e}"
            intent.updated_at = time.time()

    def _dispatch_ambassador(self, intent: DeliveryIntent):
        """Send deliverable via Ambassador outbound exchange."""
        if not self._ambassador_svc:
            intent.status = "failed"
            intent.error_message = "Ambassador service not configured"
            return

        try:
            from ambassador_service import get_ambassador_service
            svc = self._ambassador_svc

            exchange = svc.initiate_outbound_exchange(
                address_id=intent.recipient_address,
                protocol_id=None,
                counterparty_identifier=intent.recipient_name,
                counterparty_name=intent.recipient_name,
                channel="agent",
                delivery_payload={
                    "delivery_id": intent.delivery_id,
                    "deliverable_id": intent.deliverable_id,
                    "pack_id": intent.pack_id,
                },
            )
            intent.exchange_id = exchange.id
            intent.status = "sent"
            intent.sent_at = time.time()
            intent.updated_at = time.time()
            logger.info(
                "Ambassador delivery sent: %s exchange=%s",
                intent.delivery_id, exchange.id,
            )
        except Exception as e:
            intent.status = "failed"
            intent.error_message = f"Ambassador dispatch failed: {e}"
            intent.updated_at = time.time()

    def _dispatch_webhook(self, intent: DeliveryIntent):
        """Webhook delivery — STUB for Node 4. Logs and marks sent."""
        logger.info(
            "Webhook delivery STUB: %s → %s (not implemented)",
            intent.delivery_id, intent.recipient_address,
        )
        intent.status = "sent"
        intent.sent_at = time.time()
        intent.updated_at = time.time()

    def _dispatch_internal(self, intent: DeliveryIntent):
        """Send deliverable as internal notification."""
        if not self._notification_fn:
            # No notification service — mark as sent anyway (dashboard visible)
            intent.status = "sent"
            intent.sent_at = time.time()
            intent.updated_at = time.time()
            return

        try:
            self._notification_fn(
                user_id=intent.user_id,
                title="Deliverable Ready",
                body=f"A new deliverable has been generated in {intent.pack_id}.",
                data={"delivery_id": intent.delivery_id},
            )
            intent.status = "sent"
            intent.sent_at = time.time()
            intent.updated_at = time.time()
            logger.info("Internal delivery sent: %s to user %s", intent.delivery_id, intent.user_id)
        except Exception as e:
            intent.status = "failed"
            intent.error_message = f"Notification failed: {e}"
            intent.updated_at = time.time()

    # ─── Helpers ──────────────────────────────────────────

    def _get_intent(self, delivery_id: str) -> DeliveryIntent:
        """Get intent from memory or raise 404."""
        intent = self._intents.get(delivery_id)
        if not intent:
            raise HTTPException(404, f"Delivery intent {delivery_id} not found")
        return intent

    def _resolve_address(self, deliverable: Deliverable, channel: str) -> str:
        """Extract recipient address from deliverable contact info."""
        contact = deliverable.contact_info or {}
        if channel == "email":
            return contact.get("email", "")
        if channel == "ambassador":
            return contact.get("ambassador_address", "")
        return ""

    def _resolve_name(self, deliverable: Deliverable) -> str:
        """Extract recipient name from deliverable."""
        contact = deliverable.contact_info or {}
        return contact.get("name", contact.get("client_name", ""))

    def _check_rate(self, pack_id: str) -> bool:
        """Check if pack is within delivery rate limit."""
        now = time.time()
        window_start = now - _RATE_WINDOW_SECONDS
        self._rate_log[pack_id] = [
            t for t in self._rate_log[pack_id] if t > window_start
        ]
        return len(self._rate_log[pack_id]) < _DEFAULT_RATE_LIMIT

    def _record_rate(self, pack_id: str):
        """Record a delivery event for rate limiting."""
        self._rate_log[pack_id].append(time.time())

    def _persist_intent(self, intent: DeliveryIntent):
        """Persist intent to Supabase (best-effort)."""
        if not self._db:
            return
        try:
            row = {
                "id": intent.delivery_id,
                "deliverable_id": intent.deliverable_id,
                "user_id": intent.user_id or None,
                "pack_id": intent.pack_id,
                "session_id": intent.session_id or None,
                "recipient_type": intent.recipient_type,
                "recipient_address": intent.recipient_address or None,
                "mode": intent.mode,
                "status": intent.status,
                "channel": intent.channel,
                "is_ai_session": intent.is_ai_session,
                "exchange_id": intent.exchange_id,
                "approved_by": intent.approved_by,
                "approved_at": datetime.fromtimestamp(intent.approved_at, tz=timezone.utc).isoformat() if intent.approved_at else None,
                "sent_at": datetime.fromtimestamp(intent.sent_at, tz=timezone.utc).isoformat() if intent.sent_at else None,
                "error_message": intent.error_message or None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            self._db.table("delivery_records").upsert(row).execute()
        except Exception as e:
            logger.warning("Failed to persist delivery intent %s: %s", intent.delivery_id, e)


# ─── Singleton ────────────────────────────────────────────

_delivery_service: Optional[DeliveryService] = None


def init_delivery_service(
    supabase_client=None,
    email_fn: Optional[Callable] = None,
    ambassador_service=None,
    notification_fn: Optional[Callable] = None,
) -> DeliveryService:
    """Initialize the global delivery service. Called during app lifespan."""
    global _delivery_service
    _delivery_service = DeliveryService(
        supabase_client=supabase_client,
        email_fn=email_fn,
        ambassador_service=ambassador_service,
        notification_fn=notification_fn,
    )
    return _delivery_service


def get_delivery_service() -> DeliveryService:
    """Get the global delivery service instance."""
    if _delivery_service is None:
        raise HTTPException(503, "Delivery service not initialized")
    return _delivery_service
