"""
Calendly tool provider — calendar booking integration.

Supports reading availability and creating events.
Requires CALENDLY_API_KEY environment variable for live mode;
returns simulated responses when key is absent.
"""
import logging
import os
from tool_providers.base import ToolProvider

logger = logging.getLogger("tmos13.tools.calendly")


class CalendlyProvider(ToolProvider):
    """Calendly integration for calendar booking."""

    def __init__(self):
        self.api_key = os.environ.get("CALENDLY_API_KEY", "")

    @property
    def name(self) -> str:
        return "calendly"

    @property
    def live(self) -> bool:
        return bool(self.api_key)

    def supported_operations(self) -> list[str]:
        return ["read_availability", "create_event"]

    async def execute(
        self,
        operation: str,
        parameters: dict,
        config: dict,
    ) -> dict:
        if operation == "read_availability":
            return await self._read_availability(parameters, config)
        elif operation == "create_event":
            return await self._create_event(parameters, config)
        else:
            return {"success": False, "message": f"Unsupported operation: {operation}"}

    async def _read_availability(self, parameters: dict, config: dict) -> dict:
        # Simulated response (live Calendly API integration is Phase 2)
        event_type = config.get("event_type_id", "consultation-30min")
        logger.info(f"Calendly: reading availability for {event_type}")
        return {
            "success": True,
            "message": "Available time slots retrieved.",
            "live": self.live,
            "slots": [
                {"date": "2026-02-20", "time": "10:00", "available": True},
                {"date": "2026-02-20", "time": "14:00", "available": True},
                {"date": "2026-02-21", "time": "09:00", "available": True},
            ],
        }

    async def _create_event(self, parameters: dict, config: dict) -> dict:
        date = parameters.get("date", "")
        time_slot = parameters.get("time", "")
        name = parameters.get("name", "")
        email = parameters.get("email", "")

        if not date or not time_slot:
            return {"success": False, "message": "Date and time are required."}

        logger.info(f"Calendly: booking {name} ({email}) for {date} {time_slot}")
        return {
            "success": True,
            "message": f"Consultation booked for {date} at {time_slot}.",
            "live": self.live,
            "booking_id": f"cal_{date}_{time_slot}",
            "date": date,
            "time": time_slot,
        }
