"""
TMOS13 Deliverable Feedback Service

Manages deliverable ratings and comments. Stores user feedback in
deliverable_feedback table. Formats prior feedback as a [DELIVERY FEEDBACK]
block for assembler injection so future deliverable generation learns
what worked.

Singleton pattern from delivery_service.py.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger("tmos13.feedback")

# ─── Configuration ─────────────────────────────────────────
import os

FEEDBACK_ENABLED = os.environ.get("TMOS13_FEEDBACK_ENABLED", "true").lower() in ("true", "1", "yes")
FEEDBACK_MAX_INJECTIONS = int(os.environ.get("TMOS13_FEEDBACK_MAX_INJECTIONS", "5"))
FEEDBACK_MAX_TOKENS = int(os.environ.get("TMOS13_FEEDBACK_MAX_TOKENS", "800"))


class FeedbackService:
    """
    Manages deliverable feedback lifecycle: submission, retrieval, context formatting.
    """

    def __init__(self, supabase_client=None):
        self._db = supabase_client
        logger.info("Feedback service initialized (enabled=%s)", FEEDBACK_ENABLED)

    # ─── Submit ─────────────────────────────────────────

    def submit_feedback(
        self,
        deliverable_id: str,
        user_id: str,
        rating: int,
        comment: str = "",
        section_id: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Store a feedback entry. Returns the inserted row or None on failure.
        """
        if not FEEDBACK_ENABLED:
            logger.debug("Feedback disabled — skipping submit")
            return None
        if not self._db:
            return None
        if not user_id or user_id == "anonymous":
            return None
        if not isinstance(rating, int) or rating < 1 or rating > 5:
            return None

        try:
            row = {
                "deliverable_id": deliverable_id,
                "user_id": user_id,
                "rating": rating,
                "comment": comment or "",
            }
            if section_id:
                row["section_id"] = section_id

            result = self._db.table("deliverable_feedback").insert(row).execute()
            data = result.data[0] if result and result.data else row
            logger.debug(
                "Feedback saved: deliverable=%s user=%s rating=%d",
                deliverable_id, user_id, rating,
            )
            return data
        except Exception as e:
            logger.warning("Failed to save feedback: %s", e)
            return None

    # ─── Retrieve ───────────────────────────────────────

    def get_feedback(
        self,
        deliverable_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """
        Query feedback entries. Filter by deliverable_id and/or user_id.
        """
        if not self._db:
            return []

        try:
            query = self._db.table("deliverable_feedback").select("*")
            if deliverable_id:
                query = query.eq("deliverable_id", deliverable_id)
            if user_id:
                query = query.eq("user_id", user_id)
            query = query.order("created_at", desc=True).limit(limit)
            result = query.execute()
            return result.data if result and result.data else []
        except Exception as e:
            logger.warning("Feedback query failed: %s", e)
            return []

    # ─── Context Formatting ─────────────────────────────

    def fetch_feedback_context(
        self,
        user_id: str,
        pack_id: Optional[str] = None,
    ) -> str:
        """
        Format prior feedback as a [DELIVERY FEEDBACK] block for assembler injection.

        Joins feedback with deliverables to filter by pack_id.
        Returns "" when disabled, anonymous, or no results.
        """
        if not FEEDBACK_ENABLED:
            return ""
        if not self._db:
            return ""
        if not user_id or user_id == "anonymous":
            return ""

        try:
            # Query feedback joined with deliverables for this user
            # Supabase doesn't support joins natively in the JS/Python client,
            # so we do a two-step query: get recent feedback, then filter by pack.
            query = (
                self._db.table("deliverable_feedback")
                .select("*, deliverables(pack_id, spec_id, spec_name)")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(FEEDBACK_MAX_INJECTIONS * 3)  # over-fetch to filter
            )
            result = query.execute()
            rows = result.data if result and result.data else []
        except Exception as e:
            logger.warning("Feedback context query failed: %s", e)
            return ""

        if not rows:
            return ""

        # Filter by pack_id if specified
        filtered = []
        for row in rows:
            deliverable = row.get("deliverables", {}) or {}
            row_pack = deliverable.get("pack_id", "")
            if pack_id and row_pack and row_pack != pack_id:
                continue
            filtered.append(row)
            if len(filtered) >= FEEDBACK_MAX_INJECTIONS:
                break

        if not filtered:
            return ""

        # Format block
        char_budget = FEEDBACK_MAX_TOKENS * 4
        lines = ["[DELIVERY FEEDBACK — Prior deliverable ratings from this user]"]

        used = len(lines[0])
        for row in filtered:
            deliverable = row.get("deliverables", {}) or {}
            spec_name = deliverable.get("spec_name", "deliverable")
            rating = row.get("rating", 0)
            comment = row.get("comment", "")
            section = row.get("section_id", "")

            parts = [f"- {spec_name}: {rating}/5"]
            if comment:
                parts.append(f'"{comment}"')
            if section:
                parts.append(f"(section: {section})")
            line = " ".join(parts)

            if used + len(line) + 2 > char_budget:
                break
            lines.append(line)
            used += len(line) + 1

        lines.append(
            "INSTRUCTION: Use this feedback to improve deliverable quality. "
            "Lean into approaches that received high ratings. "
            "Address concerns from low ratings."
        )
        lines.append("[/DELIVERY FEEDBACK]")

        return "\n".join(lines)


# ─── Singleton ──────────────────────────────────────────────

_feedback_service: Optional[FeedbackService] = None


def init_feedback_service(supabase_client=None) -> FeedbackService:
    """Initialize the global feedback service singleton."""
    global _feedback_service
    _feedback_service = FeedbackService(supabase_client=supabase_client)
    return _feedback_service


def get_feedback_service() -> Optional[FeedbackService]:
    """Return the global feedback service singleton."""
    return _feedback_service
