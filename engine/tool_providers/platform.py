"""
Platform tool provider — reads and manages TMOS13 platform state.

Wraps existing service singletons (inbox, contacts, packs, loop, pipelines)
into a unified tool provider for the operator pack.
"""
import logging
from tool_providers.base import ToolProvider

logger = logging.getLogger("tmos13.tools.platform")


class PlatformProvider(ToolProvider):
    """Provider for platform operations — inbox, contacts, packs, automation, observability."""

    @property
    def name(self) -> str:
        return "platform"

    def supported_operations(self) -> list[str]:
        return [
            "inbox_list", "inbox_stats", "inbox_update_status",
            "contacts_list", "contacts_search",
            "loop_status", "loop_ratify",
            "pipeline_list", "pack_catalog", "session_stats",
        ]

    async def execute(
        self,
        operation: str,
        parameters: dict,
        config: dict,
    ) -> dict:
        handlers = {
            "inbox_list": self._inbox_list,
            "inbox_stats": self._inbox_stats,
            "inbox_update_status": self._inbox_update_status,
            "contacts_list": self._contacts_list,
            "contacts_search": self._contacts_search,
            "loop_status": self._loop_status,
            "loop_ratify": self._loop_ratify,
            "pipeline_list": self._pipeline_list,
            "pack_catalog": self._pack_catalog,
            "session_stats": self._session_stats,
        }
        handler = handlers.get(operation)
        if not handler:
            return {"success": False, "message": f"Unsupported operation: {operation}"}
        try:
            return await handler(parameters)
        except Exception as e:
            logger.error(f"Platform provider {operation} failed: {e}")
            return {"success": False, "message": f"Operation failed: {e}"}

    # ── Inbox ─────────────────────────────────────────────

    async def _inbox_list(self, params: dict) -> dict:
        from inbox import get_inbox_service
        from config import TMOS13_OWNER_ID
        svc = get_inbox_service()
        conversations, total = svc.list(
            owner_id=TMOS13_OWNER_ID,
            status=params.get("status"),
            deployment_id=params.get("deployment_id"),
            priority=params.get("priority"),
            classification=params.get("classification"),
            since=params.get("since"),
            until=params.get("until"),
            limit=params.get("limit", 20),
            offset=params.get("offset", 0),
        )
        return {
            "success": True,
            "total": total,
            "conversations": [
                {
                    "id": c.id,
                    "visitor_name": c.visitor_name,
                    "visitor_email": c.visitor_email,
                    "status": c.status,
                    "priority": c.priority,
                    "classification": c.classification,
                    "pack_id": c.pack_id,
                    "turns": c.turns,
                    "summary": c.summary,
                    "created_at": c.created_at,
                }
                for c in conversations
            ],
        }

    async def _inbox_stats(self, params: dict) -> dict:
        from inbox import get_inbox_service
        from config import TMOS13_OWNER_ID
        svc = get_inbox_service()
        stats = svc.stats(TMOS13_OWNER_ID)
        return {"success": True, **stats}

    async def _inbox_update_status(self, params: dict) -> dict:
        from inbox import get_inbox_service
        svc = get_inbox_service()
        conversation_id = params.get("conversation_id", "")
        status = params.get("status", "")
        if not conversation_id or not status:
            return {"success": False, "message": "Missing conversation_id or status"}
        conv = svc.update_status(conversation_id, status)
        return {
            "success": True,
            "message": f"Conversation {conversation_id} → {status}",
            "conversation_id": conv.id,
            "status": conv.status,
        }

    # ── Contacts ──────────────────────────────────────────

    async def _contacts_list(self, params: dict) -> dict:
        from contacts import get_contacts_service
        from config import TMOS13_OWNER_ID
        svc = get_contacts_service()
        contacts, total = svc.list(
            owner_id=TMOS13_OWNER_ID,
            entity_type=params.get("entity_type"),
            status=params.get("status"),
            department=params.get("department"),
            search=params.get("search"),
            tags=params.get("tags"),
            limit=params.get("limit", 20),
            offset=params.get("offset", 0),
        )
        return {
            "success": True,
            "total": total,
            "contacts": [
                {
                    "id": c.id,
                    "name": c.name,
                    "email": c.email,
                    "entity_type": c.entity_type,
                    "status": c.status,
                    "organization": c.organization,
                    "department": c.department,
                    "last_touch_at": c.last_touch_at,
                }
                for c in contacts
            ],
        }

    async def _contacts_search(self, params: dict) -> dict:
        from contacts import get_contacts_service
        from config import TMOS13_OWNER_ID
        svc = get_contacts_service()
        query = params.get("query", "")
        if not query:
            return {"success": False, "message": "Missing search query"}
        contacts = svc.search(TMOS13_OWNER_ID, query)
        return {
            "success": True,
            "total": len(contacts),
            "contacts": [
                {
                    "id": c.id,
                    "name": c.name,
                    "email": c.email,
                    "entity_type": c.entity_type,
                    "organization": c.organization,
                }
                for c in contacts
            ],
        }

    # ── Automation / Loop ─────────────────────────────────

    async def _loop_status(self, params: dict) -> dict:
        from config import LOOP_ENABLED, LOOP_CHAIN_ENABLED, LOOP_SEND_ENABLED
        result = {
            "success": True,
            "enabled": LOOP_ENABLED,
            "chain_enabled": LOOP_CHAIN_ENABLED,
            "send_enabled": LOOP_SEND_ENABLED,
            "pending_chains": 0,
            "pending_deliveries": 0,
            "upcoming": [],
        }
        if not LOOP_ENABLED:
            return result
        try:
            from chain_executor import get_chain_executor
            chain_exec = get_chain_executor()
            if chain_exec:
                result["pending_chains"] = len(chain_exec.get_pending_intents())
        except Exception:
            pass
        try:
            from delivery_service import get_delivery_service
            delivery_svc = get_delivery_service()
            if delivery_svc and hasattr(delivery_svc, "get_pending_intents"):
                result["pending_deliveries"] = len(delivery_svc.get_pending_intents())
        except Exception:
            pass
        try:
            from schedule_cache import get_schedule_cache
            from datetime import datetime, timezone
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

    async def _loop_ratify(self, params: dict) -> dict:
        from config import LOOP_ENABLED
        if not LOOP_ENABLED:
            return {"success": False, "message": "Loop is disabled"}
        intent_id = params.get("intent_id", "")
        intent_type = params.get("intent_type", "")
        action = params.get("action", "")
        if not intent_id or not intent_type or action not in ("approve", "reject"):
            return {"success": False, "message": "Missing intent_id, intent_type, or valid action (approve/reject)"}

        if intent_type == "chain":
            from chain_executor import get_chain_executor
            chain_exec = get_chain_executor()
            if not chain_exec:
                return {"success": False, "message": "Chain executor not initialized"}
            if action == "approve":
                session_id = chain_exec.approve_intent(intent_id)
                if session_id is None:
                    return {"success": False, "message": "Intent not found or not pending"}
                return {"success": True, "message": f"Chain intent approved → session {session_id}", "session_id": session_id}
            else:
                ok = chain_exec.reject_intent(intent_id)
                if not ok:
                    return {"success": False, "message": "Intent not found or not pending"}
                return {"success": True, "message": "Chain intent rejected"}

        elif intent_type == "delivery":
            from delivery_service import get_delivery_service
            delivery_svc = get_delivery_service()
            if not delivery_svc:
                return {"success": False, "message": "Delivery service not initialized"}
            if action == "approve":
                result = await delivery_svc.approve_intent(intent_id)
                return {"success": True, "message": "Delivery intent approved", "result": result}
            else:
                result = await delivery_svc.reject_intent(intent_id)
                return {"success": True, "message": "Delivery intent rejected", "result": result}

        return {"success": False, "message": f"Unknown intent_type: {intent_type}"}

    # ── Pipelines ─────────────────────────────────────────

    async def _pipeline_list(self, params: dict) -> dict:
        try:
            from pipeline_service import get_pipeline_service
            svc = get_pipeline_service()
            if not svc:
                return {"success": True, "pipelines": [], "message": "Pipeline service not initialized"}
            pipelines = svc.get_active_pipelines()
            return {
                "success": True,
                "total": len(pipelines),
                "pipelines": [
                    {
                        "id": getattr(p, "id", str(p)),
                        "status": getattr(p, "status", "unknown"),
                        "pack_id": getattr(p, "pack_id", None),
                        "created_at": getattr(p, "created_at", None),
                    }
                    for p in pipelines
                ],
            }
        except Exception as e:
            return {"success": True, "pipelines": [], "message": f"Pipeline service unavailable: {e}"}

    # ── Packs ─────────────────────────────────────────────

    async def _pack_catalog(self, params: dict) -> dict:
        from pack_loader import get_available_packs
        packs = get_available_packs()
        return {
            "success": True,
            "total": len(packs),
            "packs": [
                {
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "category": p.get("category"),
                    "description": p.get("description"),
                    "visibility": p.get("visibility"),
                    "access": p.get("access"),
                }
                for p in packs
            ],
        }

    # ── Session Stats ─────────────────────────────────────

    async def _session_stats(self, params: dict) -> dict:
        from inbox import get_inbox_service
        from config import TMOS13_OWNER_ID
        svc = get_inbox_service()
        stats = svc.stats(TMOS13_OWNER_ID)
        return {
            "success": True,
            "total_sessions": stats.get("total", 0),
            "avg_turns": stats.get("avg_turns", 0),
            "avg_duration_seconds": stats.get("avg_duration_seconds", 0),
            "avg_cost_usd": stats.get("avg_cost_usd", 0),
            "by_status": {
                "needs_review": stats.get("needs_review", 0),
                "escalated": stats.get("escalated", 0),
                "resolved": stats.get("resolved", 0),
                "abandoned": stats.get("abandoned", 0),
            },
        }
