"""
TMOS13 Pack Stats Service — Pack Intelligence Layer

Computes and formats pack-level statistics from session data, deliverables,
and feedback. Auto-generates [PACK ATTRIBUTES] context blocks for assembler
injection, giving each pack awareness of its own performance and maturity.

Singleton: init_pack_stats(db) / get_pack_stats().
"""
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import config as cfg

logger = logging.getLogger("tmos13.pack_stats")

# ─── Level Thresholds ────────────────────────────────────
# (min_sessions, max_sessions, level_start, confidence_label)
_LEVEL_TIERS = [
    (0, 49, 1, "bootstrapping"),
    (50, 199, 5, "low"),
    (200, 499, 10, "moderate"),
    (500, 999, 20, "established"),
    (1000, 2499, 30, "high"),
    (2500, 4999, 40, "veteran"),
    (5000, None, 50, "authority"),
]


def compute_level(total_sessions: int) -> tuple[int, str]:
    """
    Compute pack level and confidence label from total session count.

    Returns (level, confidence_label).
    Pure function — no DB calls.
    """
    if total_sessions < 0:
        total_sessions = 0

    for min_s, max_s, level_start, confidence in _LEVEL_TIERS:
        if max_s is None:
            # Top tier — level 50 flat
            return 50, confidence
        if min_s <= total_sessions <= max_s:
            # Interpolate level within tier
            tier_range = max_s - min_s + 1
            tier_levels = _LEVEL_TIERS[_LEVEL_TIERS.index((min_s, max_s, level_start, confidence))]
            # Find next tier's level_start for interpolation ceiling
            idx = _LEVEL_TIERS.index((min_s, max_s, level_start, confidence))
            if idx + 1 < len(_LEVEL_TIERS):
                level_end = _LEVEL_TIERS[idx + 1][2] - 1
            else:
                level_end = 50
            progress = (total_sessions - min_s) / tier_range
            level = level_start + int(progress * (level_end - level_start + 1))
            level = min(level, level_end)
            return level, confidence

    return 1, "bootstrapping"


