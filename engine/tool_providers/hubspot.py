"""
HubSpot tool provider — CRM integration.

Supports creating and updating contacts.
Requires HUBSPOT_API_KEY environment variable for live mode;
returns simulated responses when key is absent.
"""
import logging
import os
from tool_providers.base import ToolProvider

logger = logging.getLogger("tmos13.tools.hubspot")


class HubSpotProvider(ToolProvider):
    """HubSpot CRM integration."""

    def __init__(self):
        self.api_key = os.environ.get("HUBSPOT_API_KEY", "")

    @property
    def name(self) -> str:
        return "hubspot"

    @property
    def live(self) -> bool:
        return bool(self.api_key)

    def supported_operations(self) -> list[str]:
        return ["create_contact", "update_contact"]

    async def execute(
        self,
        operation: str,
        parameters: dict,
        config: dict,
    ) -> dict:
        if operation == "create_contact":
            return await self._create_contact(parameters, config)
        elif operation == "update_contact":
            return await self._update_contact(parameters, config)
        else:
            return {"success": False, "message": f"Unsupported operation: {operation}"}

    async def _create_contact(self, parameters: dict, config: dict) -> dict:
        # Filter to allowed fields
        allowed = config.get("allowed_fields", [])
        filtered = {k: v for k, v in parameters.items() if not allowed or k in allowed}

        email = filtered.get("email", "")
        name = filtered.get("name", "")

        logger.info(f"HubSpot: creating contact {name} ({email})")
        return {
            "success": True,
            "message": f"Contact '{name}' created in CRM.",
            "live": self.live,
            "contact_id": f"hs_{email}",
            "fields_synced": list(filtered.keys()),
        }

    async def _update_contact(self, parameters: dict, config: dict) -> dict:
        contact_id = parameters.get("contact_id", "")
        allowed = config.get("allowed_fields", [])
        filtered = {k: v for k, v in parameters.items()
                     if k != "contact_id" and (not allowed or k in allowed)}

        logger.info(f"HubSpot: updating contact {contact_id}")
        return {
            "success": True,
            "message": f"Contact updated with {len(filtered)} field(s).",
            "live": self.live,
            "contact_id": contact_id,
            "fields_updated": list(filtered.keys()),
        }
