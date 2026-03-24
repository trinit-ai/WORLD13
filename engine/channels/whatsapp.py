"""
WhatsApp Channel Adapter — Meta Cloud API integration.

Handles inbound messages via WhatsApp Business webhook and outbound
via Meta Cloud API. Returns simulated responses when
WHATSAPP_ACCESS_TOKEN is not configured.
"""

import logging
import os
import hashlib
import hmac
from typing import Optional

from channels.base import (
    ChannelAdapter,
    ChannelCapabilities,
    ChannelType,
    InboundMessage,
    OutboundMessage,
)

logger = logging.getLogger("tmos13.channels.whatsapp")

# WhatsApp message length limit
WHATSAPP_MAX_LENGTH = 4096


class WhatsAppAdapter(ChannelAdapter):
    """WhatsApp Business channel adapter via Meta Cloud API."""

    def __init__(self):
        self.access_token = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
        self.phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
        self.verify_token = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
        self.app_secret = os.environ.get("WHATSAPP_APP_SECRET", "")

    @property
    def live(self) -> bool:
        return bool(self.access_token and self.phone_number_id)

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.WHATSAPP

    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(
            supports_html=False,
            supports_markdown=True,  # WhatsApp supports basic markdown
            supports_media=True,
            supports_buttons=True,  # interactive messages
            supports_forms=False,
            max_message_length=WHATSAPP_MAX_LENGTH,
            supports_threading=False,
            supports_typing_indicator=True,
        )

    def parse_inbound(self, raw: dict) -> Optional[InboundMessage]:
        """
        Parse a WhatsApp Cloud API webhook payload.

        Webhook structure:
        {
          "entry": [{
            "changes": [{
              "value": {
                "messages": [{
                  "from": "phone",
                  "text": {"body": "message"},
                  "id": "wamid",
                  "type": "text"
                }],
                "contacts": [{"profile": {"name": "Name"}, "wa_id": "phone"}]
              }
            }]
          }]
        }
        """
        try:
            entries = raw.get("entry", [])
            if not entries:
                return None

            changes = entries[0].get("changes", [])
            if not changes:
                return None

            value = changes[0].get("value", {})
            messages = value.get("messages", [])
            if not messages:
                return None

            msg = messages[0]
            msg_type = msg.get("type", "")

            # Extract text from different message types
            if msg_type == "text":
                text = msg.get("text", {}).get("body", "")
            elif msg_type == "interactive":
                interactive = msg.get("interactive", {})
                reply = interactive.get("button_reply", {}) or interactive.get("list_reply", {})
                text = reply.get("title", "") or reply.get("id", "")
            else:
                text = f"[{msg_type} message received]"

            if not text:
                return None

            from_number = msg.get("from", "")
            wa_msg_id = msg.get("id", "")

            # Extract contact name
            contacts = value.get("contacts", [])
            sender_name = ""
            if contacts:
                sender_name = contacts[0].get("profile", {}).get("name", "")

            # Resolve pack_id from phone_number_id
            metadata_phone_id = value.get("metadata", {}).get("phone_number_id", "")
            pack_id = self._resolve_pack(metadata_phone_id)

            return InboundMessage(
                channel=ChannelType.WHATSAPP,
                text=text,
                sender_id=from_number,
                sender_name=sender_name,
                pack_id=pack_id,
                raw_payload=raw,
                metadata={
                    "wa_msg_id": wa_msg_id,
                    "msg_type": msg_type,
                    "phone_number_id": metadata_phone_id,
                },
                reply_to_id=wa_msg_id,
            )
        except (IndexError, KeyError) as e:
            logger.warning(f"WhatsApp parse error: {e}")
            return None

    def format_response(self, engine_response: str, inbound: InboundMessage) -> OutboundMessage:
        """Format engine response for WhatsApp (truncated, basic markdown)."""
        text = self._truncate(engine_response)

        return OutboundMessage(
            channel=ChannelType.WHATSAPP,
            text=text,
            session_id=inbound.session_id,
            recipient_id=inbound.sender_id,
            reply_to_id=inbound.metadata.get("wa_msg_id", ""),
            metadata={
                "phone_number_id": inbound.metadata.get("phone_number_id", self.phone_number_id),
            },
        )

    async def deliver(self, outbound: OutboundMessage) -> dict:
        """Send message via WhatsApp Cloud API (or simulate)."""
        if not self.live:
            logger.info(f"WhatsApp delivery simulated: to={outbound.recipient_id}")
            return {
                "delivered": True,
                "simulated": True,
                "wa_msg_id": "SIM_wa_" + outbound.recipient_id[-4:],
            }

        try:
            import httpx
        except ImportError:
            return {"delivered": False, "reason": "httpx not installed"}

        phone_id = outbound.metadata.get("phone_number_id", self.phone_number_id)
        url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"

        payload = {
            "messaging_product": "whatsapp",
            "to": outbound.recipient_id,
            "type": "text",
            "text": {"body": outbound.text},
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                result = resp.json()
                wa_msg_id = result.get("messages", [{}])[0].get("id", "unknown")
                logger.info(f"WhatsApp sent: to={outbound.recipient_id} id={wa_msg_id}")
                return {"delivered": True, "wa_msg_id": wa_msg_id}
        except Exception as e:
            logger.error(f"WhatsApp delivery failed: to={outbound.recipient_id} error={e}")
            return {"delivered": False, "reason": str(e)}

    def validate_webhook(self, headers: dict, body: bytes) -> bool:
        """Validate WhatsApp/Meta webhook signature."""
        signature = headers.get("x-hub-signature-256", "")
        if not signature or not self.app_secret:
            return True  # dev mode

        try:
            expected = "sha256=" + hmac.new(
                self.app_secret.encode(), body, hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(signature, expected)
        except Exception as e:
            logger.error(f"WhatsApp webhook verification error: {e}")
            return False

    def build_verification_response(self, params: dict) -> Optional[str]:
        """
        Handle WhatsApp webhook verification challenge.
        Returns the hub.challenge value if verification succeeds, None otherwise.
        """
        mode = params.get("hub.mode", "")
        token = params.get("hub.verify_token", "")
        challenge = params.get("hub.challenge", "")

        if mode == "subscribe" and token == self.verify_token:
            return challenge
        return None

    # ─── Helpers ────────────────────────────────────────────

    @staticmethod
    def _truncate(text: str) -> str:
        if len(text) <= WHATSAPP_MAX_LENGTH:
            return text
        return text[: WHATSAPP_MAX_LENGTH - 3] + "..."

    @staticmethod
    def _resolve_pack(phone_number_id: str) -> str:
        """Resolve pack_id from WhatsApp phone number ID. Stub: returns default."""
        return os.environ.get("TMOS13_WHATSAPP_DEFAULT_PACK", "guest")
