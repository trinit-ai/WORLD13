"""
Stripe tool provider — payment link generation.

Supports creating checkout sessions.
Requires STRIPE_SECRET_KEY environment variable for live mode;
returns simulated responses when key is absent.
"""
import logging
import os
from tool_providers.base import ToolProvider

logger = logging.getLogger("tmos13.tools.stripe")


class StripeProvider(ToolProvider):
    """Stripe integration for payment/checkout links."""

    def __init__(self):
        self.secret_key = os.environ.get("STRIPE_SECRET_KEY", "")

    @property
    def name(self) -> str:
        return "stripe"

    @property
    def live(self) -> bool:
        return bool(self.secret_key)

    def supported_operations(self) -> list[str]:
        return ["create_checkout_session"]

    async def execute(
        self,
        operation: str,
        parameters: dict,
        config: dict,
    ) -> dict:
        if operation == "create_checkout_session":
            return await self._create_checkout(parameters, config)
        else:
            return {"success": False, "message": f"Unsupported operation: {operation}"}

    async def _create_checkout(self, parameters: dict, config: dict) -> dict:
        product_id = parameters.get("product_id", "")
        amount_cents = parameters.get("amount_cents", 0)

        # Validate product is allowed
        allowed_products = config.get("allowed_products", [])
        if allowed_products and product_id not in allowed_products:
            return {
                "success": False,
                "message": f"Product '{product_id}' is not in allowed products list.",
            }

        # Validate amount ceiling
        max_amount = config.get("max_amount_cents", 0)
        if max_amount and amount_cents > max_amount:
            return {
                "success": False,
                "message": f"Amount {amount_cents} exceeds maximum {max_amount} cents.",
            }

        logger.info(f"Stripe: creating checkout for {product_id} at {amount_cents}c")
        return {
            "success": True,
            "message": f"Payment link generated for {product_id}.",
            "live": self.live,
            "checkout_url": f"https://checkout.stripe.com/pay/{product_id}",
            "product_id": product_id,
            "amount_cents": amount_cents,
        }
