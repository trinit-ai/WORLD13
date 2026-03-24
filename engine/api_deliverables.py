"""
TMOS13 Deliverable Pipeline — API Endpoints

POST /api/deliverables/evaluate  — Evaluate a session for deliverable generation
GET  /api/deliverables/preview   — Preview extraction progress for an active session
GET  /api/deliverables           — List generated deliverables
GET  /api/deliverables/{id}      — Get a specific deliverable
PATCH /api/deliverables/{id}     — Update deliverable status
GET  /api/deliverables/stats     — Pipeline statistics
"""
import logging
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from errors import APIError, ErrorCode

logger = logging.getLogger("tmos13.deliverables.api")


# ─── Pydantic Models ─────────────────────────────────────

class EvaluateRequest(BaseModel):
    session_id: str
    pack_id: Optional[str] = None


class EvaluateResponse(BaseModel):
    session_id: str
    deliverables_generated: int
    deliverables: list[dict]


class PreviewResponse(BaseModel):
    session_id: str
    specs: list[dict]


class DeliverableResponse(BaseModel):
    deliverable: dict


class DeliverableListResponse(BaseModel):
    deliverables: list[dict]
    total: int


class StatusUpdateRequest(BaseModel):
    status: str  # generated | sent | viewed | archived


class StatsResponse(BaseModel):
    stats: dict


# ─── Registration ─────────────────────────────────────────

def register_deliverable_endpoints(
    app: FastAPI,
    pipeline,
    transcript_store,
    pack_loader_fn,
) -> None:
    """Register deliverable pipeline endpoints on the FastAPI application."""
    from fastapi import Depends
    from auth import require_auth, require_role, UserProfile

    @app.post(
        "/api/deliverables/evaluate",
        response_model=EvaluateResponse,
        tags=["deliverables"],
        summary="Evaluate a session transcript for deliverable generation",
    )
    async def evaluate_session(req: EvaluateRequest, user: UserProfile = Depends(require_role("admin"))):
        """
        Run the deliverable pipeline on a closed session transcript.
        Extracts structured data and generates deliverables if eligible.
        """
        transcript = transcript_store.get(req.session_id)
        if not transcript:
            raise APIError(
                ErrorCode.NOT_FOUND,
                f"Transcript not found: {req.session_id}",
                404,
            )

        # Load pack manifest
        pack_id = req.pack_id or transcript.pack_id
        try:
            pack = pack_loader_fn(pack_id)
            manifest = pack.manifest if hasattr(pack, "manifest") else {}
        except Exception:
            raise APIError(
                ErrorCode.NOT_FOUND,
                f"Pack not found: {pack_id}",
                404,
            )

        results = pipeline.evaluate(transcript, manifest, session_state=None)

        # Tag the transcript with deliverable info for alert integration
        if results:
            if not transcript.classification:
                transcript.classification = {}
            transcript.classification["deliverables_generated"] = [
                {"spec_id": d.spec_id, "name": d.spec_name, "id": d.deliverable_id}
                for d in results
            ]

        return EvaluateResponse(
            session_id=req.session_id,
            deliverables_generated=len(results),
            deliverables=[d.to_dict() for d in results],
        )

    @app.get(
        "/api/deliverables/preview",
        response_model=PreviewResponse,
        tags=["deliverables"],
        summary="Preview extraction progress for an active session",
    )
    async def preview_extraction(session_id: str, pack_id: Optional[str] = None, user: UserProfile = Depends(require_auth)):
        """
        Show real-time extraction progress without generating deliverables.
        Useful for displaying a progress indicator during conversation.
        """
        transcript = transcript_store.get(session_id)
        if not transcript:
            raise APIError(
                ErrorCode.NOT_FOUND,
                f"Transcript not found: {session_id}",
                404,
            )

        pid = pack_id or transcript.pack_id
        try:
            pack = pack_loader_fn(pid)
            manifest = pack.manifest if hasattr(pack, "manifest") else {}
        except Exception:
            raise APIError(ErrorCode.NOT_FOUND, f"Pack not found: {pid}", 404)

        previews = pipeline.extract_preview(transcript, manifest)
        return PreviewResponse(session_id=session_id, specs=previews)

    @app.get(
        "/api/deliverables",
        response_model=DeliverableListResponse,
        tags=["deliverables"],
        summary="List generated deliverables",
    )
    async def list_deliverables(
        user: UserProfile = Depends(require_auth),
        pack_id: Optional[str] = None,
        user_id: Optional[str] = None,
        spec_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ):
        results = pipeline.store.list_deliverables(
            pack_id=pack_id, user_id=user_id,
            spec_id=spec_id, status=status,
            limit=limit, offset=offset,
        )
        return DeliverableListResponse(
            deliverables=[d.to_dict() for d in results],
            total=pipeline.store.count,
        )

    @app.get(
        "/api/deliverables/{deliverable_id}",
        response_model=DeliverableResponse,
        tags=["deliverables"],
        summary="Get a specific deliverable",
    )
    async def get_deliverable(deliverable_id: str, user: UserProfile = Depends(require_auth)):
        d = pipeline.store.get(deliverable_id)
        if not d:
            raise APIError(
                ErrorCode.NOT_FOUND,
                f"Deliverable not found: {deliverable_id}",
                404,
            )
        return DeliverableResponse(deliverable=d.to_dict())

    @app.patch(
        "/api/deliverables/{deliverable_id}",
        response_model=DeliverableResponse,
        tags=["deliverables"],
        summary="Update deliverable status",
    )
    async def update_deliverable_status(deliverable_id: str, req: StatusUpdateRequest, user: UserProfile = Depends(require_role("admin"))):
        valid_statuses = {"generated", "sent", "viewed", "archived"}
        if req.status not in valid_statuses:
            raise APIError(
                ErrorCode.VALIDATION_ERROR,
                f"Invalid status: {req.status}. Valid: {valid_statuses}",
                400,
            )
        d = pipeline.store.update_status(deliverable_id, req.status)
        if not d:
            raise APIError(
                ErrorCode.NOT_FOUND,
                f"Deliverable not found: {deliverable_id}",
                404,
            )
        return DeliverableResponse(deliverable=d.to_dict())

    @app.get(
        "/api/deliverables/stats",
        response_model=StatsResponse,
        tags=["deliverables"],
        summary="Deliverable pipeline statistics",
    )
    async def deliverable_stats(user: UserProfile = Depends(require_role("admin"))):
        return StatsResponse(stats=pipeline.store.get_stats())