class PackStatsService:
    """Computes and caches pack-level statistics."""

    def __init__(self, db=None):
        self._db = db
        self._last_run: float = 0.0
        self._cache: dict[str, dict] = {}
        logger.info("Pack stats service initialized")

    @property
    def enabled(self) -> bool:
        return self._db is not None and cfg.PACK_STATS_ENABLED

    def compute_pack_stats(
        self, pack_id: str, lookback_days: int = None
    ) -> dict:
        """
        Compute statistics for a pack from DB data.

        Returns dict with keys: total_sessions, avg_turns, avg_depth,
        completion_rate, deliverable_count, avg_rating, feedback_count,
        install_count, top_cartridge, weakest_cartridge, level, confidence.
        """
        if not self.enabled:
            return {}
        if lookback_days is None:
            lookback_days = cfg.PACK_STATS_LOOKBACK_DAYS

        cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
        stats: dict = {"pack_id": pack_id}

        # ─── Session Journals ─────────────────────────────
        try:
            result = (
                self._db.table("session_journals")
                .select("id, turn_count, depth, session_outcome, cartridges_visited")
                .eq("pack_id", pack_id)
                .gte("session_ended_at", cutoff)
                .execute()
            )
            journals = result.data if result and result.data else []
            stats["total_sessions"] = len(journals)

            if journals:
                turns = [j.get("turn_count", 0) or 0 for j in journals]
                depths = [j.get("depth", 0) or 0 for j in journals]
                stats["avg_turns"] = round(sum(turns) / len(turns), 1) if turns else 0
                stats["avg_depth"] = round(sum(depths) / len(depths), 1) if depths else 0

                # Completion rate (sessions with session_outcome="completed")
                completed = sum(1 for j in journals if j.get("session_outcome") == "completed")
                stats["completion_rate"] = round(completed / len(journals) * 100) if journals else 0

                # Cartridge frequency
                cart_counts: dict[str, int] = {}
                for j in journals:
                    carts = j.get("cartridges_visited") or []
                    if isinstance(carts, list):
                        for c in carts:
                            cart_counts[c] = cart_counts.get(c, 0) + 1
                if cart_counts:
                    stats["top_cartridge"] = max(cart_counts, key=cart_counts.get)
                    stats["top_cartridge_count"] = cart_counts[stats["top_cartridge"]]
                    stats["weakest_cartridge"] = min(cart_counts, key=cart_counts.get)
                    stats["weakest_cartridge_count"] = cart_counts[stats["weakest_cartridge"]]
                    stats["cartridge_counts"] = cart_counts
            else:
                stats["avg_turns"] = 0
                stats["avg_depth"] = 0
                stats["completion_rate"] = 0
        except Exception as e:
            logger.warning("Pack stats: session journal query failed for %s: %s", pack_id, e)
            stats["total_sessions"] = 0
            stats["avg_turns"] = 0
            stats["avg_depth"] = 0
            stats["completion_rate"] = 0

        # ─── Deliverables ─────────────────────────────────
        try:
            result = (
                self._db.table("deliverables")
                .select("id, status")
                .eq("pack_id", pack_id)
                .gte("created_at", cutoff)
                .execute()
            )
            deliverables = result.data if result and result.data else []
            stats["deliverable_count"] = len(deliverables)
        except Exception as e:
            logger.warning("Pack stats: deliverables query failed for %s: %s", pack_id, e)
            stats["deliverable_count"] = 0

        # ─── Feedback ─────────────────────────────────────
        try:
            result = (
                self._db.table("deliverable_feedback")
                .select("rating, deliverable_id")
                .execute()
            )
            all_feedback = result.data if result and result.data else []

            # Filter to this pack's deliverables if we have deliverable IDs
            if stats.get("deliverable_count", 0) > 0 and all_feedback:
                try:
                    del_result = (
                        self._db.table("deliverables")
                        .select("id")
                        .eq("pack_id", pack_id)
                        .execute()
                    )
                    pack_del_ids = {d["id"] for d in (del_result.data or [])}
                    pack_feedback = [f for f in all_feedback if f.get("deliverable_id") in pack_del_ids]
                except Exception:
                    pack_feedback = []
            else:
                pack_feedback = []

            stats["feedback_count"] = len(pack_feedback)
            if pack_feedback:
                ratings = [f.get("rating", 0) for f in pack_feedback if f.get("rating")]
                stats["avg_rating"] = round(sum(ratings) / len(ratings), 1) if ratings else 0
            else:
                stats["avg_rating"] = 0
        except Exception as e:
            logger.warning("Pack stats: feedback query failed for %s: %s", pack_id, e)
            stats["feedback_count"] = 0
            stats["avg_rating"] = 0

        # ─── Active Installs ──────────────────────────────
        try:
            from pack_install_service import get_pack_install_service
            pis = get_pack_install_service()
            if pis:
                result = (
                    self._db.table("pack_installs")
                    .select("id")
                    .eq("pack_id", pack_id)
                    .eq("status", "active")
                    .execute()
                )
                stats["install_count"] = len(result.data) if result and result.data else 0
            else:
                stats["install_count"] = 0
        except Exception:
            stats["install_count"] = 0

        # ─── Level ────────────────────────────────────────
        level, confidence = compute_level(stats.get("total_sessions", 0))
        stats["level"] = level
        stats["confidence"] = confidence

        # Cache the result
        self._cache[pack_id] = stats
        return stats

    def format_pack_stats(self, stats: dict) -> str:
        """
        Format computed stats into a compact [PACK ATTRIBUTES] block.

        Returns "" if stats are empty or have no sessions.
        """
        if not stats:
            return ""

        level = stats.get("level", 1)
        total = stats.get("total_sessions", 0)
        confidence = stats.get("confidence", "bootstrapping")
        completion = stats.get("completion_rate", 0)
        avg_depth = stats.get("avg_depth", 0)
        avg_turns = stats.get("avg_turns", 0)
        deliverables = stats.get("deliverable_count", 0)
        avg_rating = stats.get("avg_rating", 0)

        lines = ["[PACK ATTRIBUTES]"]

        # Line 1: Level summary
        line1_parts = [f"Level {level}", f"{total} sessions"]
        if total > 0:
            line1_parts.append(f"{completion}% completion")
        line1_parts.append(f"Confidence: {confidence}")
        lines.append(" | ".join(line1_parts))

        # Line 2: Metrics (only if we have sessions)
        if total > 0:
            line2_parts = []
            if avg_depth:
                line2_parts.append(f"Avg depth: {avg_depth}")
            if avg_turns:
                line2_parts.append(f"Avg turns: {avg_turns}")
            if deliverables:
                line2_parts.append(f"Deliverables: {deliverables}")
            if avg_rating:
                line2_parts.append(f"Avg rating: {avg_rating}/5")
            if line2_parts:
                lines.append(" | ".join(line2_parts))

        # Line 3: Cartridge highlights (only if data exists)
        top = stats.get("top_cartridge")
        weakest = stats.get("weakest_cartridge")
        if top and top != weakest:
            line3_parts = []
            top_count = stats.get("top_cartridge_count", 0)
            line3_parts.append(f"Top cartridge: {top} ({top_count})")
            if weakest:
                weakest_count = stats.get("weakest_cartridge_count", 0)
                line3_parts.append(f"Weakest: {weakest} ({weakest_count})")
            lines.append(" | ".join(line3_parts))

        lines.append("[/PACK ATTRIBUTES]")
        return "\n".join(lines)

    def fetch_pack_stats(self, pack_id: str) -> str:
        """
        Compute and format pack stats. Returns formatted [PACK ATTRIBUTES] block.
        Returns "" on failure or when disabled.
        """
        if not self.enabled:
            return ""
        try:
            stats = self.compute_pack_stats(pack_id)
            return self.format_pack_stats(stats)
        except Exception as e:
            logger.warning("Pack stats fetch failed for %s: %s", pack_id, e)
            return ""

    def generate_all_stats(self, limit: int = 50) -> dict:
        """
        Batch compute stats for all active packs. Used by background loop.

        Returns dict of {pack_id: stats_dict}.
        """
        if not self.enabled:
            return {}

        results = {}
        try:
            pack_ids = cfg.get_pack_ids()
            for pack_id in pack_ids[:limit]:
                try:
                    stats = self.compute_pack_stats(pack_id)
                    results[pack_id] = stats
                except Exception as e:
                    logger.debug("Stats generation skipped for %s: %s", pack_id, e)
        except Exception as e:
            logger.warning("Batch stats generation failed: %s", e)

        return results

    def should_run(self) -> bool:
        """Check if enough time has passed since last stats generation."""
        if not self.enabled:
            return False
        interval_seconds = cfg.PACK_STATS_INTERVAL_HOURS * 3600
        return (time.time() - self._last_run) >= interval_seconds

    def mark_run(self):
        """Mark that a stats generation run just completed."""
        self._last_run = time.time()


# ─── Singleton ────────────────────────────────────────────

_pack_stats: Optional[PackStatsService] = None


def init_pack_stats(db=None) -> PackStatsService:
    """Initialize the global PackStatsService singleton."""
    global _pack_stats
    _pack_stats = PackStatsService(db=db)
    return _pack_stats


def get_pack_stats() -> Optional[PackStatsService]:
    """Return the global PackStatsService or None."""
    return _pack_stats
