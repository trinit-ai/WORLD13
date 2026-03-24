"""
TMOS13 Pack Pipeline — API Endpoints (Fibonacci Plume Node 5)

POST /api/pipelines/start          — Start a new pipeline
POST /api/pipelines/{id}/approve   — Approve stage advancement
POST /api/pipelines/{id}/cancel    — Cancel pipeline
GET  /api/pipelines/active         — List active pipelines (Dashboard)
GET  /api/pipelines/{id}           — Pipeline instance detail
GET  /api/pipelines/catalog        — List available pipeline definitions
"""
import logging
from typing import Optional

from fastapi import FastAPI, Query
from pydantic import BaseModel

from errors import APIError, ErrorCode

logger = logging.getLogger("tmos13.pipeline.api")


# ─── Pydantic Models ─────────────────────────────────────

class StartPipelineRequest(BaseModel):
    pipeline_id: str
    owner_id: str
    initial_context: Optional[dict] = None


class ApproveRequest(BaseModel):
    approver_id: str


class CancelRequest(BaseModel):
    reason: str = ""


class PipelineResponse(BaseModel):
    pipeline: dict


class PipelineListResponse(BaseModel):
    pipelines: list[dict]
    total: int


class CatalogEntry(BaseModel):
    pipeline_id: str
    stages: list[dict]
    total_stages: int


class CatalogResponse(BaseModel):
    pipelines: list[dict]
    total: int


# ─── Registration ─────────────────────────────────────────

def register_pipeline_endpoints(app: FastAPI, pipeline_service) -> None:
    """Register pack pipeline endpoints on the FastAPI application."""

    @app.post(
        "/api/pipelines/start",
        response_model=PipelineResponse,
        tags=["pipelines"],
        summary="Start a new pipeline",
    )
    async def start_pipeline(req: StartPipelineRequest):
        """Start a new pipeline instance for a user."""
        instance = await pipeline_service.start_pipeline(
            pipeline_id=req.pipeline_id,
            owner_id=req.owner_id,
            initial_context=req.initial_context,
        )
        return {"pipeline": instance.to_dict()}

    @app.post(
        "/api/pipelines/{instance_id}/approve",
        response_model=PipelineResponse,
        tags=["pipelines"],
        summary="Approve stage advancement",
    )
    async def approve_advance(instance_id: str, req: ApproveRequest):
        """Approve a pipeline that is waiting for human approval to advance."""
        instance = await pipeline_service.approve_advance(instance_id, req.approver_id)
        return {"pipeline": instance.to_dict()}

    @app.post(
        "/api/pipelines/{instance_id}/cancel",
        response_model=PipelineResponse,
        tags=["pipelines"],
        summary="Cancel pipeline",
    )
    async def cancel_pipeline(instance_id: str, req: CancelRequest):
        """Cancel an active or waiting pipeline."""
        instance = await pipeline_service.cancel_pipeline(instance_id, req.reason)
        return {"pipeline": instance.to_dict()}

    @app.get(
        "/api/pipelines/active",
        response_model=PipelineListResponse,
        tags=["pipelines"],
        summary="List active pipelines",
    )
    async def list_active_pipelines(
        owner_id: str = Query(..., description="User ID"),
    ):
        """List active/waiting pipelines for a user (Dashboard feed)."""
        instances = await pipeline_service.get_active_pipelines(owner_id)
        return {
            "pipelines": [i.to_dict() for i in instances],
            "total": len(instances),
        }

    @app.get(
        "/api/pipelines/{instance_id}",
        response_model=PipelineResponse,
        tags=["pipelines"],
        summary="Pipeline instance detail",
    )
    async def get_pipeline_instance(instance_id: str):
        """Get full details of a pipeline instance."""
        instance = await pipeline_service.get_instance(instance_id)
        if not instance:
            raise APIError(ErrorCode.NOT_FOUND, f"Pipeline instance {instance_id} not found", 404)
        return {"pipeline": instance.to_dict()}

    @app.get(
        "/api/pipelines/catalog",
        response_model=CatalogResponse,
        tags=["pipelines"],
        summary="List available pipeline definitions",
    )
    async def list_pipeline_catalog():
        """List all discovered pipeline definitions and their stages."""
        catalog = []
        for pid, stages in pipeline_service._stage_catalog.items():
            catalog.append({
                "pipeline_id": pid,
                "stages": [s.to_dict() for s in stages],
                "total_stages": len(stages),
            })
        return {
            "pipelines": catalog,
            "total": len(catalog),
        }
