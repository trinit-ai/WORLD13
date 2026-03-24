"""
Email-Exchange Bridge — Converts inbound emails into Ambassador exchanges
and runs them through the pack engine.

Connects: resend_inbound.InboundEmail -> ambassador.Exchange -> app.process_message()
"""

import logging
import time
import uuid
from typing import Optional

import httpx

import config
from resend_inbound import InboundEmail, ResendInboundClient, strip_html

logger = logging.getLogger("tmos13.inbound.bridge")


# ─── Standalone Address Registry ─────────────────────────────
# Used when ambassador_service is not yet deployed.

_ADDRESS_REGISTRY: dict[str, dict] = {}


def register_address(handle: str, domain: str, pack_id: str, owner_id: str = ""):
    """Register an address for standalone mode."""
    key = f"{handle}@{domain}"
    _ADDRESS_REGISTRY[key] = {
        "handle": handle,
        "domain": domain,
        "pack_id": pack_id,
        "owner_id": owner_id,
    }
    logger.debug(f"Address registered: {key} -> pack={pack_id}")


def resolve_address(email_address: str) -> Optional[dict]:
    """Look up address. Returns config dict or None."""
    return _ADDRESS_REGISTRY.get(email_address)


# ─── Email template constants (imported from email_service) ──

EMERALD = "#34d399"
BG = "#060d0a"
CARD_BG = "#0a1510"
TEXT_COLOR = "#e2e8f0"
MUTED = "#64748b"


