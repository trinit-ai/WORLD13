"""
Channel Response Formatter — Post-processes engine output for channel constraints.

Applied after the engine generates a response, before the channel adapter
formats it for delivery. Handles length truncation, markdown stripping,
and channel-specific content adaptation.
"""

import re
from channels.base import ChannelCapabilities, ChannelType


def format_for_channel(
    text: str,
    channel: ChannelType,
    capabilities: ChannelCapabilities,
) -> str:
    """
    Apply channel-specific formatting to engine output.

    1. Strip markdown if channel doesn't support it
    2. Strip HTML if channel doesn't support it
    3. Truncate to channel's max message length
    4. Clean up whitespace
    """
    result = text

    # Strip markdown for channels that don't support it
    if not capabilities.supports_markdown and not capabilities.supports_html:
        result = strip_markdown(result)

    # Strip HTML tags for non-HTML channels
    if not capabilities.supports_html:
        result = strip_html_tags(result)

    # Truncate if channel has a max length
    if capabilities.max_message_length > 0:
        result = truncate_with_ellipsis(result, capabilities.max_message_length)

    # Clean up whitespace
    result = re.sub(r"\n{3,}", "\n\n", result).strip()

    return result


def strip_markdown(text: str) -> str:
    """Remove common markdown formatting while preserving readability."""
    result = text

    # Bold: **text** or __text__
    result = re.sub(r"\*\*(.+?)\*\*", r"\1", result)
    result = re.sub(r"__(.+?)__", r"\1", result)

    # Italic: *text* or _text_
    result = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", result)

    # Headers: # Header -> Header
    result = re.sub(r"^#{1,6}\s+", "", result, flags=re.MULTILINE)

    # Bullet lists: - item or * item -> item
    result = re.sub(r"^[\-\*]\s+", "- ", result, flags=re.MULTILINE)

    # Links: [text](url) -> text
    result = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", result)

    # Code blocks: ```code``` -> code
    result = re.sub(r"```[\w]*\n?", "", result)

    # Inline code: `code` -> code
    result = re.sub(r"`([^`]+)`", r"\1", result)

    return result


def strip_html_tags(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r"<[^>]+>", "", text)


def truncate_with_ellipsis(text: str, max_length: int) -> str:
    """Truncate text and append ellipsis if over max_length."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."
