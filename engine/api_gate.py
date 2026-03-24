"""
TMOS13 PII Gate API — Pre-flight PII Detection

Endpoints:
  POST /api/gate/check   — Check a message for PII
  GET  /api/gate/config   — Get gate config for a pack
"""

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from pii_gate import get_pii_gate, get_gate_config_from_manifest

logger = logging.getLogger("tmos13.api.gate")


# ─── Request / Response Models ───────────────────────────

class GateCheckRequest(BaseModel):
    message: str
    session_id: str


class PIIDetectionResponse(BaseModel):
    type: str
    value: str
    start: int
    end: int
    confidence: float


class GateCheckResponse(BaseModel):
    mode: str
    detections: list[PIIDetectionResponse]
    action: str
    redacted_text: str | None = None
    rail_id: str | None = None
    original_stored: bool = False


class GateConfigResponse(BaseModel):
    mode: str
    types: list[str]
    custom_patterns: list[dict] = []
    nudge_rail_id: str | None = None


# ─── Registration ────────────────────────────────────────

def register_gate_endpoints(app: FastAPI) -> None:
    """Register PII Gate API endpoints."""

    @app.post(
        "/api/gate/check",
        response_model=GateCheckResponse,
        tags=["pii_gate"],
    )
    async def check_gate(req: GateCheckRequest):
        """
        Run the PII gate on a message. Returns detections and
        the recommended action based on the pack's gate mode.
        """
        from config import get_pack

        gate = get_pii_gate()

        pack = get_pack()
        manifest = pack.manifest if pack else {}
        config = get_gate_config_from_manifest(manifest)

        result = gate.check(req.message, config)

        return GateCheckResponse(
            mode=result.mode,
            detections=[
                PIIDetectionResponse(
                    type=d.pii_type,
                    value=d.value,
                    start=d.start,
                    end=d.end,
                    confidence=d.confidence,
                )
                for d in result.detections
            ],
            action=result.action,
            redacted_text=result.redacted_text,
            rail_id=result.rail_id,
            original_stored=result.original_stored,
        )

    @app.get(
        "/api/gate/config",
        response_model=GateConfigResponse,
        tags=["pii_gate"],
    )
    async def get_gate_config(pack_id: str | None = None):
        """Get the PII gate configuration for a pack."""
        from config import get_pack

        pack = get_pack()
        manifest = pack.manifest if pack else {}
        config = get_gate_config_from_manifest(manifest)

        return GateConfigResponse(
            mode=config.mode,
            types=config.types,
            custom_patterns=config.custom_patterns,
            nudge_rail_id=config.nudge_rail_id,
        )