def _render_reply_html(response_text: str, signature: str = "") -> str:
    """Render a response as branded HTML email."""
    # Escape for HTML safety
    safe_text = (
        response_text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    # Convert newlines to <br>
    safe_text = safe_text.replace("\n", "<br>")

    sig_html = ""
    if signature:
        safe_sig = (
            signature
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )
        sig_html = f"""
        <div style="margin-top:24px; padding-top:16px; border-top:1px solid #1e3a2f;
             font-size:13px; color:{MUTED}; line-height:1.6;">
          {safe_sig}
        </div>"""

    return f"""
  <div style="background:{BG}; color:{TEXT_COLOR}; font-family:'DM Sans',sans-serif;
       padding:40px 24px; max-width:560px; margin:0 auto;">
    <div style="font-family:'JetBrains Mono',monospace; font-size:18px;
         color:{EMERALD}; font-weight:700; letter-spacing:3px; margin-bottom:32px;">
      TMOS13
    </div>
    <div style="background:{CARD_BG}; border:1px solid #1e3a2f; border-radius:8px;
         padding:20px; margin-bottom:24px;">
      <p style="color:{TEXT_COLOR}; font-size:14px; line-height:1.7; margin:0;">
        {safe_text}
      </p>
    </div>
    {sig_html}
    <div style="margin-top:40px; padding-top:20px; border-top:1px solid #1e3a2f;
         font-size:12px; color:{MUTED}; font-family:'JetBrains Mono',monospace;">
      &copy; 2026 TMOS13, LLC &middot; Jersey City, NJ<br>
      <a href="mailto:support@tmos13.ai" style="color:{EMERALD}; text-decoration:none;">
        support@tmos13.ai
      </a>
    </div>
  </div>"""


# ─── EmailExchangeBridge ─────────────────────────────────────


class EmailExchangeBridge:
    """
    Bridge between parsed inbound emails and the Ambassador/engine systems.
    Converts emails into conversations and sends replies.
    """

    def __init__(self, ambassador_service=None, inbound_client: ResendInboundClient = None):
        self._ambassador = ambassador_service
        self._inbound = inbound_client
        # Thread tracking: (address_key, counterparty_email) -> exchange_id
        self._threads: dict[str, str] = {}
        # Track processed count for status endpoint
        self.emails_processed: int = 0
        self.last_received: Optional[str] = None

    async def process_inbound(self, email: InboundEmail) -> dict:
        """
        Main inbound email processing pipeline.

        Steps:
        1. Resolve Ambassador address from `to` field
        2. Determine pack_id from address config
        3. Check for existing thread (resume vs new)
        4. Extract message text from email body
        5. Create SessionState and call process_message()
        6. Record exchange turn
        7. Send reply email
        8. Return result dict
        """
        start_time = time.time()
        self.last_received = email.created_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # 1. Resolve address
        to_address = email.to[0] if email.to else ""
        # Extract bare email from "Name <email>" or just "email"
        if "<" in to_address and ">" in to_address:
            to_address = to_address.split("<")[1].split(">")[0]
        to_address = to_address.strip().lower()

        address_config = None
        if self._ambassador:
            try:
                handle = to_address.split("@")[0] if "@" in to_address else to_address
                domain = to_address.split("@")[1] if "@" in to_address else config.TMOS13_INBOUND_DOMAIN
                addr = self._ambassador.get_address_by_handle(handle, domain)
                address_config = {
                    "handle": addr.handle,
                    "domain": addr.domain,
                    "pack_id": addr.default_protocol_id or "guest",
                    "owner_id": addr.owner_id,
                    "address_id": addr.id,
                }
            except Exception:
                logger.debug(f"Ambassador lookup failed for {to_address}, trying standalone")

        if not address_config:
            address_config = resolve_address(to_address)

        if not address_config:
            logger.warning(f"No address registered for {to_address}")
            return {
                "exchange_id": None,
                "session_id": None,
                "response_preview": None,
                "reply_sent": False,
                "address_handle": to_address,
                "counterparty": email.from_email,
                "error": f"No address registered for {to_address}",
            }

        # 2. Determine pack_id
        pack_id = address_config.get("pack_id", "guest")
        address_handle = address_config.get("handle", "")

        # Load pack manifest for inbound config
        pack = config.get_pack(pack_id)
        manifest = pack.manifest if pack and hasattr(pack, "manifest") else {}
        inbound_config = manifest.get("inbound", {})
        reply_settings = inbound_config.get("reply_settings", {})

        # Check spam filters
        spam_filters = inbound_config.get("spam_filters", {})
        if spam_filters.get("reject_empty_body") and not email.text and not email.html:
            logger.info(f"Rejected email from {email.from_email}: empty body")
            return {
                "exchange_id": None,
                "session_id": None,
                "response_preview": None,
                "reply_sent": False,
                "address_handle": address_handle,
                "counterparty": email.from_email,
                "error": "Rejected: empty body",
            }

        # 3. Check for existing thread
        thread_key = f"{to_address}:{email.from_email}"
        exchange_id = self._threads.get(thread_key, str(uuid.uuid4())[:8])
        is_new_thread = thread_key not in self._threads
        self._threads[thread_key] = exchange_id

        # 4. Extract message text
        message_text = self._extract_message_text(email, is_first=is_new_thread)

        # 5. Create session and process message
        from state import SessionState

        session_id = f"email-{exchange_id}"
        state = SessionState(
            session_id=session_id,
            user_id=f"email:{email.from_email}",
            pack_id=pack_id,
        )

        # Store session in the global sessions dict
        try:
            from app import sessions, process_message, transcript_store
            sessions.put(state)

            # Apply greeting for first message if configured
            greeting = self._get_greeting(inbound_config, address_handle)
            if greeting and is_new_thread:
                # Prepend greeting context to help the AI understand the exchange
                state.add_message("system", f"[GREETING TO INCLUDE: {greeting}]")

            response = await process_message(message_text, state)

        except Exception as e:
            logger.error(f"Process message failed for {email.email_id}: {e}")
            response = "Thank you for your message. We've received it and will follow up shortly."

        # 6. Record exchange (log to transcript store if ambassador not available)
        if self._ambassador:
            try:
                address_id = address_config.get("address_id", "")
                if is_new_thread:
                    exc = self._ambassador.create_exchange(
                        address_id=address_id,
                        direction="inbound",
                        channel="email",
                        counterparty_type="human",
                        counterparty_identifier=email.from_email,
                        counterparty_name=email.from_name,
                    )
                    exchange_id = exc.id
                    self._threads[thread_key] = exchange_id

                self._ambassador.add_turn(
                    exchange_id=exchange_id,
                    direction="inbound",
                    sender_type="human",
                    content_raw=message_text,
                    content_response=response,
                    latency_ms=int((time.time() - start_time) * 1000),
                )
            except Exception as e:
                logger.error(f"Ambassador exchange recording failed: {e}")

        # 7. Send reply
        signature = reply_settings.get("signature", "")
        reply_msg_id = await self._send_threaded_reply(
            email=email,
            response=response,
            address_handle=address_handle,
            from_name=reply_settings.get("from_name", "TMOS13"),
            signature=signature,
        )

        self.emails_processed += 1

        return {
            "exchange_id": exchange_id,
            "session_id": session_id,
            "response_preview": response[:200] if response else "",
            "reply_sent": reply_msg_id is not None,
            "address_handle": address_handle,
            "counterparty": email.from_email,
        }

    def _extract_message_text(self, email: InboundEmail, is_first: bool = True) -> str:
        """Extract message text from email, preferring plain text over HTML."""
        body = email.text
        if not body and email.html:
            body = strip_html(email.html)
        if not body:
            body = "(no message body)"

        # Prepend subject on first message in thread
        if is_first and email.subject:
            return f"Subject: {email.subject}\n\n{body}"
        return body

    def _get_greeting(self, inbound_config: dict, address_handle: str) -> str:
        """Get greeting from inbound config for the matching address handle."""
        addresses = inbound_config.get("addresses", [])
        for addr_cfg in addresses:
            if addr_cfg.get("handle") == address_handle:
                return addr_cfg.get("greeting", "")
        return ""

    async def _send_threaded_reply(
        self,
        email: InboundEmail,
        response: str,
        address_handle: str,
        from_name: str = "TMOS13",
        signature: str = "",
    ) -> Optional[str]:
        """
        Send a reply email with proper threading headers.

        Uses Resend API directly via httpx to include In-Reply-To and
        References headers that email_service.send_email() doesn't support.
        """
        if not self._inbound or not self._inbound._api_key:
            logger.info(f"Reply suppressed (no API key): to={email.from_email}")
            return None

        # Build subject with Re: prefix
        subject = email.subject or "(no subject)"
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"

        # Build from address
        from_addr = config.TMOS13_INBOUND_REPLY_FROM
        if from_name:
            domain = config.TMOS13_INBOUND_DOMAIN
            from_addr = f"{from_name} <{address_handle}@{domain}>"

        # Build HTML
        html = _render_reply_html(response, signature=signature)

        # Build payload
        payload = {
            "from": from_addr,
            "to": [email.from_email],
            "subject": subject,
            "html": html,
            "text": response + (f"\n{signature}" if signature else ""),
        }

        # Threading headers
        headers_payload = {}
        if email.message_id:
            headers_payload["In-Reply-To"] = email.message_id
            headers_payload["References"] = email.message_id
        if headers_payload:
            payload["headers"] = headers_payload

        try:
            async with httpx.AsyncClient(
                base_url="https://api.resend.com",
                headers={"Authorization": f"Bearer {self._inbound._api_key}"},
                timeout=30.0,
            ) as client:
                resp = await client.post("/emails", json=payload)
                resp.raise_for_status()
                result = resp.json()
                msg_id = result.get("id", "unknown")
                logger.info(f"Reply sent: to={email.from_email} subject={subject} id={msg_id}")
                return msg_id
        except Exception as e:
            logger.error(f"Reply send failed: to={email.from_email} error={e}")
            return None
