"""Sprint Items — session-based task board for Workspace home."""
import logging
from datetime import datetime, timezone as tz
from typing import Optional
from uuid import uuid4

logger = logging.getLogger("tmos13.sprints")


class SprintStore:
    """CRUD for sprint_items table."""

    def __init__(self, supabase_client=None):
        self._db = supabase_client

    def list_sprints(
        self,
        owner_id: str,
        status_filter: Optional[list[str]] = None,
        pack_id: Optional[str] = None,
        limit: int = 20,
    ) -> dict:
        """List sprint items for a user, with counts."""
        if not self._db:
            return {"items": [], "counts": {"pending": 0, "active": 0, "complete": 0}}

        try:
            query = self._db.table("sprint_items").select("*").eq("owner_id", owner_id)

            if status_filter:
                query = query.in_("status", status_filter)
            else:
                query = query.in_("status", ["pending", "active"])

            if pack_id:
                query = query.eq("pack_id", pack_id)

            query = query.order("priority").order("created_at").limit(limit)
            result = query.execute()
            items = result.data or []

            # Get counts
            counts = {"pending": 0, "active": 0, "complete": 0}
            count_query = (
                self._db.table("sprint_items")
                .select("status", count="exact")
                .eq("owner_id", owner_id)
                .neq("status", "archived")
            )
            count_result = count_query.execute()
            for row in count_result.data or []:
                s = row.get("status")
                if s in counts:
                    counts[s] = counts.get(s, 0) + 1

            return {"items": items, "counts": counts}

        except Exception as e:
            logger.warning(f"Sprint list failed for {owner_id}: {e}")
            return {"items": [], "counts": {"pending": 0, "active": 0, "complete": 0}}

    def create_sprint(
        self,
        owner_id: str,
        title: str,
        description: Optional[str] = None,
        pack_id: Optional[str] = None,
        seed_context: Optional[dict] = None,
        due_date: Optional[str] = None,
        completion_type: str = "manual",
        priority: int = 0,
    ) -> Optional[dict]:
        """Create a new sprint item."""
        if not self._db:
            return None

        try:
            row = {
                "id": str(uuid4()),
                "owner_id": owner_id,
                "title": title,
                "description": description,
                "pack_id": pack_id,
                "seed_context": seed_context or {},
                "status": "pending",
                "due_date": due_date,
                "priority": priority,
                "completion_type": completion_type if pack_id else "manual",
                "created_at": datetime.now(tz.utc).isoformat(),
                "updated_at": datetime.now(tz.utc).isoformat(),
            }
            result = self._db.table("sprint_items").insert(row).execute()
            return result.data[0] if result.data else None

        except Exception as e:
            logger.warning(f"Sprint create failed: {e}")
            return None

    def update_sprint(self, sprint_id: str, owner_id: str, updates: dict) -> Optional[dict]:
        """Partial update. Only allows safe fields."""
        if not self._db:
            return None

        allowed = {"title", "description", "pack_id", "seed_context", "due_date",
                    "priority", "status", "completion_type"}
        safe = {k: v for k, v in updates.items() if k in allowed}

        if not safe:
            return None

        # Handle status transitions
        if safe.get("status") == "complete":
            safe["completed_at"] = datetime.now(tz.utc).isoformat()

        try:
            result = (
                self._db.table("sprint_items")
                .update(safe)
                .eq("id", sprint_id)
                .eq("owner_id", owner_id)
                .execute()
            )
            return result.data[0] if result.data else None

        except Exception as e:
            logger.warning(f"Sprint update failed for {sprint_id}: {e}")
            return None

    def start_sprint(self, sprint_id: str, owner_id: str, session_id: str) -> Optional[dict]:
        """Link a sprint to a session and mark active."""
        if not self._db:
            return None

        try:
            result = (
                self._db.table("sprint_items")
                .update({
                    "status": "active",
                    "session_id": session_id,
                    "started_at": datetime.now(tz.utc).isoformat(),
                })
                .eq("id", sprint_id)
                .eq("owner_id", owner_id)
                .in_("status", ["pending", "active"])
                .execute()
            )
            return result.data[0] if result.data else None

        except Exception as e:
            logger.warning(f"Sprint start failed for {sprint_id}: {e}")
            return None

    def complete_by_session(self, session_id: str, deliverable_id: Optional[str] = None):
        """Auto-complete sprint items linked to a session.

        Called from deliverables pipeline when a deliverable is produced,
        or from session close for session_end completion type.
        """
        if not self._db or not session_id:
            return

        try:
            query = (
                self._db.table("sprint_items")
                .select("id, completion_type")
                .eq("session_id", session_id)
                .eq("status", "active")
            )
            result = query.execute()

            for item in result.data or []:
                should_complete = False
                if item["completion_type"] == "deliverable" and deliverable_id:
                    should_complete = True
                elif item["completion_type"] == "session_end":
                    should_complete = True

                if should_complete:
                    update = {
                        "status": "complete",
                        "completed_at": datetime.now(tz.utc).isoformat(),
                    }
                    if deliverable_id:
                        update["deliverable_id"] = deliverable_id
                    self._db.table("sprint_items").update(update).eq("id", item["id"]).execute()

        except Exception as e:
            logger.warning(f"Sprint auto-complete failed for session {session_id}: {e}")

    def archive_sprint(self, sprint_id: str, owner_id: str) -> bool:
        """Soft-delete by archiving."""
        if not self._db:
            return False

        try:
            self._db.table("sprint_items").update(
                {"status": "archived"}
            ).eq("id", sprint_id).eq("owner_id", owner_id).execute()
            return True
        except Exception:
            return False
