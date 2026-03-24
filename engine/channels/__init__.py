"""
TMOS13 Multi-Channel Pack Execution (OpenClaw Spec 04)

Channel-agnostic adapter layer: the pack engine processes conversations
through a unified pipeline while each channel adapter handles I/O
formatting, webhook parsing, and response delivery.
"""

from channels.base import (
    ChannelAdapter,
    ChannelType,
    InboundMessage,
    OutboundMessage,
    ChannelCapabilities,
)
from channels.web import WebAdapter
from channels.email_adapter import EmailChannelAdapter
from channels.sms import SmsAdapter
from channels.whatsapp import WhatsAppAdapter
from channels.voice import VoiceAdapter

__all__ = [
    "ChannelAdapter",
    "ChannelType",
    "InboundMessage",
    "OutboundMessage",
    "ChannelCapabilities",
    "WebAdapter",
    "EmailChannelAdapter",
    "SmsAdapter",
    "WhatsAppAdapter",
    "VoiceAdapter",
]
