"""
TMOS13 Billing — Stripe Integration

Full e-commerce support: subscriptions, one-time purchases,
checkout sessions, customer portal, and webhook processing.
"""
import time
import json
import hmac
import hashlib
import logging
from typing import Optional

from fastapi import Request, HTTPException, Depends, Header
from pydantic import BaseModel

logger = logging.getLogger("tmos13.billing")


# ─── Models ─────────────────────────────────────────────

class ProductInfo(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    tier: Optional[str] = None
    features: list[str] = []

class PriceInfo(BaseModel):
    id: str
    product_id: str
    amount: int              # cents
    currency: str = "usd"
    interval: Optional[str] = None  # month | year | None for one-time
    interval_count: int = 1

class PlanInfo(BaseModel):
    product: ProductInfo
    prices: list[PriceInfo]

class CheckoutRequest(BaseModel):
    price_id: str
    success_url: str = "https://tmos13.ai/dashboard/billing?checkout=success"
    cancel_url: str = "https://tmos13.ai/pricing"
    mode: str = "subscription"  # subscription | payment

class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str

class SubscriptionInfo(BaseModel):
    id: str
    status: str              # active | past_due | canceled | trialing | incomplete
    tier: str
    current_period_start: float
    current_period_end: float
    cancel_at_period_end: bool = False
    price_id: Optional[str] = None

class PortalResponse(BaseModel):
    url: str

class OrderInfo(BaseModel):
    id: str
    user_id: str
    amount: int
    currency: str
    status: str
    product_name: str
    created_at: float

class BillingOverview(BaseModel):
    subscription: Optional[SubscriptionInfo] = None
    orders: list[OrderInfo] = []
    tier: str = "free"


# ─── Billing Service ───────────────────────────────────

class BillingService:
    """Wraps Stripe SDK for subscription and payment management."""

    def __init__(self, secret_key: str, webhook_secret: str, public_key: str = ""):
        self.secret_key = secret_key
        self.webhook_secret = webhook_secret
        self.public_key = public_key
        self._stripe = None

        if secret_key:
            import stripe
            stripe.api_key = secret_key
            self._stripe = stripe
            logger.info("Billing service initialized with Stripe")
        else:
            logger.warning("Billing service: Stripe not configured — billing features disabled")

    @property
    def enabled(self) -> bool:
        return self._stripe is not None

    def _require_stripe(self):
        if not self.enabled:
            raise HTTPException(503, "Billing service unavailable")

    # ─── Products & Prices ───────────────────────────────

    def list_plans(self) -> list[PlanInfo]:
        """List all active products with their prices."""
        self._require_stripe()

        products = self._stripe.Product.list(active=True, limit=20)
        plans = []

        for product in products.data:
            prices = self._stripe.Price.list(product=product.id, active=True, limit=10)
            plans.append(PlanInfo(
                product=ProductInfo(
                    id=product.id,
                    name=product.name,
                    description=product.description,
                    tier=product.metadata.get("tier", "pro"),
                    features=json.loads(product.metadata.get("features", "[]")),
                ),
                prices=[
                    PriceInfo(
                        id=price.id,
                        product_id=product.id,
                        amount=price.unit_amount or 0,
                        currency=price.currency,
                        interval=price.recurring.interval if price.recurring else None,
                        interval_count=price.recurring.interval_count if price.recurring else 1,
                    )
                    for price in prices.data
                ],
            ))

        return plans

    # ─── Checkout ────────────────────────────────────────

    def create_checkout(self, user_id: str, email: str, req: CheckoutRequest) -> CheckoutResponse:
        """Create a Stripe Checkout Session."""
        self._require_stripe()

        # Get or create Stripe customer
        customer_id = self._get_or_create_customer(user_id, email)

        try:
            session_params = {
                "customer": customer_id,
                "line_items": [{"price": req.price_id, "quantity": 1}],
                "mode": req.mode,
                "success_url": req.success_url + "?session_id={CHECKOUT_SESSION_ID}",
                "cancel_url": req.cancel_url,
                "metadata": {"user_id": user_id},
                "client_reference_id": user_id,
            }

            if req.mode == "subscription":
                session_params["subscription_data"] = {
                    "metadata": {"user_id": user_id},
                }

            session = self._stripe.checkout.Session.create(**session_params)

            return CheckoutResponse(
                checkout_url=session.url,
                session_id=session.id,
            )
        except Exception as e:
            logger.error(f"Checkout creation failed: {e}")
            raise HTTPException(500, "Failed to create checkout session")

    # ─── Subscriptions ───────────────────────────────────

    def get_subscription(self, user_id: str) -> Optional[SubscriptionInfo]:
        """Get the active subscription for a user."""
        self._require_stripe()

        customer_id = self._find_customer(user_id)
        if not customer_id:
            return None

        subs = self._stripe.Subscription.list(customer=customer_id, status="all", limit=1)
        if not subs.data:
            return None

        sub = subs.data[0]
        tier = sub.metadata.get("tier", "pro")

        return SubscriptionInfo(
            id=sub.id,
            status=sub.status,
            tier=tier,
            current_period_start=sub.current_period_start,
            current_period_end=sub.current_period_end,
            cancel_at_period_end=sub.cancel_at_period_end,
            price_id=sub.items.data[0].price.id if sub.items.data else None,
        )

    def cancel_subscription(self, user_id: str) -> SubscriptionInfo:
        """Cancel a subscription at end of current period."""
        self._require_stripe()

        sub = self.get_subscription(user_id)
        if not sub:
            raise HTTPException(404, "No active subscription found")

        updated = self._stripe.Subscription.modify(
            sub.id,
            cancel_at_period_end=True,
        )

        return SubscriptionInfo(
            id=updated.id,
            status=updated.status,
            tier=sub.tier,
            current_period_start=updated.current_period_start,
            current_period_end=updated.current_period_end,
            cancel_at_period_end=True,
            price_id=sub.price_id,
        )

    def resume_subscription(self, user_id: str) -> SubscriptionInfo:
        """Resume a subscription that was set to cancel at period end."""
        self._require_stripe()

        sub = self.get_subscription(user_id)
        if not sub:
            raise HTTPException(404, "No subscription found")

        updated = self._stripe.Subscription.modify(
            sub.id,
            cancel_at_period_end=False,
        )

        return SubscriptionInfo(
            id=updated.id,
            status=updated.status,
            tier=sub.tier,
            current_period_start=updated.current_period_start,
            current_period_end=updated.current_period_end,
            cancel_at_period_end=False,
            price_id=sub.price_id,
        )

    # ─── Customer Portal ─────────────────────────────────

    def create_portal_session(self, user_id: str, return_url: str = "https://tmos13.ai/dashboard/billing") -> PortalResponse:
        """Create a Stripe Customer Portal session for self-service management."""
        self._require_stripe()

        customer_id = self._find_customer(user_id)
        if not customer_id:
            raise HTTPException(404, "No billing account found. Make a purchase first.")

        session = self._stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )

        return PortalResponse(url=session.url)

    # ─── Orders ──────────────────────────────────────────

    def get_orders(self, user_id: str, db) -> list[OrderInfo]:
        """Get order history from database."""
        if not db:
            return []
        try:
            if hasattr(db, 'client'):
                result = db.client.table("orders").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(50).execute()
                return [
                    OrderInfo(
                        id=o["id"],
                        user_id=o["user_id"],
                        amount=o["amount"],
                        currency=o.get("currency", "usd"),
                        status=o["status"],
                        product_name=o.get("product_name", ""),
                        created_at=o["created_at"],
                    )
                    for o in result.data
                ]
            else:
                rows = db.conn.execute(
                    "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
                    (user_id,)
                ).fetchall()
                return [
                    OrderInfo(
                        id=r[0], user_id=r[1], amount=r[2], currency=r[3],
                        status=r[4], product_name=r[5], created_at=r[6],
                    )
                    for r in rows
                ]
        except Exception as e:
            logger.error(f"Failed to fetch orders: {e}")
            return []

    # ─── Billing Overview ────────────────────────────────

    def get_overview(self, user_id: str, db) -> BillingOverview:
        """Get complete billing overview for a user."""
        subscription = None
        if self.enabled:
            subscription = self.get_subscription(user_id)

        orders = self.get_orders(user_id, db)
        tier = subscription.tier if subscription and subscription.status == "active" else "free"

        return BillingOverview(
            subscription=subscription,
            orders=orders,
            tier=tier,
        )

    # ─── Webhook Processing ──────────────────────────────

    def verify_webhook(self, payload: bytes, signature: str) -> dict:
        """Verify and parse a Stripe webhook event."""
        self._require_stripe()

        try:
            event = self._stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            return event
        except self._stripe.error.SignatureVerificationError:
            raise HTTPException(400, "Invalid webhook signature")
        except Exception as e:
            logger.error(f"Webhook verification failed: {e}")
            raise HTTPException(400, "Webhook processing failed")

    def handle_webhook_event(self, event: dict, db, auth_service) -> str:
        """Process a verified Stripe webhook event."""
        event_type = event["type"]
        data = event["data"]["object"]

        logger.info(f"Processing webhook: {event_type}")

        if event_type == "checkout.session.completed":
            return self._handle_checkout_completed(data, db, auth_service)
        elif event_type == "customer.subscription.updated":
            return self._handle_subscription_updated(data, db, auth_service)
        elif event_type == "customer.subscription.deleted":
            return self._handle_subscription_deleted(data, db, auth_service)
        elif event_type == "invoice.payment_succeeded":
            return self._handle_payment_succeeded(data, db)
        elif event_type == "invoice.payment_failed":
            return self._handle_payment_failed(data, db)
        else:
            logger.info(f"Unhandled webhook event: {event_type}")
            return f"unhandled:{event_type}"

    def _handle_checkout_completed(self, session: dict, db, auth_service) -> str:
        """Process successful checkout."""
        user_id = session.get("client_reference_id") or session.get("metadata", {}).get("user_id")
        mode = session.get("mode")

        if mode == "subscription":
            # Tier upgrade handled by subscription.updated webhook
            logger.info(f"Checkout completed: subscription for user {user_id}")
        elif mode == "payment":
            # Check if this is a pack install purchase (Node 12)
            pack_id = session.get("metadata", {}).get("pack_id")
            if pack_id and user_id:
                from pack_install_service import get_pack_install_service
                svc = get_pack_install_service()
                if svc:
                    svc.complete_stripe_install(user_id, pack_id, session.get("id", ""))
                    logger.info(f"Pack install completed via Stripe: user={user_id} pack={pack_id}")
            # One-time purchase order recording
            if db and user_id:
                self._record_order(db, user_id, session)
            logger.info(f"Checkout completed: one-time payment for user {user_id}")

        return "checkout_completed"

    def _handle_subscription_updated(self, subscription: dict, db, auth_service) -> str:
        """Update user tier when subscription changes."""
        user_id = subscription.get("metadata", {}).get("user_id")
        status = subscription.get("status")
        tier = subscription.get("metadata", {}).get("tier", "pro")

        if user_id and auth_service and auth_service.enabled:
            if status == "active":
                self._update_user_tier(auth_service, user_id, tier)
            elif status in ("canceled", "unpaid"):
                self._update_user_tier(auth_service, user_id, "free")

        logger.info(f"Subscription updated: user={user_id} status={status} tier={tier}")
        return "subscription_updated"

    def _handle_subscription_deleted(self, subscription: dict, db, auth_service) -> str:
        """Downgrade user when subscription is fully cancelled."""
        user_id = subscription.get("metadata", {}).get("user_id")

        if user_id and auth_service and auth_service.enabled:
            self._update_user_tier(auth_service, user_id, "free")

        logger.info(f"Subscription deleted: user={user_id}")
        return "subscription_deleted"

    def _handle_payment_succeeded(self, invoice: dict, db) -> str:
        """Record successful payment."""
        customer_id = invoice.get("customer")
        amount = invoice.get("amount_paid", 0)
        logger.info(f"Payment succeeded: customer={customer_id} amount={amount}")
        return "payment_succeeded"

    def _handle_payment_failed(self, invoice: dict, db) -> str:
        """Handle failed payment."""
        customer_id = invoice.get("customer")
        logger.warning(f"Payment failed: customer={customer_id}")
        return "payment_failed"

    # ─── Internal Helpers ────────────────────────────────

    def _get_or_create_customer(self, user_id: str, email: str) -> str:
        """Find or create a Stripe customer for this user."""
        existing = self._find_customer(user_id)
        if existing:
            return existing

        customer = self._stripe.Customer.create(
            email=email,
            metadata={"user_id": user_id},
        )
        return customer.id

    def _find_customer(self, user_id: str) -> Optional[str]:
        """Find a Stripe customer by user_id metadata."""
        customers = self._stripe.Customer.search(
            query=f'metadata["user_id"]:"{user_id}"',
            limit=1,
        )
        if customers.data:
            return customers.data[0].id
        return None

    def _update_user_tier(self, auth_service, user_id: str, tier: str):
        """Update user tier in profiles table."""
        try:
            if auth_service._admin_client:
                auth_service._admin_client.table("profiles").update(
                    {"tier": tier, "updated_at": time.time()}
                ).eq("user_id", user_id).execute()
        except Exception as e:
            logger.error(f"Failed to update user tier: {e}")

    def _record_order(self, db, user_id: str, session: dict):
        """Record a one-time purchase order."""
        try:
            order_data = {
                "id": session.get("id", ""),
                "user_id": user_id,
                "amount": session.get("amount_total", 0),
                "currency": session.get("currency", "usd"),
                "status": "completed",
                "product_name": "One-time purchase",
                "created_at": time.time(),
                "stripe_session_id": session.get("id"),
            }
            if hasattr(db, 'client'):
                db.client.table("orders").insert(order_data).execute()
            else:
                db.conn.execute(
                    """INSERT INTO orders (id, user_id, amount, currency, status, product_name, created_at, stripe_session_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (order_data["id"], user_id, order_data["amount"], order_data["currency"],
                     order_data["status"], order_data["product_name"], order_data["created_at"],
                     order_data["stripe_session_id"]),
                )
                db.conn.commit()
        except Exception as e:
            logger.error(f"Failed to record order: {e}")


# ─── Module-Level State ─────────────────────────────────

_billing_service: Optional[BillingService] = None


def init_billing_service(secret_key: str, webhook_secret: str, public_key: str = "") -> BillingService:
    """Initialize the global billing service. Called during app lifespan."""
    global _billing_service
    _billing_service = BillingService(secret_key, webhook_secret, public_key)
    return _billing_service


# ─── Endpoint Registration ──────────────────────────────

def register_billing_endpoints(app, billing_service: BillingService, db, auth_service):
    """Register all /billing/* endpoints on the FastAPI app."""

    from auth import require_auth, UserProfile

    @app.get("/billing/plans", response_model=list[PlanInfo])
    async def list_plans():
        """List all available subscription plans and products."""
        return billing_service.list_plans()

    @app.post("/billing/checkout", response_model=CheckoutResponse)
    async def create_checkout(req: CheckoutRequest, user: UserProfile = Depends(require_auth)):
        """Create a Stripe Checkout Session."""
        return billing_service.create_checkout(user.user_id, user.email or "", req)

    @app.get("/billing/subscription", response_model=Optional[SubscriptionInfo])
    async def get_subscription(user: UserProfile = Depends(require_auth)):
        """Get the current user's subscription status."""
        return billing_service.get_subscription(user.user_id)

    @app.post("/billing/subscription/cancel", response_model=SubscriptionInfo)
    async def cancel_subscription(user: UserProfile = Depends(require_auth)):
        """Cancel subscription at end of current billing period."""
        return billing_service.cancel_subscription(user.user_id)

    @app.post("/billing/subscription/resume", response_model=SubscriptionInfo)
    async def resume_subscription(user: UserProfile = Depends(require_auth)):
        """Resume a subscription that was set to cancel."""
        return billing_service.resume_subscription(user.user_id)

    @app.post("/billing/portal", response_model=PortalResponse)
    async def customer_portal(
        return_url: str = "https://tmos13.ai/dashboard/billing",
        user: UserProfile = Depends(require_auth),
    ):
        """Open Stripe Customer Portal for self-service billing management."""
        return billing_service.create_portal_session(user.user_id, return_url)

    @app.get("/billing/overview", response_model=BillingOverview)
    async def billing_overview(user: UserProfile = Depends(require_auth)):
        """Get complete billing overview: subscription, orders, tier."""
        return billing_service.get_overview(user.user_id, db)

    @app.get("/billing/orders", response_model=list[OrderInfo])
    async def list_orders(user: UserProfile = Depends(require_auth)):
        """Get order history for the current user."""
        return billing_service.get_orders(user.user_id, db)

    @app.post("/billing/webhook")
    async def stripe_webhook(request: Request, stripe_signature: str = Header(alias="stripe-signature")):
        """Stripe webhook endpoint — receives and processes events."""
        payload = await request.body()
        event = billing_service.verify_webhook(payload, stripe_signature)
        result = billing_service.handle_webhook_event(event, db, auth_service)
        return {"received": True, "result": result}

    logger.info("Billing endpoints registered: /billing/*")
