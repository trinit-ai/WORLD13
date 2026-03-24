"""
Email Channel Adapter — Inbound email via Resend webhooks.

Wraps the existing EmailExchangeBridge pattern into the unified
channel adapter interface. Handles:
- Parsing Resend webhook payloads into InboundMessage
- Formatting engine responses as branded HTML email
- Sending threaded replies via Resend API

Note: Named email_adapter.py to avoid collision with stdlib email module.
"""

import logging
import os
import re
from typing import Optional

from channels.base import (
    ChannelAdapter,
    ChannelCapabilities,
    ChannelType,
    InboundMessage,
    OutboundMessage,
)

logger = logging.getLogger("tmos13.channels.email")

# ─── HTML Template Constants ────────────────────────────────
EMERALD = "#34d399"
BG = "#060d0a"
CARD_BG = "#0a1510"
TEXT_COLOR = "#e2e8f0"
MUTED = "#64748b"


class EmailChannelAdapter(ChannelAdapter):
    """Email channel adapter: Resend inbound/outbound."""

    def __init__(self, default_domain: str = "tmos13.ai"):
        self.default_domain = default_domain

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.EMAIL

    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(
            supports_html=True,
            supports_markdown=False,
            supports_media=True,  # attachments
            supports_buttons=False,
            supports_forms=False,
            max_message_length=0,  # unlimited
            supports_threading=True,
            supports_typing_indicator=False,
        )

    def parse_inbound(self, raw: dict) -> Optional[InboundMessage]:
        """
        Parse a Resend email.received webhook payload.

        Expected raw dict keys from webhook:
          type, data.email_id, data.from, data.to, data.subject,
          data.text, data.html, data.message_id
        """
        if raw.get("type") != "email.received":
            return None

        data = raw.get("data", {})
        email_id = data.get("email_id", "")
        if not email_id:
            return None

        from_raw = data.get("from", "")
        sender_name, sender_email = self._parse_sender(from_raw)

        to_raw = data.get("to", [])
        if isinstance(to_raw, str):
            to_raw = [to_raw]

        # Extract bare email from first "to" address
        to_address = to_raw[0] if to_raw else ""
        if "<" in to_address and ">" in to_address:
            to_address = to_address.split("<")[1].split(">")[0]
        to_address = to_address.strip().lower()

        # Resolve pack_id from address handle
        handle = to_address.split("@")[0] if "@" in to_address else to_address
        pack_id = handle.replace("-", "_")  # legal-intake -> legal_intake

        # Extract body text
        text = data.get("text", "")
        if not text and data.get("html"):
            text = self._strip_html(data["html"])

        subject = data.get("subject", "")
        if subject and text:
            text = f"Subject: {subject}\n\n{text}"
        elif subject:
            text = f"Subject: {subject}"

        return InboundMessage(
            channel=ChannelType.EMAIL,
            text=text or "(no message body)",
            sender_id=sender_email,
            sender_name=sender_name,
            pack_id=pack_id,
            raw_payload=raw,
            metadata={
                "email_id": email_id,
                "message_id": data.get("message_id", ""),
                "subject": subject,
                "to_address": to_address,
                "handle": handle,
            },
            reply_to_id=data.get("message_id", ""),
        )

    def format_response(self, engine_response: str, inbound: InboundMessage) -> OutboundMessage:
        """Format engine response as branded HTML email."""
        html = self._render_html(engine_response)
        subject = inbound.metadata.get("subject", "")
        handle = inbound.metadata.get("handle", "tmos13")

        return OutboundMessage(
            channel=ChannelType.EMAIL,
            text=engine_response,
            html=html,
            session_id=inbound.session_id,
            recipient_id=inbound.sender_id,
            reply_to_id=inbound.reply_to_id,
            metadata={
                "subject": f"Re: {subject}" if subject and not subject.lower().startswith("re:") else subject,
                "from_handle": handle,
                "from_domain": self.default_domain,
                "original_message_id": inbound.metadata.get("message_id", ""),
            },
        )

    async def deliver(self, outbound: OutboundMessage) -> dict:
        """Send reply email via Resend API."""
        try:
            import httpx
        except ImportError:
            logger.warning("httpx not installed — email delivery unavailable")
            return {"delivered": False, "reason": "httpx not installed"}

        api_key = os.environ.get("RESEND_API_KEY", "")
        if not api_key:
            logger.info(f"Email delivery suppressed (no API key): to={outbound.recipient_id}")
            return {"delivered": False, "reason": "no API key"}

        handle = outbound.metadata.get("from_handle", "tmos13")
        domain = outbound.metadata.get("from_domain", "tmos13.ai")
        from_addr = f"TMOS13 <{handle}@{domain}>"
        subject = outbound.metadata.get("subject", "Re: Your message")

        payload = {
            "from": from_addr,
            "to": [outbound.recipient_id],
            "subject": subject,
            "html": outbound.html,
            "text": outbound.text,
        }

        # Threading headers
        msg_id = outbound.metadata.get("original_message_id", "")
        if msg_id:
            payload["headers"] = {
                "In-Reply-To": msg_id,
                "References": msg_id,
            }

        try:
            async with httpx.AsyncClient(
                base_url="https://api.resend.com",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30.0,
            ) as client:
                resp = await client.post("/emails", json=payload)
                resp.raise_for_status()
                result = resp.json()
                msg_id = result.get("id", "unknown")
                logger.info(f"Email reply sent: to={outbound.recipient_id} id={msg_id}")
                return {"delivered": True, "message_id": msg_id}
        except Exception as e:
            logger.error(f"Email delivery failed: to={outbound.recipient_id} error={e}")
            return {"delivered": False, "reason": str(e)}

    def validate_webhook(self, headers: dict, body: bytes) -> bool:
        """Verify Resend/Svix webhook signature."""
        svix_id = headers.get("svix-id", "")
        svix_timestamp = headers.get("svix-timestamp", "")
        svix_signature = headers.get("svix-signature", "")
        webhook_secret = os.environ.get("RESEND_WEBHOOK_SECRET", "")

        if not all([svix_id, svix_timestamp, svix_signature, webhook_secret]):
            # No secret configured — accept (dev mode)
            return True

        import base64
        import hashlib
        import hmac

        try:
            secret_str = webhook_secret
            if secret_str.startswith("whsec_"):
                secret_str = secret_str[6:]
            secret_bytes = base64.b64decode(secret_str)

            signed_content = f"{svix_id}.{svix_timestamp}.".encode() + body
            expected_sig = base64.b64encode(
                hmac.new(secret_bytes, signed_content, hashlib.sha256).digest()
            ).decode()

            for sig_entry in svix_signature.split(" "):
                sig_entry = sig_entry.strip()
                if sig_entry.startswith("v1,"):
                    candidate = sig_entry[3:]
                    if hmac.compare_digest(expected_sig, candidate):
                        return True
            return False
        except Exception as e:
            logger.error(f"Email webhook verification error: {e}")
            return False

    # ─── Helpers ────────────────────────────────────────────

    @staticmethod
    def _parse_sender(raw: str) -> tuple[str, str]:
        """Extract (name, email) from 'Name <email>' format."""
        if not raw or not raw.strip():
            return ("", "")
        raw = raw.strip()
        match = re.match(r"^(.*?)\s*<([^>]+)>$", raw)
        if match:
            name = match.group(1).strip().strip('"')
            email = match.group(2).strip()
            return (name, email)
        if "@" in raw:
            return ("", raw.strip())
        return ("", "")

    @staticmethod
    def _strip_html(html: str) -> str:
        """Basic HTML-to-text conversion."""
        if not html:
            return ""
        text = html
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</(?:p|div|li|tr|h[1-6])>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        text = text.replace("&nbsp;", " ").replace("&#39;", "'").replace("&quot;", '"')
        text = re.sub(r"[^\S\n]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _render_html(response_text: str, signature: str = "") -> str:
        """Render engine response as branded HTML email."""
        safe_text = (
            response_text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )

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
