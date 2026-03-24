"""
TMOS13 Delivery Pipeline — API Endpoints (Fibonacci Plume Node 4)

POST /api/deliveries/{deliverable_id}/send  — Create delivery intent
POST /api/deliveries/{delivery_id}/approve  — Approve staged delivery
POST /api/deliveries/{delivery_id}/cancel   — Cancel pending delivery
GET  /api/deliveries/pending                — List pending approvals
GET  /api/deliveries/{delivery_id}/status   — Check delivery status
"""
import logging
from typing import Optional

from fastapi import FastAPI, Query
from pydantic import BaseModel

from errors import APIError, ErrorCode

logger = logging.getLogger("tmos13.delivery.api")


# ─── Pydantic Models ─────────────────────────────────────

class SendRequest(BaseModel):
    recipient_type: str = "email"          # email | ambassador | webhook | internal
    recipient_address: Optional[str] = None
    recipient_name: Optional[str] = None
    mode: Optional[str] = None             # auto | staged | manual (None = use config default)
    is_ai_session: bool = False


class ApproveRequest(BaseModel):
    approved_by: str


class DeliveryResponse(BaseModel):
    delivery: dict


class DeliveryListResponse(BaseModel):
    deliveries: list[dict]
    total: int


# ─── Registration ─────────────────────────────────────────

def register_delivery_endpoints(
    app: FastAPI,
    delivery_service,
    deliverable_store,
) -> None:
    """Register delivery pipeline endpoints on the FastAPI application."""

    @app.post(
        "/api/deliveries/{deliverable_id}/send",
        response_model=DeliveryResponse,
        tags=["deliveries"],
        summary="Create a delivery intent for a deliverable",
    )
    async def create_delivery(deliverable_id: str, req: SendRequest):
        """
        Create delivery intent(s) for a generated deliverable.
        AI sessions force staged mode regardless of request.
        """
        # Look up the deliverable
        deliverable = deliverable_store.get(deliverable_id)
        if not deliverable:
            raise APIError(ErrorCode.NOT_FOUND, f"Deliverable {deliverable_id} not found", 404)

        # Override channels with request
        if req.recipient_type:
            deliverable.channels = [req.recipient_type]
        if req.recipient_address:
            if not deliverable.contact_info:
                deliverable.contact_info = {}
            deliverable.contact_info["email"] = req.recipient_address
            deliverable.contact_info["ambassador_address"] = req.recipient_address

        # Build delivery config from request overrides
        delivery_config = {}
        if req.mode:
            delivery_config["default_mode"] = req.mode
        delivery_config["allowed_recipients"] = [req.recipient_type]
        delivery_config["require_approval_for_ai_sessions"] = True

        intents = delivery_service.create_intent(
            deliverable, delivery_config, is_ai=req.is_ai_session,
        )

        if not intents:
            raise APIError(ErrorCode.INTERNAL_ERROR, "No delivery intents created", 500)

        return {"delivery": intents[0].to_dict()}

    @app.post(
        "/api/deliveries/{delivery_id}/approve",
        response_model=DeliveryResponse,
        tags=["deliveries"],
        summary="Approve a staged delivery",
    )
    async def approve_delivery(delivery_id: str, req: ApproveRequest):
        """Approve a pending staged delivery and dispatch it."""
        intent = delivery_service.approve(delivery_id, req.approved_by)
        return {"delivery": intent.to_dict()}

    @app.post(
        "/api/deliveries/{delivery_id}/cancel",
        response_model=DeliveryResponse,
        tags=["deliveries"],
        summary="Cancel a pending delivery",
    )
    async def cancel_delivery(delivery_id: str):
        """Cancel a pending or approved delivery."""
        intent = delivery_service.cancel(delivery_id)
        return {"delivery": intent.to_dict()}

    @app.get(
        "/api/deliveries/pending",
        response_model=DeliveryListResponse,
        tags=["deliveries"],
        summary="List pending delivery approvals",
    )
    async def list_pending_deliveries(
        user_id: Optional[str] = Query(None),
        pack_id: Optional[str] = Query(None),
    ):
        """List pending delivery intents for the dashboard feed."""
        intents = delivery_service.list_pending(user_id=user_id, pack_id=pack_id)
        return {
            "deliveries": [i.to_dict() for i in intents],
            "total": len(intents),
        }

    @app.get(
        "/api/deliveries/{delivery_id}/status",
        response_model=DeliveryResponse,
        tags=["deliveries"],
        summary="Check delivery status",
    )
    async def get_delivery_status(delivery_id: str):
        """Get the current status of a delivery intent."""
        intent = delivery_service.get_intent(delivery_id)
        return {"delivery": intent.to_dict()}
