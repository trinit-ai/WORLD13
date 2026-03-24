"""
Web Channel Adapter — HTTP REST and WebSocket.

This is the identity adapter: web is the default channel.
Input arrives as JSON from the /chat endpoint or WebSocket;
responses are returned directly (no push delivery needed).
"""

from typing import Optional

from channels.base import (
    ChannelAdapter,
    ChannelCapabilities,
    ChannelType,
    InboundMessage,
    OutboundMessage,
)


class WebAdapter(ChannelAdapter):
    """Web channel: REST /chat and WebSocket /ws."""

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.WEB

    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(
            supports_html=True,
            supports_markdown=True,
            supports_media=True,
            supports_buttons=True,
            supports_forms=True,
            max_message_length=0,  # unlimited
            supports_threading=False,
            supports_typing_indicator=True,
        )

    def parse_inbound(self, raw: dict) -> Optional[InboundMessage]:
        """Parse a /chat request body or WebSocket message."""
        message = raw.get("message", "")
        if not message:
            return None

        return InboundMessage(
            channel=ChannelType.WEB,
            text=message,
            sender_id=raw.get("user_id", "anonymous"),
            session_id=raw.get("session_id", ""),
            pack_id=raw.get("pack_id", ""),
            raw_payload=raw,
        )

    def format_response(self, engine_response: str, inbound: InboundMessage) -> OutboundMessage:
        """Web responses pass through with no transformation."""
        return OutboundMessage(
            channel=ChannelType.WEB,
            text=engine_response,
            session_id=inbound.session_id,
            recipient_id=inbound.sender_id,
        )

    async def deliver(self, outbound: OutboundMessage) -> dict:
        """Web delivery is handled inline by the endpoint — no push needed."""
        return {"delivered": True, "reason": "inline"}
