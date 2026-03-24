"""
TMOS13 Deliverable Feedback — API Endpoints

POST /api/feedback              — Submit feedback (rating + optional comment)
GET  /api/feedback/{id}         — Get feedback for a deliverable
GET  /api/feedback              — List user's feedback
"""
import logging
from typing import Optional

from fastapi import FastAPI, Query, Request
from pydantic import BaseModel, Field

from errors import APIError, ErrorCode

logger = logging.getLogger("tmos13.feedback.api")


# ─── Pydantic Models ─────────────────────────────────────

class FeedbackRequest(BaseModel):
    deliverable_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: str = ""
    section_id: Optional[str] = None


class FeedbackResponse(BaseModel):
    feedback: dict


class FeedbackListResponse(BaseModel):
    feedback: list[dict]
    total: int


# ─── Registration ─────────────────────────────────────────

def register_feedback_endpoints(
    app: FastAPI,
    feedback_service,
) -> None:
    """Register deliverable feedback endpoints on the FastAPI application."""

    @app.post(
        "/api/feedback",
        response_model=FeedbackResponse,
        tags=["feedback"],
        summary="Submit deliverable feedback",
    )
    async def submit_feedback(req: FeedbackRequest, request: Request):
        """Submit a rating and optional comment for a deliverable."""
        user_id = getattr(request.state, "user_id", None)
        if not user_id or user_id == "anonymous":
            raise APIError(ErrorCode.AUTH_REQUIRED, "Authentication required", 401)

        result = feedback_service.submit_feedback(
            deliverable_id=req.deliverable_id,
            user_id=user_id,
            rating=req.rating,
            comment=req.comment,
            section_id=req.section_id,
        )
        if result is None:
            raise APIError(ErrorCode.INTERNAL, "Failed to save feedback", 500)

        return {"feedback": result}

    @app.get(
        "/api/feedback/{deliverable_id}",
        response_model=FeedbackListResponse,
        tags=["feedback"],
        summary="Get feedback for a deliverable",
    )
    async def get_deliverable_feedback(
        deliverable_id: str,
        limit: int = Query(default=20, ge=1, le=100),
    ):
        """List all feedback entries for a specific deliverable."""
        results = feedback_service.get_feedback(
            deliverable_id=deliverable_id,
            limit=limit,
        )
        return {"feedback": results, "total": len(results)}

    @app.get(
        "/api/feedback",
        response_model=FeedbackListResponse,
        tags=["feedback"],
        summary="List user's feedback",
    )
    async def list_user_feedback(
        request: Request,
        limit: int = Query(default=20, ge=1, le=100),
    ):
        """List all feedback submitted by the current user."""
        user_id = getattr(request.state, "user_id", None)
        if not user_id or user_id == "anonymous":
            raise APIError(ErrorCode.AUTH_REQUIRED, "Authentication required", 401)

        results = feedback_service.get_feedback(
            user_id=user_id,
            limit=limit,
        )
        return {"feedback": results, "total": len(results)}
