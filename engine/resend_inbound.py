"""
Resend Inbound — Fetch received email content and verify webhooks.

Thin async wrapper around Resend's received email API.
Does NOT handle business logic — just HTTP calls and parsing.
"""

import base64
import hashlib
import hmac
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger("tmos13.inbound")


# ─── InboundEmail ────────────────────────────────────────────


@dataclass
class InboundEmail:
    """Parsed representation of a received email from Resend webhook."""
    email_id: str
    from_address: str  # raw "Name <email>" string from webhook
    from_email: str    # extracted bare email
    from_name: str     # extracted display name
    to: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    subject: str = ""
    message_id: str = ""  # SMTP Message-ID for threading
    text: Optional[str] = None   # plain text body (fetched separately)
    html: Optional[str] = None   # HTML body (fetched separately)
    attachments: list[dict] = field(default_factory=list)
    created_at: str = ""

    @staticmethod
    def parse_sender(raw: str) -> tuple[str, str]:
        """
        Extract (name, email) from "Name <email>" format.

        Handles:
          - "Jane Doe <jane@example.com>" → ("Jane Doe", "jane@example.com")
          - "jane@example.com" → ("", "jane@example.com")
          - "<jane@example.com>" → ("", "jane@example.com")
          - "" → ("", "")
        """
        if not raw or not raw.strip():
            return ("", "")

        raw = raw.strip()
        match = re.match(r"^(.*?)\s*<([^>]+)>$", raw)
        if match:
            name = match.group(1).strip().strip('"')
            email = match.group(2).strip()
            return (name, email)

        # Bare email — no angle brackets
        if "@" in raw:
            return ("", raw.strip())

        return ("", "")


# ─── ResendInboundClient ─────────────────────────────────────


class ResendInboundClient:
    """Async client for Resend's inbound email API."""

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url="https://api.resend.com",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    async def fetch_email_content(self, email_id: str) -> dict:
        """GET /emails/{email_id} — returns parsed JSON or empty dict on failure."""
        try:
            response = await self._client.get(f"/emails/{email_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch email {email_id}: {e}")
            return {}

    async def parse_webhook(self, payload: dict) -> Optional[InboundEmail]:
        """
        Parse an email.received webhook payload into an InboundEmail.

        Returns None if type != "email.received" or required data is missing.
        """
        if payload.get("type") != "email.received":
            return None

        data = payload.get("data")
        if not data:
            return None

        email_id = data.get("email_id", "")
        if not email_id:
            return None

        from_raw = data.get("from", "")
        name, email = InboundEmail.parse_sender(from_raw)

        # to field can be a list or a string
        to_raw = data.get("to", [])
        if isinstance(to_raw, str):
            to_raw = [to_raw]

        cc_raw = data.get("cc", [])
        if isinstance(cc_raw, str):
            cc_raw = [cc_raw]

        bcc_raw = data.get("bcc", [])
        if isinstance(bcc_raw, str):
            bcc_raw = [bcc_raw]

        return InboundEmail(
            email_id=email_id,
            from_address=from_raw,
            from_email=email,
            from_name=name,
            to=to_raw,
            cc=cc_raw,
            bcc=bcc_raw,
            subject=data.get("subject", ""),
            message_id=data.get("message_id", ""),
            attachments=data.get("attachments", []),
            created_at=payload.get("created_at", ""),
        )

    async def fetch_and_hydrate(self, email: InboundEmail) -> InboundEmail:
        """
        Fetch full email content and populate text/html fields.

        Returns the mutated email. If fetch fails, text and html stay None.
        """
        content = await self.fetch_email_content(email.email_id)
        if content:
            email.text = content.get("text")
            email.html = content.get("html")
        return email

    def verify_signature(
        self,
        payload_body: bytes,
        svix_id: str,
        svix_timestamp: str,
        svix_signature: str,
        webhook_secret: str,
    ) -> bool:
        """
        Verify Resend webhook signature using HMAC-SHA256 per Svix spec.

        The signed content is "{svix_id}.{svix_timestamp}.{payload_body}".
        The secret is base64-encoded after stripping the "whsec_" prefix.
        Compare against each signature in the comma-separated svix_signature
        header (format: "v1,{base64_sig}").

        Returns True if any signature matches.
        """
        try:
            # Strip "whsec_" prefix and decode the secret
            secret_str = webhook_secret
            if secret_str.startswith("whsec_"):
                secret_str = secret_str[6:]
            secret_bytes = base64.b64decode(secret_str)

            # Build the signed content
            signed_content = f"{svix_id}.{svix_timestamp}.".encode() + payload_body

            # Compute expected signature
            expected_sig = base64.b64encode(
                hmac.new(secret_bytes, signed_content, hashlib.sha256).digest()
            ).decode()

            # Svix signatures are space-separated, each in "v1,{base64}" format
            for sig_entry in svix_signature.split(" "):
                sig_entry = sig_entry.strip()
                if sig_entry.startswith("v1,"):
                    candidate = sig_entry[3:]
                    if hmac.compare_digest(expected_sig, candidate):
                        return True

            return False
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False

    async def close(self):
        """Close the httpx client."""
        await self._client.aclose()


# ─── Module-level helpers ────────────────────────────────────

_client: Optional[ResendInboundClient] = None


def init_inbound(api_key: str):
    """Create the global inbound client."""
    global _client
    _client = ResendInboundClient(api_key)
    logger.info("Resend inbound client initialized")


def get_inbound() -> Optional[ResendInboundClient]:
    """Return the global inbound client or None."""
    return _client


def strip_html(html: str) -> str:
    """
    Basic HTML-to-text conversion for email bodies.

    Strips tags, decodes common HTML entities, collapses whitespace.
    Not a full HTML parser — sufficient for extracting conversational
    text from email HTML.
    """
    if not html:
        return ""

    text = html

    # Replace <br>, <br/>, <br /> with newlines
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)

    # Replace </p>, </div>, </li> with newlines for block separation
    text = re.sub(r"</(?:p|div|li|tr|h[1-6])>", "\n", text, flags=re.IGNORECASE)

    # Strip all remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Decode common HTML entities
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&nbsp;", " ")
    text = text.replace("&#39;", "'")
    text = text.replace("&quot;", '"')

    # Collapse multiple whitespace (but preserve newlines)
    text = re.sub(r"[^\S\n]+", " ", text)
    # Collapse multiple newlines into at most two
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
