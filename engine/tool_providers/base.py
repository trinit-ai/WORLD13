"""
Base class for tool providers.

Each provider handles one external service (Calendly, HubSpot, Stripe, etc.)
and exposes a set of operations that the ToolRegistry can dispatch to.
"""
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger("tmos13.tools")


class ToolProvider(ABC):
    """
    Abstract base for external tool integrations.
    Each provider handles one external service.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g. 'calendly', 'hubspot')."""
        ...

    @abstractmethod
    async def execute(
        self,
        operation: str,
        parameters: dict,
        config: dict,
    ) -> dict:
        """
        Execute an operation. Returns provider-specific response data.

        Args:
            operation: The operation to execute (e.g. 'create_event')
            parameters: Operation-specific parameters from the tool request
            config: Tool configuration from the pack manifest

        Returns:
            dict with at least 'success' and 'message' keys.
        """
        ...

    @abstractmethod
    def supported_operations(self) -> list[str]:
        """List operations this provider supports."""
        ...

    def validate_config(self, config: dict) -> bool:
        """Validate provider configuration. Override for stricter checks."""
        return True
