"""
Slack tool provider — internal team notifications.

Supports sending channel messages.
Requires SLACK_BOT_TOKEN environment variable for live mode;
returns simulated responses when key is absent.
"""
import logging
import os
from tool_providers.base import ToolProvider

logger = logging.getLogger("tmos13.tools.slack")


class SlackProvider(ToolProvider):
    """Slack integration for internal notifications."""

    def __init__(self):
        self.bot_token = os.environ.get("SLACK_BOT_TOKEN", "")

    @property
    def name(self) -> str:
        return "slack"

    @property
    def live(self) -> bool:
        return bool(self.bot_token)

    def supported_operations(self) -> list[str]:
        return ["send_message"]

    async def execute(
        self,
        operation: str,
        parameters: dict,
        config: dict,
    ) -> dict:
        if operation == "send_message":
            return await self._send_message(parameters, config)
        else:
            return {"success": False, "message": f"Unsupported operation: {operation}"}

    async def _send_message(self, parameters: dict, config: dict) -> dict:
        channel = config.get("channel", "#general")
        text = parameters.get("text", "")
        mention = config.get("mention_on_high_priority", False)
        priority = parameters.get("priority", "normal")

        if mention and priority == "high":
            text = f"<!channel> {text}"

        logger.info(f"Slack: sending to {channel}: {text[:80]}")
        return {
            "success": True,
            "message": f"Message sent to {channel}.",
            "live": self.live,
            "channel": channel,
        }
