"""
Channel Manager — Orchestrates the unified multi-channel pipeline.

Manages adapter registration, message routing, and response delivery.
The engine calls `process_inbound()` which:
1. Creates/resumes a session
2. Sets active_channel on state
3. Calls the engine's process_message()
4. Formats the response for the channel
5. Delivers via the channel adapter
"""

import logging
import time
from typing import Callable, Optional

from channels.base import (
    ChannelAdapter,
    ChannelType,
    InboundMessage,
    OutboundMessage,
)
from channels.formatter import format_for_channel

logger = logging.getLogger("tmos13.channels.manager")


class ChannelManager:
    """Manages channel adapters and routes messages through the unified pipeline."""

    def __init__(self):
        self._adapters: dict[str, ChannelAdapter] = {}

    def register(self, adapter: ChannelAdapter):
        """Register a channel adapter."""
        key = adapter.channel_type.value
        self._adapters[key] = adapter
        logger.info(f"Channel adapter registered: {key}")

    def get_adapter(self, channel: str) -> Optional[ChannelAdapter]:
        """Get an adapter by channel name."""
        return self._adapters.get(channel)

    async def process_inbound(
        self,
        inbound: InboundMessage,
        process_message_fn: Callable,
        sessions,
    ) -> dict:
        """
        Unified inbound message processing pipeline.

        1. Get or create session
        2. Set active_channel on state
        3. Call engine's process_message()
        4. Apply channel formatting
        5. Format outbound via adapter
        6. Deliver via adapter
        7. Return result dict
        """
        from state import SessionState

        start_time = time.time()
        adapter = self._adapters.get(inbound.channel.value)
        if not adapter:
            return {
                "error": f"No adapter for channel {inbound.channel.value}",
                "session_id": "",
                "response_text": "",
                "delivered": False,
            }

        # 1. Get or create session
        session_id = inbound.session_id
        state = sessions.get(session_id) if session_id else None

        if state is None:
            # Create session with channel-specific ID prefix
            state = SessionState(
                user_id=inbound.sender_id or f"{inbound.channel.value}:anonymous",
            )
            if inbound.pack_id:
                state.pack_id = inbound.pack_id
            session_id = f"{inbound.channel.value}-{state.session_id}"
            state.session_id = session_id
            sessions.put(state)

        # 2. Set active channel
        state.active_channel = inbound.channel.value

        # Update inbound with resolved session_id
        inbound.session_id = state.session_id

        # 3. Call engine's process_message
        try:
            engine_response = await process_message_fn(inbound.text, state)
        except Exception as e:
            logger.error(f"Engine processing failed for {inbound.channel.value}: {e}")
            engine_response = "Thank you for your message. We've received it and will follow up shortly."

        # 4. Apply channel formatting
        formatted_text = format_for_channel(
            engine_response,
            inbound.channel,
            adapter.capabilities,
        )

        # 5. Format outbound via adapter
        outbound = adapter.format_response(formatted_text, inbound)

        # 6. Deliver
        delivery_result = await adapter.deliver(outbound)

        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(
            f"Channel {inbound.channel.value}: "
            f"session={state.session_id} "
            f"sender={inbound.sender_id} "
            f"delivered={delivery_result.get('delivered', False)} "
            f"duration={duration_ms}ms"
        )

        return {
            "session_id": state.session_id,
            "response_text": formatted_text,
            "delivered": delivery_result.get("delivered", False),
            "delivery_result": delivery_result,
            "duration_ms": duration_ms,
        }

    def get_status(self) -> dict:
        """Return status of all registered channels."""
        channels = {}
        for name, adapter in self._adapters.items():
            live = getattr(adapter, "live", True)  # web is always live
            channels[name] = {
                "registered": True,
                "live": live,
                "capabilities": {
                    "supports_html": adapter.capabilities.supports_html,
                    "supports_markdown": adapter.capabilities.supports_markdown,
                    "supports_media": adapter.capabilities.supports_media,
                    "max_message_length": adapter.capabilities.max_message_length,
                    "supports_threading": adapter.capabilities.supports_threading,
                },
            }
        return {"channels": channels, "count": len(channels)}
