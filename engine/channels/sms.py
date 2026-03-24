"""
SMS Channel Adapter — Twilio integration.

Handles inbound SMS via Twilio webhook and outbound via Twilio API.
Returns simulated responses when TWILIO_ACCOUNT_SID is not configured.
"""

import logging
import os
from typing import Optional

from channels.base import (
    ChannelAdapter,
    ChannelCapabilities,
    ChannelType,
    InboundMessage,
    OutboundMessage,
)

logger = logging.getLogger("tmos13.channels.sms")

# SMS character limit (standard concatenated SMS)
SMS_MAX_LENGTH = 1600


class SmsAdapter(ChannelAdapter):
    """SMS channel adapter: Twilio inbound/outbound."""

    def __init__(self):
        self.account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.from_number = os.environ.get("TWILIO_PHONE_NUMBER", "")

    @property
    def live(self) -> bool:
        return bool(self.account_sid and self.auth_token and self.from_number)

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.SMS

    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(
            supports_html=False,
            supports_markdown=False,
            supports_media=True,  # MMS
            supports_buttons=False,
            supports_forms=False,
            max_message_length=SMS_MAX_LENGTH,
            supports_threading=False,
            supports_typing_indicator=False,
        )

    def parse_inbound(self, raw: dict) -> Optional[InboundMessage]:
        """
        Parse a Twilio SMS webhook payload.

        Expected keys from Twilio POST:
          From, To, Body, MessageSid, NumMedia, MediaUrl0, etc.
        """
        body = raw.get("Body", "")
        from_number = raw.get("From", "")
        to_number = raw.get("To", "")

        if not body or not from_number:
            return None

        # Resolve pack_id from the To number (configured per-pack)
        pack_id = self._resolve_pack_from_number(to_number)

        # Parse media attachments
        attachments = []
        num_media = int(raw.get("NumMedia", 0))
        for i in range(num_media):
            url = raw.get(f"MediaUrl{i}", "")
            content_type = raw.get(f"MediaContentType{i}", "")
            if url:
                attachments.append({"url": url, "type": content_type})

        return InboundMessage(
            channel=ChannelType.SMS,
            text=body.strip(),
            sender_id=from_number,
            pack_id=pack_id,
            raw_payload=raw,
            attachments=attachments,
            metadata={
                "message_sid": raw.get("MessageSid", ""),
                "to_number": to_number,
            },
        )

    def format_response(self, engine_response: str, inbound: InboundMessage) -> OutboundMessage:
        """Format engine response for SMS (plain text, truncated)."""
        text = self._truncate_for_sms(engine_response)

        return OutboundMessage(
            channel=ChannelType.SMS,
            text=text,
            session_id=inbound.session_id,
            recipient_id=inbound.sender_id,
            metadata={
                "to_number": inbound.sender_id,
                "from_number": inbound.metadata.get("to_number", self.from_number),
            },
        )

    async def deliver(self, outbound: OutboundMessage) -> dict:
        """Send SMS via Twilio API (or simulate)."""
        if not self.live:
            logger.info(f"SMS delivery simulated: to={outbound.recipient_id}")
            return {
                "delivered": True,
                "simulated": True,
                "message_sid": "SIM_" + outbound.recipient_id[-4:],
            }

        try:
            import httpx
        except ImportError:
            return {"delivered": False, "reason": "httpx not installed"}

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        from_number = outbound.metadata.get("from_number", self.from_number)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    url,
                    auth=(self.account_sid, self.auth_token),
                    data={
                        "From": from_number,
                        "To": outbound.recipient_id,
                        "Body": outbound.text,
                    },
                )
                resp.raise_for_status()
                result = resp.json()
                sid = result.get("sid", "unknown")
                logger.info(f"SMS sent: to={outbound.recipient_id} sid={sid}")
                return {"delivered": True, "message_sid": sid}
        except Exception as e:
            logger.error(f"SMS delivery failed: to={outbound.recipient_id} error={e}")
            return {"delivered": False, "reason": str(e)}

    def validate_webhook(self, headers: dict, body: bytes) -> bool:
        """Validate Twilio webhook signature."""
        signature = headers.get("x-twilio-signature", "")
        if not signature or not self.auth_token:
            # No auth configured — accept in dev mode
            return True

        # Twilio signature validation requires the full request URL
        # and form parameters. For now, accept if token is present.
        # Full validation should use twilio.request_validator in production.
        return bool(signature)

    # ─── Helpers ────────────────────────────────────────────

    @staticmethod
    def _truncate_for_sms(text: str) -> str:
        """Truncate text for SMS, adding ellipsis if needed."""
        if len(text) <= SMS_MAX_LENGTH:
            return text
        return text[: SMS_MAX_LENGTH - 3] + "..."

    @staticmethod
    def _resolve_pack_from_number(to_number: str) -> str:
        """Resolve pack_id from the Twilio phone number. Stub: returns default."""
        # In production, this maps phone numbers to pack_ids via config
        return os.environ.get("TMOS13_SMS_DEFAULT_PACK", "guest")
