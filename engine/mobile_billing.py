"""
TMOS13 Mobile Billing — RevenueCat Integration

Wraps App Store and Google Play billing for React Native and native iOS.
Syncs mobile subscriptions with the backend tier system.
"""
import time
import logging
from typing import Optional

from fastapi import HTTPException, Depends
from pydantic import BaseModel

logger = logging.getLogger("tmos13.mobile_billing")


class MobileReceiptRequest(BaseModel):
    platform: str           # "ios" | "android"
    receipt_data: str       # base64 receipt (iOS) or purchase token (Android)
    product_id: str
    user_id: str

class MobileSubscriptionInfo(BaseModel):
    user_id: str
    platform: str
    product_id: str
    is_active: bool
    expires_at: Optional[float] = None
    tier: str = "free"
    store: str = "unknown"

class MobileEntitlement(BaseModel):
    identifier: str
    is_active: bool
    expires_date: Optional[str] = None
    product_identifier: str
    store: str


class RevenueCatService:
    """RevenueCat integration for mobile IAP management."""

    def __init__(self, api_key: str, webhook_secret: str = ""):
        self.api_key = api_key
        self.webhook_secret = webhook_secret
        self._base_url = "https://api.revenuecat.com/v1"
        self._session = None

        if not api_key:
            logger.info("RevenueCat not configured — mobile billing disabled")
            return

        logger.info("RevenueCat mobile billing initialized")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, body: dict = None) -> dict:
        """Make an API request to RevenueCat."""
        import httpx
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient() as client:
            response = await client.request(method, url, headers=self._headers(), json=body)
            response.raise_for_status()
            return response.json()

    async def get_subscriber(self, user_id: str) -> dict:
        """Get subscriber info from RevenueCat."""
        if not self.enabled:
            return {}
        try:
            return await self._request("GET", f"/subscribers/{user_id}")
        except Exception as e:
            logger.error(f"RevenueCat subscriber fetch failed: {e}")
            return {}

    async def validate_receipt(self, req: MobileReceiptRequest) -> MobileSubscriptionInfo:
        """Validate a mobile receipt and sync subscription status."""
        if not self.enabled:
            raise HTTPException(503, "Mobile billing not configured")

        try:
            body = {
                "app_user_id": req.user_id,
                "fetch_token": req.receipt_data,
                "product_id": req.product_id,
            }
            result = await self._request("POST", f"/receipts", body=body)
            subscriber = result.get("subscriber", {})
            entitlements = subscriber.get("entitlements", {})

            is_active = False
            tier = "free"
            expires_at = None

            # Check for active entitlements
            for ent_id, ent in entitlements.items():
                if ent.get("expires_date"):
                    from datetime import datetime
                    exp = datetime.fromisoformat(ent["expires_date"].replace("Z", "+00:00"))
                    if exp.timestamp() > time.time():
                        is_active = True
                        expires_at = exp.timestamp()
                        # Map product to tier
                        if "enterprise" in req.product_id.lower():
                            tier = "enterprise"
                        elif "pro" in req.product_id.lower():
                            tier = "pro"

            return MobileSubscriptionInfo(
                user_id=req.user_id,
                platform=req.platform,
                product_id=req.product_id,
                is_active=is_active,
                expires_at=expires_at,
                tier=tier,
                store="app_store" if req.platform == "ios" else "play_store",
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Receipt validation failed: {e}")
            raise HTTPException(500, "Receipt validation failed")

    async def get_entitlements(self, user_id: str) -> list[MobileEntitlement]:
        """Get active entitlements for a user."""
        if not self.enabled:
            return []

        try:
            data = await self.get_subscriber(user_id)
            subscriber = data.get("subscriber", {})
            entitlements = subscriber.get("entitlements", {})

            return [
                MobileEntitlement(
                    identifier=ent_id,
                    is_active=bool(ent.get("expires_date")),
                    expires_date=ent.get("expires_date"),
                    product_identifier=ent.get("product_identifier", ""),
                    store=ent.get("store", "unknown"),
                )
                for ent_id, ent in entitlements.items()
            ]
        except Exception as e:
            logger.error(f"Entitlements fetch failed: {e}")
            return []

    def handle_webhook(self, event: dict, auth_service=None) -> str:
        """Process RevenueCat webhook events."""
        event_type = event.get("type", "")
        app_user_id = event.get("app_user_id", "")

        logger.info(f"RevenueCat webhook: type={event_type} user={app_user_id}")

        if event_type in ("INITIAL_PURCHASE", "RENEWAL", "PRODUCT_CHANGE"):
            # Upgrade user tier
            product = event.get("product_id", "")
            tier = "pro"
            if "enterprise" in product.lower():
                tier = "enterprise"
            if auth_service and auth_service.enabled and app_user_id:
                try:
                    auth_service._admin_client.table("profiles").update(
                        {"tier": tier, "updated_at": time.time()}
                    ).eq("user_id", app_user_id).execute()
                except Exception as e:
                    logger.error(f"Tier update failed: {e}")
            return f"tier_upgraded:{tier}"

        elif event_type in ("CANCELLATION", "EXPIRATION"):
            # Downgrade to free
            if auth_service and auth_service.enabled and app_user_id:
                try:
                    auth_service._admin_client.table("profiles").update(
                        {"tier": "free", "updated_at": time.time()}
                    ).eq("user_id", app_user_id).execute()
                except Exception as e:
                    logger.error(f"Tier downgrade failed: {e}")
            return "tier_downgraded:free"

        return f"unhandled:{event_type}"


# ─── Module State ───────────────────────────────────────

_rc_service: Optional[RevenueCatService] = None


def init_mobile_billing(api_key: str = "", webhook_secret: str = "") -> RevenueCatService:
    global _rc_service
    _rc_service = RevenueCatService(api_key, webhook_secret)
    return _rc_service


# ─── Endpoint Registration ──────────────────────────────

def register_mobile_billing_endpoints(app, rc_service: RevenueCatService, auth_service=None):
    """Register /mobile-billing/* endpoints."""

    from auth import require_auth, UserProfile
    from fastapi import Request

    @app.post("/mobile-billing/validate", response_model=MobileSubscriptionInfo)
    async def validate_receipt(req: MobileReceiptRequest):
        return await rc_service.validate_receipt(req)

    @app.get("/mobile-billing/entitlements", response_model=list[MobileEntitlement])
    async def get_entitlements(user: UserProfile = Depends(require_auth)):
        return await rc_service.get_entitlements(user.user_id)

    @app.get("/mobile-billing/status")
    async def mobile_billing_status(user: UserProfile = Depends(require_auth)):
        sub = await rc_service.get_subscriber(user.user_id)
        return {"subscriber": sub, "enabled": rc_service.enabled}

    @app.post("/mobile-billing/webhook")
    async def revenuecat_webhook(request: Request):
        body = await request.json()
        event = body.get("event", body)
        result = rc_service.handle_webhook(event, auth_service)
        return {"received": True, "result": result}

    logger.info("Mobile billing endpoints registered: /mobile-billing/*")
