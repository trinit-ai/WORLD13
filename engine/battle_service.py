"""
Battle Service — Agent-to-Agent Protocol (Fibonacci Plume Node 8)

Singleton service implementing the 5-phase turn engine for
battle-governed bilateral exchange between AI Ambassadors.

Pattern follows ambassador_service.py.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException

from battle_moves import (
    MoveType, MoveCategory, MOVE_CONFIG,
    PPTracker, PPExhausted,
    is_trainer_move, get_category, format_move_marker,
)
from battle_state import (
    BattleState, BattlePhase, BattleOutcome,
    AuthorityBoundary, BattleTurn,
)

logger = logging.getLogger("tmos13.battle")


class BattleService:
    """Service layer for battle-governed bilateral exchanges."""

    def __init__(self, db=None):
        self._db = db
        self._battles: dict[str, BattleState] = {}
        logger.info("Battle service initialized")

    # ─── Battle Lifecycle ────────────────────────────────────

    async def create_battle(
        self,
        exchange_id: str,
        initiator_address_id: str,
        responder_address_id: str,
        authority_boundary: dict,
        pp_overrides: dict | None = None,
        max_turns: int = 50,
        stall_threshold: int = 3,
        user_id: str | None = None,
    ) -> BattleState:
        """Create a new battle linked to an Ambassador exchange."""
        battle_id = f"battle_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        boundary = AuthorityBoundary.from_dict(authority_boundary)
        pp_tracker = PPTracker(overrides=pp_overrides)

        battle = BattleState(
            battle_id=battle_id,
            exchange_id=exchange_id,
            initiator_address_id=initiator_address_id,
            responder_address_id=responder_address_id,
            authority_boundary=boundary,
            pp_tracker=pp_tracker,
            max_turns=max_turns,
            stall_threshold=stall_threshold,
            created_at=now,
            updated_at=now,
            user_id=user_id,
        )

        self._battles[battle_id] = battle
        await self._persist_battle(battle)

        logger.info(
            "Battle created: %s (exchange=%s, max_turns=%d)",
            battle_id, exchange_id, max_turns,
        )
        return battle

    async def get_battle(self, battle_id: str) -> BattleState | None:
        """Get a battle by ID. Returns None if not found."""
        return self._battles.get(battle_id)

    async def get_battle_by_exchange(self, exchange_id: str) -> BattleState | None:
        """Get the active battle for an exchange. Returns None if not found."""
        for battle in self._battles.values():
            if battle.exchange_id == exchange_id:
                return battle
        return None

    # ─── 5-Phase Turn Engine ─────────────────────────────────

    async def process_turn(
        self,
        battle_id: str,
        party: str,
        move_type: str,
        content: str,
        actor: str = "ambassador",
    ) -> BattleTurn:
        """
        Process a single turn through the 5-phase pipeline.

        Phase 1 — RECEIVE: validate move marker, parse move type
        Phase 2 — EVALUATE: check authority boundary, check PP
        Phase 3 — SELECT: validate move is available (PP, category)
        Phase 4 — GENERATE: attach move marker to content
        Phase 5 — TRANSMIT: record turn, update state, check stall
        """
        battle = self._battles.get(battle_id)
        if not battle:
            raise HTTPException(404, f"Battle {battle_id} not found")

        if not battle.is_active:
            raise HTTPException(
                400,
                f"Battle {battle_id} is not active (transport={battle.transport}, "
                f"outcome={battle.outcome})",
            )

        if battle.current_turn >= battle.max_turns:
            await self.resolve_battle(battle_id, BattleOutcome.TIMEOUT.value)
            raise HTTPException(400, f"Battle {battle_id} has reached max turns")

        # Phase 1 — RECEIVE
        try:
            move = MoveType(move_type)
        except ValueError:
            raise HTTPException(400, f"Invalid move type: {move_type}")

        # Phase 2 — EVALUATE
        if is_trainer_move(move) and actor != "trainer":
            raise HTTPException(
                403,
                f"Move {move.value} requires trainer authorization",
            )

        if not battle.authority_boundary.allows_move(move) and actor != "trainer":
            raise HTTPException(
                403,
                f"Move {move.value} is not authorized by authority boundary",
            )

        # Phase 3 — SELECT
        if not battle.pp_tracker.can_use(move):
            raise HTTPException(
                400,
                f"Move {move.value} has no remaining PP",
            )

        try:
            battle.pp_tracker.use(move)
        except PPExhausted:
            raise HTTPException(400, f"Move {move.value} PP exhausted")

        # Phase 4 — GENERATE
        now = datetime.now(timezone.utc).isoformat()

        turn = BattleTurn(
            turn_number=battle.current_turn,
            party=party,
            move_type=move,
            content=content,
            phase=BattlePhase.TRANSMIT,
            timestamp=now,
        )

        # Phase 5 — TRANSMIT
        battle.turns.append(turn)
        battle.updated_at = now

        # Stall detection
        stall_triggered = self._check_stall(battle, move)
        if stall_triggered:
            battle.transport = "pause"
            turn.metadata["stall_triggered"] = True
            logger.warning(
                "Battle %s stall detected (count=%d, threshold=%d)",
                battle_id, battle.stall_count, battle.stall_threshold,
            )

        await self._persist_turn(battle, turn)
        await self._persist_battle(battle)

        logger.debug(
            "Turn %d recorded: battle=%s party=%s move=%s",
            turn.turn_number, battle_id, party, move.value,
        )
        return turn

    # ─── Stall Detection ─────────────────────────────────────

    def _check_stall(self, battle: BattleState, move: MoveType) -> bool:
        """
        Check for stall condition: N consecutive same-category moves.

        Returns True if stall threshold is reached (caller should pause + notify).
        Resets counter on different-category move.
        """
        current_cat = get_category(move)

        if len(battle.turns) < 2:
            battle.stall_count = 0
            return False

        # Check the last N turns (including the one just added)
        recent = battle.turns[-(battle.stall_threshold):]
        if len(recent) < battle.stall_threshold:
            return False

        categories = [get_category(t.move_type) for t in recent]
        if all(c == current_cat for c in categories):
            battle.stall_count += 1
            return battle.stall_count >= 1  # first detection triggers
        else:
            battle.stall_count = 0
            return False

    # ─── Transport Control ───────────────────────────────────

    async def pause_battle(self, battle_id: str, reason: str = "") -> BattleState:
        """Pause a battle (play → pause)."""
        battle = self._battles.get(battle_id)
        if not battle:
            raise HTTPException(404, f"Battle {battle_id} not found")
        if battle.transport != "play":
            raise HTTPException(400, f"Cannot pause battle in {battle.transport} state")

        battle.transport = "pause"
        battle.updated_at = datetime.now(timezone.utc).isoformat()
        if reason:
            battle.metadata["pause_reason"] = reason

        await self._persist_battle(battle)
        logger.info("Battle %s paused: %s", battle_id, reason or "no reason")
        return battle

    async def resume_battle(self, battle_id: str) -> BattleState:
        """Resume a paused battle (pause → play)."""
        battle = self._battles.get(battle_id)
        if not battle:
            raise HTTPException(404, f"Battle {battle_id} not found")
        if battle.transport != "pause":
            raise HTTPException(400, f"Cannot resume battle in {battle.transport} state")

        battle.transport = "play"
        battle.updated_at = datetime.now(timezone.utc).isoformat()
        battle.metadata.pop("pause_reason", None)

        await self._persist_battle(battle)
        logger.info("Battle %s resumed", battle_id)
        return battle

    # ─── Resolution ──────────────────────────────────────────

    async def resolve_battle(
        self,
        battle_id: str,
        outcome: str,
        resolution_data: dict | None = None,
        actor: str = "trainer",
    ) -> BattleState:
        """
        Resolve a battle with a final outcome.

        Sets outcome, transport=stop, and optionally creates a Resolution
        record via AmbassadorService.
        """
        battle = self._battles.get(battle_id)
        if not battle:
            raise HTTPException(404, f"Battle {battle_id} not found")

        try:
            battle_outcome = BattleOutcome(outcome)
        except ValueError:
            raise HTTPException(400, f"Invalid outcome: {outcome}")

        if battle.outcome is not None:
            raise HTTPException(400, f"Battle {battle_id} already resolved")

        battle.outcome = battle_outcome
        battle.transport = "stop"
        battle.updated_at = datetime.now(timezone.utc).isoformat()
        if resolution_data:
            battle.metadata["resolution_data"] = resolution_data

        # Try to create Resolution in Ambassador layer
        try:
            from ambassador_service import get_ambassador_service
            amb_svc = get_ambassador_service()
            amb_svc.resolve_exchange(
                exchange_id=battle.exchange_id,
                resolution_type=f"battle_{outcome}",
                summary=f"Battle resolved: {outcome}",
                structured_data=resolution_data or {},
            )
        except Exception as e:
            logger.warning("Ambassador resolution failed (non-fatal): %s", e)

        await self._persist_battle(battle)
        logger.info("Battle %s resolved: %s (actor=%s)", battle_id, outcome, actor)
        return battle

    # ─── Trainer Actions ─────────────────────────────────────

    async def trainer_action(
        self,
        battle_id: str,
        action: str,
        payload: dict | None = None,
    ) -> BattleTurn:
        """
        Execute a trainer-only action (switch, use_item, run).

        - switch: type substitution (payload contains replacement info)
        - use_item: context injection (payload contains context data)
        - run: immediate exit → resolves battle with WITHDRAWAL outcome
        """
        battle = self._battles.get(battle_id)
        if not battle:
            raise HTTPException(404, f"Battle {battle_id} not found")

        try:
            move = MoveType(action)
        except ValueError:
            raise HTTPException(400, f"Invalid trainer action: {action}")

        if not is_trainer_move(move):
            raise HTTPException(400, f"{action} is not a trainer action")

        # RUN is special — resolves the battle immediately
        if move == MoveType.RUN:
            turn = await self.process_turn(
                battle_id=battle_id,
                party="trainer",
                move_type=action,
                content=payload.get("reason", "Trainer initiated exit") if payload else "Trainer initiated exit",
                actor="trainer",
            )
            await self.resolve_battle(
                battle_id=battle_id,
                outcome=BattleOutcome.WITHDRAWAL.value,
                resolution_data=payload,
                actor="trainer",
            )
            return turn

        # SWITCH / USE_ITEM
        content = ""
        if payload:
            content = payload.get("content", payload.get("reason", ""))

        return await self.process_turn(
            battle_id=battle_id,
            party="trainer",
            move_type=action,
            content=content,
            actor="trainer",
        )

    # ─── Query ───────────────────────────────────────────────

    async def list_battles(
        self,
        user_id: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        """List battles with optional filters."""
        results = []
        for battle in self._battles.values():
            if user_id and battle.user_id != user_id:
                continue
            if status == "active" and not battle.is_active:
                continue
            if status == "resolved" and battle.outcome is None:
                continue
            results.append(battle.to_dict())
        return results

    async def get_battle_turns(self, battle_id: str) -> list[dict]:
        """Get all turns for a battle, ordered by turn number."""
        battle = self._battles.get(battle_id)
        if not battle:
            raise HTTPException(404, f"Battle {battle_id} not found")
        return [t.to_dict() for t in battle.turns]

    # ─── Persistence ─────────────────────────────────────────

    async def _persist_battle(self, battle: BattleState):
        """Persist battle state to database. Non-fatal on failure."""
        if not self._db:
            return
        try:
            data = {
                "battle_id": battle.battle_id,
                "exchange_id": battle.exchange_id,
                "initiator_address_id": battle.initiator_address_id,
                "responder_address_id": battle.responder_address_id,
                "authority_boundary": battle.authority_boundary.to_dict(),
                "pp_state": battle.pp_tracker.to_dict(),
                "transport": battle.transport,
                "outcome": battle.outcome.value if battle.outcome else None,
                "stall_count": battle.stall_count,
                "stall_threshold": battle.stall_threshold,
                "max_turns": battle.max_turns,
                "turn_count": battle.current_turn,
                "metadata": battle.metadata,
                "created_at": battle.created_at,
                "updated_at": battle.updated_at,
                "user_id": battle.user_id,
            }
            if battle.outcome:
                data["resolved_at"] = battle.updated_at
                data["resolution_data"] = battle.metadata.get("resolution_data")

            self._db.table("battles").upsert(
                data, on_conflict="battle_id"
            ).execute()
        except Exception as e:
            logger.warning("Battle persist failed (non-fatal): %s", e)

    async def _persist_turn(self, battle: BattleState, turn: BattleTurn):
        """Persist a single turn to database. Non-fatal on failure."""
        if not self._db:
            return
        try:
            self._db.table("battle_turns").insert({
                "battle_id": battle.battle_id,
                "turn_number": turn.turn_number,
                "party": turn.party,
                "move_type": turn.move_type.value,
                "move_category": get_category(turn.move_type).value,
                "content": turn.content,
                "phase": turn.phase.value,
                "metadata": turn.metadata,
            }).execute()
        except Exception as e:
            logger.warning("Battle turn persist failed (non-fatal): %s", e)


# ─── Singleton ────────────────────────────────────────────────

_battle_service: Optional[BattleService] = None


def init_battle_service(db=None) -> BattleService:
    """Initialize the global battle service. Called during app lifespan."""
    global _battle_service
    _battle_service = BattleService(db=db)
    return _battle_service


def get_battle_service() -> BattleService:
    """Get the global battle service instance."""
    if _battle_service is None:
        raise HTTPException(503, "Battle service not initialized")
    return _battle_service
