"""
Battle API Endpoints — Agent-to-Agent Protocol (Fibonacci Plume Node 8)

REST endpoints for battle-governed bilateral exchange.
All endpoints require authentication via auth.py dependencies.

Registered by `register_battle_endpoints(app, battle_service)`.
"""
import logging
from typing import Optional

from fastapi import Depends
from pydantic import BaseModel

from auth import require_auth, UserProfile
from battle_service import BattleService

logger = logging.getLogger("tmos13.battle")


# ─── Pydantic Request/Response Models ──────────────────

class CreateBattleRequest(BaseModel):
    exchange_id: str
    initiator_address_id: str
    responder_address_id: str
    authority_boundary: dict
    pp_overrides: Optional[dict] = None
    max_turns: int = 50
    stall_threshold: int = 3


class BattleResponse(BaseModel):
    battle_id: str
    exchange_id: str
    initiator_address_id: str
    responder_address_id: str
    authority_boundary: dict
    pp_state: dict
    transport: str
    outcome: Optional[str]
    stall_count: int
    stall_threshold: int
    max_turns: int
    turn_count: int
    metadata: dict
    created_at: str
    updated_at: str
    user_id: Optional[str]


class ProcessTurnRequest(BaseModel):
    party: str
    move_type: str
    content: str
    actor: str = "ambassador"


class TurnResponse(BaseModel):
    turn_number: int
    party: str
    move_type: str
    move_category: str
    content: str
    phase: str
    timestamp: str
    metadata: dict


class PauseBattleRequest(BaseModel):
    reason: str = ""


class ResolveBattleRequest(BaseModel):
    outcome: str
    resolution_data: Optional[dict] = None
    actor: str = "trainer"


class TrainerActionRequest(BaseModel):
    action: str
    payload: Optional[dict] = None


class BattleListResponse(BaseModel):
    battles: list[dict]
    count: int


# ─── Helpers ──────────────────────────────────────────────

def _battle_response(battle) -> BattleResponse:
    d = battle.to_dict()
    return BattleResponse(
        battle_id=d["battle_id"],
        exchange_id=d["exchange_id"],
        initiator_address_id=d["initiator_address_id"],
        responder_address_id=d["responder_address_id"],
        authority_boundary=d["authority_boundary"],
        pp_state=d["pp_state"],
        transport=d["transport"],
        outcome=d["outcome"],
        stall_count=d["stall_count"],
        stall_threshold=d["stall_threshold"],
        max_turns=d["max_turns"],
        turn_count=d["turn_count"],
        metadata=d["metadata"],
        created_at=d["created_at"],
        updated_at=d["updated_at"],
        user_id=d.get("user_id"),
    )


def _turn_response(turn) -> TurnResponse:
    d = turn.to_dict() if hasattr(turn, "to_dict") else turn
    return TurnResponse(
        turn_number=d["turn_number"],
        party=d["party"],
        move_type=d["move_type"],
        move_category=d["move_category"],
        content=d["content"],
        phase=d["phase"],
        timestamp=d.get("timestamp", ""),
        metadata=d.get("metadata", {}),
    )


# ─── Endpoint Registration ────────────────────────────────

def register_battle_endpoints(app, battle_service: BattleService):
    """Register all /api/battles/* endpoints on the FastAPI app."""

    @app.post("/api/battles", response_model=BattleResponse, tags=["battle"])
    async def create_battle(
        req: CreateBattleRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """Create a new battle linked to an Ambassador exchange."""
        battle = await battle_service.create_battle(
            exchange_id=req.exchange_id,
            initiator_address_id=req.initiator_address_id,
            responder_address_id=req.responder_address_id,
            authority_boundary=req.authority_boundary,
            pp_overrides=req.pp_overrides,
            max_turns=req.max_turns,
            stall_threshold=req.stall_threshold,
            user_id=user.user_id,
        )
        return _battle_response(battle)

    @app.get("/api/battles", response_model=BattleListResponse, tags=["battle"])
    async def list_battles(
        status: Optional[str] = None,
        user: UserProfile = Depends(require_auth),
    ):
        """List battles for the authenticated user."""
        battles = await battle_service.list_battles(
            user_id=user.user_id, status=status,
        )
        return BattleListResponse(battles=battles, count=len(battles))

    @app.get("/api/battles/{battle_id}", response_model=BattleResponse, tags=["battle"])
    async def get_battle(
        battle_id: str,
        user: UserProfile = Depends(require_auth),
    ):
        """Get a battle by ID."""
        battle = await battle_service.get_battle(battle_id)
        if not battle:
            from fastapi import HTTPException
            raise HTTPException(404, f"Battle {battle_id} not found")
        return _battle_response(battle)

    @app.post("/api/battles/{battle_id}/turn", response_model=TurnResponse, tags=["battle"])
    async def process_turn(
        battle_id: str,
        req: ProcessTurnRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """Process a turn in a battle (move_type + content)."""
        turn = await battle_service.process_turn(
            battle_id=battle_id,
            party=req.party,
            move_type=req.move_type,
            content=req.content,
            actor=req.actor,
        )
        return _turn_response(turn)

    @app.post("/api/battles/{battle_id}/pause", response_model=BattleResponse, tags=["battle"])
    async def pause_battle(
        battle_id: str,
        req: PauseBattleRequest = PauseBattleRequest(),
        user: UserProfile = Depends(require_auth),
    ):
        """Pause an active battle."""
        battle = await battle_service.pause_battle(battle_id, reason=req.reason)
        return _battle_response(battle)

    @app.post("/api/battles/{battle_id}/resume", response_model=BattleResponse, tags=["battle"])
    async def resume_battle(
        battle_id: str,
        user: UserProfile = Depends(require_auth),
    ):
        """Resume a paused battle."""
        battle = await battle_service.resume_battle(battle_id)
        return _battle_response(battle)

    @app.post("/api/battles/{battle_id}/resolve", response_model=BattleResponse, tags=["battle"])
    async def resolve_battle(
        battle_id: str,
        req: ResolveBattleRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """Resolve a battle with a final outcome."""
        battle = await battle_service.resolve_battle(
            battle_id=battle_id,
            outcome=req.outcome,
            resolution_data=req.resolution_data,
            actor=req.actor,
        )
        return _battle_response(battle)

    @app.post("/api/battles/{battle_id}/trainer", response_model=TurnResponse, tags=["battle"])
    async def trainer_action(
        battle_id: str,
        req: TrainerActionRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """Execute a trainer-only action (switch/use_item/run)."""
        turn = await battle_service.trainer_action(
            battle_id=battle_id,
            action=req.action,
            payload=req.payload,
        )
        return _turn_response(turn)

    logger.info("Battle endpoints registered: /api/battles/*")
