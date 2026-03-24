"""
Channel Adapter Base — Abstract interface for multi-channel I/O.

Every channel (web, email, SMS, WhatsApp, voice) implements this interface.
The engine calls `parse_inbound()` to normalize incoming messages and
`format_response()` to shape outgoing responses for the channel.

SAFETY: Channels do NOT modify engine behavior. They adapt I/O format only.
The pack manifest declares which channels are enabled; the engine enforces it.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger("tmos13.channels")


# ─── Channel Types ─────────────────────────────────────────

class ChannelType(str, Enum):
    WEB = "web"
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    VOICE = "voice"


# ─── Message Dataclasses ───────────────────────────────────

@dataclass
class InboundMessage:
    """Normalized inbound message from any channel."""
    channel: ChannelType
    text: str
    sender_id: str = ""            # channel-specific identifier (email, phone, user_id)
    sender_name: str = ""
    session_id: str = ""           # existing session to resume, or empty for new
    pack_id: str = ""              # target pack (resolved from address/webhook config)
    raw_payload: dict = field(default_factory=dict)   # original webhook/request data
    attachments: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)       # channel-specific metadata
    reply_to_id: str = ""          # message ID to thread replies against
    is_new_thread: bool = True


@dataclass
class OutboundMessage:
    """Formatted outbound response for a specific channel."""
    channel: ChannelType
    text: str                       # plain text response
    html: str = ""                  # HTML-formatted response (email, web)
    session_id: str = ""
    recipient_id: str = ""          # channel-specific recipient (email, phone)
    metadata: dict = field(default_factory=dict)
    reply_to_id: str = ""          # for threading (email Message-ID, WhatsApp msg ID)
    media: list = field(default_factory=list)  # media attachments [{url, type, caption}]


@dataclass
class ChannelCapabilities:
    """Declares what a channel can do — used by assembler for prompt hints."""
    supports_html: bool = False
    supports_markdown: bool = False
    supports_media: bool = False
    supports_buttons: bool = False
    supports_forms: bool = False
    max_message_length: int = 0     # 0 = unlimited
    supports_threading: bool = False
    supports_typing_indicator: bool = False


# ─── Channel Adapter ABC ───────────────────────────────────

class ChannelAdapter(ABC):
    """Abstract base for channel adapters."""

    @property
    @abstractmethod
    def channel_type(self) -> ChannelType:
        """The channel type this adapter handles."""
        ...

    @property
    @abstractmethod
    def capabilities(self) -> ChannelCapabilities:
        """Declare what this channel supports."""
        ...

    @abstractmethod
    def parse_inbound(self, raw: dict) -> Optional[InboundMessage]:
        """
        Parse a raw webhook/request payload into a normalized InboundMessage.
        Returns None if the payload is invalid or should be ignored.
        """
        ...

    @abstractmethod
    def format_response(self, engine_response: str, inbound: InboundMessage) -> OutboundMessage:
        """
        Format the engine's text response for this channel.
        Applies length limits, formatting, and channel-specific structure.
        """
        ...

    async def deliver(self, outbound: OutboundMessage) -> dict:
        """
        Send the outbound message via this channel's API.
        Returns a dict with delivery status.

        Default implementation is a no-op (web channels don't need delivery).
        Override for channels that push responses (email, SMS, WhatsApp).
        """
        return {"delivered": False, "reason": "delivery not implemented"}

    def validate_webhook(self, headers: dict, body: bytes) -> bool:
        """
        Verify webhook signature/authenticity.
        Returns True if valid. Default: no validation (web).
        """
        return True
