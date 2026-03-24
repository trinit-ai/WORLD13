"""
TMOS13 Architect Pipeline — API Endpoints

GET  /api/architect/profiles                      — List classified profiles
GET  /api/architect/profiles/{id}                 — Get specific profile
GET  /api/architect/suites                        — List suites
GET  /api/architect/suites/{id}                   — Get suite with all artifacts
GET  /api/architect/suites/{id}/artifacts/{spec}  — Get specific artifact
GET  /api/architect/pitches                       — List pitches
GET  /api/architect/pitches/{id}                  — Get specific pitch
PATCH /api/architect/pitches/{id}                 — Update pitch status
GET  /api/architect/stats                         — Combined stats
"""
import logging
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from errors import APIError, ErrorCode

logger = logging.getLogger("tmos13.architect.api")


# ─── Pydantic Models ─────────────────────────────────────

class ProfileResponse(BaseModel):
    profile: dict


class ProfileListResponse(BaseModel):
    profiles: list[dict]
    total: int


class SuiteResponse(BaseModel):
    suite: dict


class SuiteListResponse(BaseModel):
    suites: list[dict]
    total: int


class ArtifactResponse(BaseModel):
    artifact: dict


class PitchResponse(BaseModel):
    pitch: dict


class PitchListResponse(BaseModel):
    pitches: list[dict]
    total: int


class PitchStatusUpdate(BaseModel):
    status: str  # queued | draft | approved | sent | failed


class StatsResponse(BaseModel):
    profiles: dict
    suites: dict
    pitches: dict


# ─── Registration ─────────────────────────────────────────

def register_architect_endpoints(
    app: FastAPI,
    architect_orchestrator,
    classifier,
    pitch_store,
    opportunity_store,
) -> None:
    """Register architect pipeline endpoints on the FastAPI application."""
    from fastapi import Depends
    from auth import require_role, UserProfile

    # ─── Profiles ─────────────────────────────────────

    @app.get(
        "/api/architect/profiles",
        response_model=ProfileListResponse,
        tags=["architect"],
        summary="List classified opportunity profiles",
    )
    async def list_profiles(
        pack_id: Optional[str] = None,
        limit: int = 50,
        user: UserProfile = Depends(require_role("admin")),
    ):
        profiles = opportunity_store.list_profiles(pack_id=pack_id, limit=limit)
        return ProfileListResponse(
            profiles=[p.to_dict() for p in profiles],
            total=len(profiles),
        )

    @app.get(
        "/api/architect/profiles/{profile_id}",
        response_model=ProfileResponse,
        tags=["architect"],
        summary="Get a specific opportunity profile",
    )
    async def get_profile(profile_id: str, user: UserProfile = Depends(require_role("admin"))):
        profile = opportunity_store.get(profile_id)
        if not profile:
            raise APIError(ErrorCode.NOT_FOUND, f"Profile not found: {profile_id}", 404)
        return ProfileResponse(profile=profile.to_dict())

    # ─── Suites ───────────────────────────────────────

    @app.get(
        "/api/architect/suites",
        response_model=SuiteListResponse,
        tags=["architect"],
        summary="List artifact suites",
    )
    async def list_suites(
        user: UserProfile = Depends(require_role("admin")),
        pack_id: Optional[str] = None,
        pitch_ready: Optional[bool] = None,
        limit: int = 50,
    ):
        suites = architect_orchestrator.store.list_suites(
            pack_id=pack_id, pitch_ready=pitch_ready, limit=limit,
        )
        return SuiteListResponse(
            suites=[s.to_dict() for s in suites],
            total=len(suites),
        )

    @app.get(
        "/api/architect/suites/{suite_id}",
        response_model=SuiteResponse,
        tags=["architect"],
        summary="Get suite with all artifacts",
    )
    async def get_suite(suite_id: str, user: UserProfile = Depends(require_role("admin"))):
        suite = architect_orchestrator.get_suite(suite_id)
        if not suite:
            raise APIError(ErrorCode.NOT_FOUND, f"Suite not found: {suite_id}", 404)
        return SuiteResponse(suite=suite.to_dict())

    @app.get(
        "/api/architect/suites/{suite_id}/artifacts/{spec_id}",
        response_model=ArtifactResponse,
        tags=["architect"],
        summary="Get specific artifact with version history",
    )
    async def get_artifact(suite_id: str, spec_id: str, user: UserProfile = Depends(require_role("admin"))):
        suite = architect_orchestrator.get_suite(suite_id)
        if not suite:
            raise APIError(ErrorCode.NOT_FOUND, f"Suite not found: {suite_id}", 404)
        artifact = suite.artifacts.get(spec_id)
        if not artifact:
            raise APIError(ErrorCode.NOT_FOUND, f"Artifact not found: {spec_id}", 404)
        return ArtifactResponse(artifact=artifact.to_dict())

    # ─── Pitches ──────────────────────────────────────

    @app.get(
        "/api/architect/pitches",
        response_model=PitchListResponse,
        tags=["architect"],
        summary="List pitches",
    )
    async def list_pitches(
        user: UserProfile = Depends(require_role("admin")),
        status: Optional[str] = None,
        channel: Optional[str] = None,
        limit: int = 50,
    ):
        pitches = pitch_store.list_pitches(
            status=status, channel=channel, limit=limit,
        )
        return PitchListResponse(
            pitches=[p.to_dict() for p in pitches],
            total=len(pitches),
        )

    @app.get(
        "/api/architect/pitches/{pitch_id}",
        response_model=PitchResponse,
        tags=["architect"],
        summary="Get a specific pitch",
    )
    async def get_pitch(pitch_id: str, user: UserProfile = Depends(require_role("admin"))):
        pitch = pitch_store.get(pitch_id)
        if not pitch:
            raise APIError(ErrorCode.NOT_FOUND, f"Pitch not found: {pitch_id}", 404)
        return PitchResponse(pitch=pitch.to_dict())

    @app.patch(
        "/api/architect/pitches/{pitch_id}",
        response_model=PitchResponse,
        tags=["architect"],
        summary="Update pitch status",
    )
    async def update_pitch_status(pitch_id: str, req: PitchStatusUpdate, user: UserProfile = Depends(require_role("admin"))):
        valid_statuses = {"queued", "draft", "approved", "sent", "failed"}
        if req.status not in valid_statuses:
            raise APIError(
                ErrorCode.VALIDATION_ERROR,
                f"Invalid status: {req.status}. Valid: {valid_statuses}",
                400,
            )
        pitch = pitch_store.update_status(pitch_id, req.status)
        if not pitch:
            raise APIError(ErrorCode.NOT_FOUND, f"Pitch not found: {pitch_id}", 404)
        return PitchResponse(pitch=pitch.to_dict())

    # ─── Stats ────────────────────────────────────────

    @app.get(
        "/api/architect/stats",
        response_model=StatsResponse,
        tags=["architect"],
        summary="Combined architect pipeline stats",
    )
    async def architect_stats(user: UserProfile = Depends(require_role("admin"))):
        return StatsResponse(
            profiles=opportunity_store.get_stats(),
            suites=architect_orchestrator.store.get_stats(),
            pitches=pitch_store.get_stats().__dict__,
        )
