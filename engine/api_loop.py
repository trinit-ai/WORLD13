"""
TMOS13 Loop API — The Loop (Fibonacci Plume Node 13)

4 REST endpoints for loop status, ratification, intents listing, and history.
"""
import logging
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Depends, Request, Query
from pydantic import BaseModel

logger = logging.getLogger("tmos13.api_loop")


class RatifyRequest(BaseModel):
    intent_id: str
    intent_type: str  # "chain" | "delivery"
    action: str       # "approve" | "reject"


def register_loop_endpoints(app: FastAPI, sessions, owner_id: str = ""):
    """Register Loop API endpoints."""

    @app.get("/api/loop/status")
    async def loop_status():
        """Loop dashboard: enabled state, pending counts, active sessions, upcoming events."""
        from config import LOOP_ENABLED, LOOP_CHAIN_ENABLED, LOOP_SEND_ENABLED

        result = {
            "enabled": LOOP_ENABLED,
            "chain_enabled": LOOP_CHAIN_ENABLED,
            "send_enabled": LOOP_SEND_ENABLED,
            "pending_chains": 0,
            "pending_deliveries": 0,
            "active_loop_sessions": 0,
            "upcoming": [],
        }

        if not LOOP_ENABLED:
            return result

        # Count pending chain intents
        try:
            from chain_executor import get_chain_executor
            chain_exec = get_chain_executor()
            if chain_exec:
                result["pending_chains"] = len(chain_exec.get_pending_intents())
        except Exception:
            pass

        # Count pending delivery intents
        try:
            from delivery_service import get_delivery_service
            delivery_svc = get_delivery_service()
            if delivery_svc and hasattr(delivery_svc, "get_pending_intents"):
                result["pending_deliveries"] = len(delivery_svc.get_pending_intents())
        except Exception:
            pass

        # Count active loop sessions
        try:
            if sessions:
                count = 0
                for state in sessions.all.values():
                    if getattr(state, "is_loop_session", False):
                        count += 1
                result["active_loop_sessions"] = count
        except Exception:
            pass

        # Upcoming schedule events
        try:
            from schedule_cache import get_schedule_cache
            cache = get_schedule_cache()
            if cache:
                now = datetime.now(timezone.utc)
                all_upcoming = []
                for pack_id in cache._entries:
                    upcoming = cache.get_upcoming(pack_id, now, limit=5)
                    for item in upcoming:
                        item["pack_id"] = pack_id
                    all_upcoming.extend(upcoming)
                all_upcoming.sort(key=lambda x: x.get("next_at", ""))
                result["upcoming"] = all_upcoming[:10]
        except Exception:
            pass

        return result

    @app.post("/api/loop/ratify")
    async def loop_ratify(req: RatifyRequest):
        """Approve or reject a pending intent (chain or delivery)."""
        from config import LOOP_ENABLED
        if not LOOP_ENABLED:
            raise HTTPException(503, "Loop is disabled")

        if req.action not in ("approve", "reject"):
            raise HTTPException(400, "action must be 'approve' or 'reject'")

        if req.intent_type == "chain":
            from chain_executor import get_chain_executor
            chain_exec = get_chain_executor()
            if not chain_exec:
                raise HTTPException(503, "Chain executor not initialized")

            if req.action == "approve":
                session_id = chain_exec.approve_intent(req.intent_id)
                if session_id is None:
                    raise HTTPException(404, "Intent not found or not pending")
                return {"status": "approved", "session_id": session_id}
            else:
                ok = chain_exec.reject_intent(req.intent_id)
                if not ok:
                    raise HTTPException(404, "Intent not found or not pending")
                return {"status": "rejected"}

        elif req.intent_type == "delivery":
            try:
                from delivery_service import get_delivery_service
                delivery_svc = get_delivery_service()
                if not delivery_svc:
                    raise HTTPException(503, "Delivery service not initialized")

                if req.action == "approve":
                    result = await delivery_svc.approve_intent(req.intent_id)
                    return {"status": "approved", "result": result}
                else:
                    result = await delivery_svc.reject_intent(req.intent_id)
                    return {"status": "rejected", "result": result}
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(500, f"Delivery ratification failed: {e}")

        else:
            raise HTTPException(400, "intent_type must be 'chain' or 'delivery'")

    @app.get("/api/loop/intents")
    async def loop_intents():
        """List all pending chain and delivery intents with details."""
        from config import LOOP_ENABLED
        intents = []

        if not LOOP_ENABLED:
            return {"intents": intents}

        # Pending chain intents
        try:
            from chain_executor import get_chain_executor
            chain_exec = get_chain_executor()
            if chain_exec:
                for intent in chain_exec.get_pending_intents():
                    intents.append({
                        "id": intent.id,
                        "type": "chain",
                        "chain_id": intent.chain_id,
                        "source_pack": intent.source_pack,
                        "target_pack": intent.target_pack,
                        "status": intent.status,
                        "mode": intent.mode,
                        "created_at": intent.created_at,
                    })
        except Exception:
            pass

        # Pending delivery intents
        try:
            from delivery_service import get_delivery_service
            delivery_svc = get_delivery_service()
            if delivery_svc and hasattr(delivery_svc, "get_pending_intents"):
                for intent in delivery_svc.get_pending_intents():
                    intents.append({
                        "id": getattr(intent, "id", str(intent)),
                        "type": "delivery",
                        "chain_id": getattr(intent, "chain_id", None),
                        "source_pack": getattr(intent, "source_pack", None),
                        "target_pack": getattr(intent, "target_pack", None),
                        "status": getattr(intent, "status", "pending"),
                        "mode": getattr(intent, "mode", None),
                        "created_at": getattr(intent, "created_at", None),
                    })
        except Exception:
            pass

        # Sort by created_at ascending (oldest first)
        intents.sort(key=lambda x: x.get("created_at") or "")
        return {"intents": intents}

    @app.get("/api/loop/history")
    async def loop_history(limit: int = Query(default=20, le=100)):
        """List recently executed/rejected intents for the activity log."""
        from config import LOOP_ENABLED
        history = []

        if not LOOP_ENABLED:
            return {"history": history}

        # Executed/rejected chain intents
        try:
            from chain_executor import get_chain_executor
            chain_exec = get_chain_executor()
            if chain_exec and hasattr(chain_exec, "get_history"):
                for intent in chain_exec.get_history(limit=limit):
                    history.append({
                        "id": intent.id,
                        "type": "chain",
                        "chain_id": intent.chain_id,
                        "source_pack": intent.source_pack,
                        "target_pack": intent.target_pack,
                        "status": intent.status,
                        "session_id": intent.session_id,
                        "created_at": intent.created_at,
                    })
        except Exception:
            pass

        # Executed/rejected delivery intents
        try:
            from delivery_service import get_delivery_service
            delivery_svc = get_delivery_service()
            if delivery_svc and hasattr(delivery_svc, "get_history"):
                for intent in delivery_svc.get_history(limit=limit):
                    history.append({
                        "id": getattr(intent, "id", str(intent)),
                        "type": "delivery",
                        "source_pack": getattr(intent, "source_pack", None),
                        "target_pack": getattr(intent, "target_pack", None),
                        "status": getattr(intent, "status", "unknown"),
                        "created_at": getattr(intent, "created_at", None),
                    })
        except Exception:
            pass

        # Sort by created_at descending (most recent first)
        history.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return {"history": history[:limit]}
