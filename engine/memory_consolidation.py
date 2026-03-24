"""
TMOS13 Memory Consolidation — L2 memory synthesis.

Compresses 5+ session insights into higher-order patterns using Haiku.
Tiered memory model: L1 (raw insights) → L2 (consolidated patterns) → L3 (UserIdentity).

Background job finds users with enough un-consolidated insights, calls Haiku
to synthesize patterns, stores the result in memory_consolidations, and
optionally embeds the summary via EmbeddingPipeline.

Singleton: init_memory_consolidation(db, llm_provider) / get_memory_consolidation().
"""
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import config as cfg

logger = logging.getLogger("tmos13.memory_consolidation")

_SYNTHESIS_SYSTEM = (
    "You are a memory synthesis engine. Given session insights from a user, "
    "produce a 3-5 sentence consolidated pattern summary. Capture: stable preferences, "
    "recurring topics, effective approaches, and predictive signals. Be specific and "
    "actionable. This will be injected into future sessions so the system remembers "
    "who this person is. No pleasantries."
)

_IDENTITY_SYSTEM = (
    "You are a user identity synthesis engine. Given consolidated pattern summaries "
    "from multiple domain contexts (packs), produce a 4-8 sentence unified user profile. "
    "Capture: cross-domain preferences, communication style, expertise areas, recurring "
    "needs, decision patterns, and any tensions between domains (e.g., technical precision "
    "in engineering vs approachability in customer-facing work). This profile will be "
    "injected into all future sessions across all domains. Be specific, actionable, and "
    "note where patterns reinforce or contradict each other. No pleasantries."
)


class MemoryConsolidationService:
    """L2 memory consolidation: synthesize raw insights into patterns."""

    def __init__(self, db=None, llm_provider=None):
        self._db = db
        self._llm = llm_provider
        self._last_run: float = 0.0
        logger.info("Memory consolidation service initialized")

    @property
    def enabled(self) -> bool:
        return self._db is not None and cfg.MEMORY_CONSOLIDATION_ENABLED

    def find_consolidation_candidates(self, limit: int = 10) -> list[dict]:
        """
        Find user+pack combos with ≥ threshold un-consolidated insights.

        Returns list of {user_id, pack_id, count} dicts.
        """
        if not self.enabled:
            return []

        threshold = cfg.MEMORY_CONSOLIDATION_THRESHOLD

        try:
            # Find journals with insights that haven't been consolidated yet
            # (embedded_at IS NULL used as consolidation marker)
            result = self._db.rpc(
                "find_consolidation_candidates",
                {"threshold_count": threshold, "max_results": limit},
            ).execute()
            if result.data:
                return result.data
        except Exception:
            # RPC may not exist — fall back to manual query
            pass

        # Fallback: manual query approach
        try:
            result = (
                self._db.table("session_journals")
                .select("user_id, pack_id")
                .not_.is_("insight", "null")
                .is_("embedded_at", "null")
                .execute()
            )
            rows = result.data if result and result.data else []
            if not rows:
                return []

            # Group by user_id + pack_id
            groups: dict[str, dict] = {}
            for row in rows:
                key = f"{row['user_id']}|{row.get('pack_id', '')}"
                if key not in groups:
                    groups[key] = {
                        "user_id": row["user_id"],
                        "pack_id": row.get("pack_id", ""),
                        "count": 0,
                    }
                groups[key]["count"] += 1

            # Filter by threshold
            candidates = [g for g in groups.values() if g["count"] >= threshold]
            candidates.sort(key=lambda g: g["count"], reverse=True)
            return candidates[:limit]
        except Exception as e:
            logger.warning("Consolidation candidate search failed: %s", e)
            return []

    async def consolidate_user_pack(
        self, user_id: str, pack_id: str
    ) -> dict | None:
        """
        Consolidate un-consolidated insights for a user+pack.

        Fetches insights, calls Haiku for synthesis, stores result,
        marks journals, and embeds the summary.
        Returns the consolidation row on success, None on failure.
        """
        if not self.enabled:
            return None

        try:
            # Fetch un-consolidated insights
            query = (
                self._db.table("session_journals")
                .select("id, insight, pack_id, cartridges_visited, session_ended_at")
                .eq("user_id", user_id)
                .not_.is_("insight", "null")
                .is_("embedded_at", "null")
                .order("session_ended_at", desc=True)
                .limit(20)
            )
            if pack_id:
                query = query.eq("pack_id", pack_id)
            result = query.execute()
            journals = result.data if result and result.data else []
        except Exception as e:
            logger.warning("Fetch journals for consolidation failed: %s", e)
            return None

        if len(journals) < cfg.MEMORY_CONSOLIDATION_THRESHOLD:
            return None

        # Build synthesis prompt
        insight_lines = []
        journal_ids = []
        for j in journals:
            insight = j.get("insight", "").strip()
            if insight:
                pack = j.get("pack_id", "unknown")
                date = (j.get("session_ended_at") or "")[:10]
                insight_lines.append(f"- [{pack}, {date}] {insight}")
                journal_ids.append(j["id"])

        if not insight_lines:
            return None

        pack_label = pack_id if pack_id else "cross-pack"
        user_msg = (
            f"User has {len(insight_lines)} session insights across {pack_label}:\n\n"
            + "\n".join(insight_lines)
        )

        # Call LLM for synthesis
        summary = await self._synthesize(user_msg)
        if not summary:
            return None

        # Store consolidation
        try:
            row = {
                "user_id": user_id,
                "pack_id": pack_id or None,
                "summary": summary,
                "source_journal_ids": journal_ids,
                "journal_count": len(journal_ids),
                "confidence": min(0.5 + len(journal_ids) * 0.05, 0.95),
            }
            insert_result = self._db.table("memory_consolidations").insert(row).execute()
            consolidation = insert_result.data[0] if insert_result.data else row
        except Exception as e:
            logger.warning("Store consolidation failed: %s", e)
            return None

        # Supersede older consolidations for same user+pack
        try:
            new_id = consolidation.get("id")
            supersede_query = (
                self._db.table("memory_consolidations")
                .update({"status": "superseded"})
                .eq("user_id", user_id)
                .eq("status", "current")
            )
            if pack_id:
                supersede_query = supersede_query.eq("pack_id", pack_id)
            else:
                supersede_query = supersede_query.is_("pack_id", "null")
            if new_id:
                supersede_query = supersede_query.neq("id", new_id)
            supersede_query.execute()
        except Exception as e:
            logger.warning("Supersede old consolidations failed: %s", e)

        # Mark journals as consolidated
        try:
            now = datetime.now(timezone.utc).isoformat()
            for jid in journal_ids:
                self._db.table("session_journals").update(
                    {"embedded_at": now}
                ).eq("id", jid).execute()
        except Exception as e:
            logger.warning("Mark journals consolidated failed: %s", e)

        # Embed the consolidation (non-fatal)
        try:
            from embedding_pipeline import get_embedding_pipeline
            ep = get_embedding_pipeline()
            if ep:
                ep.embed_consolidation({
                    "id": consolidation.get("id", ""),
                    "summary": summary,
                    "user_id": user_id,
                    "pack_id": pack_id or "",
                })
        except Exception as e:
            logger.debug("Embed consolidation failed: %s", e)

        logger.info(
            "Consolidated %d insights for user=%s pack=%s (%.0f chars)",
            len(journal_ids), user_id[:8], pack_label, len(summary),
        )
        return consolidation

    async def consolidate_cross_pack(self, user_id: str) -> dict | None:
        """Consolidate across all packs for cross-domain patterns."""
        return await self.consolidate_user_pack(user_id, pack_id="")

    # ─── L3: User Identity Model ──────────────────────────

    async def build_user_identity(self, user_id: str) -> dict | None:
        """
        L3 synthesis: build a unified user identity model from all current
        L2 consolidations across packs. Supersedes any prior identity model.

        Returns the identity row on success, None if insufficient data.
        """
        if not self.enabled:
            return None

        try:
            result = (
                self._db.table("memory_consolidations")
                .select("id, summary, pack_id, confidence, journal_count, created_at")
                .eq("user_id", user_id)
                .eq("status", "current")
                .order("created_at", desc=True)
                .limit(20)
                .execute()
            )
            consolidations = result.data if result and result.data else []
        except Exception as e:
            logger.warning("L3 identity: fetch consolidations failed: %s", e)
            return None

        # Need consolidations from at least 2 different packs
        pack_ids = list(set(c.get("pack_id") or "cross-pack" for c in consolidations))
        if len(consolidations) < 2:
            return None

        # Build synthesis prompt
        lines = []
        consolidation_ids = []
        for c in consolidations:
            pack = c.get("pack_id") or "cross-pack"
            count = c.get("journal_count", 0)
            summary = c.get("summary", "").strip()
            if summary:
                lines.append(f"- [{pack}, {count} sessions] {summary}")
                consolidation_ids.append(c["id"])

        if len(lines) < 2:
            return None

        user_msg = (
            f"User has {len(lines)} consolidated pattern summaries across "
            f"{len(pack_ids)} domains ({', '.join(pack_ids)}):\n\n"
            + "\n".join(lines)
        )

        # Call LLM for L3 synthesis
        summary = await self._synthesize_identity(user_msg)
        if not summary:
            return None

        # Supersede any existing current identity model
        try:
            self._db.table("user_identity_models").update(
                {"status": "superseded"}
            ).eq("user_id", user_id).eq("status", "current").execute()
        except Exception as e:
            logger.warning("L3 identity: supersede old models failed: %s", e)

        # Store new identity model
        try:
            row = {
                "user_id": user_id,
                "summary": summary,
                "source_consolidation_ids": consolidation_ids,
                "consolidation_count": len(consolidation_ids),
                "pack_ids": pack_ids,
                "confidence": min(0.5 + len(consolidation_ids) * 0.05, 0.95),
            }
            insert_result = self._db.table("user_identity_models").insert(row).execute()
            identity = insert_result.data[0] if insert_result.data else row
        except Exception as e:
            logger.warning("L3 identity: store failed: %s", e)
            return None

        logger.info(
            "L3 identity model built for user=%s from %d consolidations across %s",
            user_id[:8], len(consolidation_ids), pack_ids,
        )
        return identity

    def fetch_user_identity(
        self, user_id: str, max_tokens: int = 600
    ) -> str:
        """
        Fetch the current [USER IDENTITY] block for prompt injection.

        Returns "" for anonymous users or when no identity model exists.
        """
        if not self.enabled:
            return ""
        if not user_id or user_id == "anonymous":
            return ""

        try:
            result = (
                self._db.table("user_identity_models")
                .select("summary, pack_ids, consolidation_count, confidence, created_at")
                .eq("user_id", user_id)
                .eq("status", "current")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            rows = result.data if result and result.data else []
        except Exception as e:
            logger.warning("Fetch user identity failed: %s", e)
            return ""

        if not rows:
            return ""

        identity = rows[0]
        summary = identity.get("summary", "")
        if not summary:
            return ""

        packs = identity.get("pack_ids", [])
        count = identity.get("consolidation_count", 0)
        char_budget = max_tokens * 4

        lines = [
            "[USER IDENTITY — Cross-domain synthesized profile]",
            f"Derived from {count} pattern summaries across {', '.join(packs)}.",
            "Use this to personalize tone, anticipate needs, and maintain continuity.",
            "",
            summary[:char_budget - 200],
            "",
            "[/USER IDENTITY]",
        ]
        return "\n".join(lines)

    async def _synthesize_identity(self, user_msg: str) -> str:
        """Call LLM for L3 identity synthesis. Returns '' on failure."""
        if not self._llm:
            return ""
        try:
            response = await self._llm.generate(
                system=_IDENTITY_SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
                max_tokens=500,
            )
            return response.text.strip() if response and response.text else ""
        except Exception as e:
            logger.warning("L3 identity synthesis LLM call failed: %s", e)
            return ""

    def fetch_consolidated_memory(
        self,
        user_id: str,
        pack_id: str | None = None,
        max_tokens: int = None,
    ) -> str:
        """
        Fetch and format [CONSOLIDATED MEMORY] block from stored consolidations.

        Returns "" for anonymous users or when no consolidations exist.
        """
        if not self.enabled:
            return ""
        if not user_id or user_id == "anonymous":
            return ""

        if max_tokens is None:
            max_tokens = cfg.MEMORY_CONSOLIDATION_MAX_TOKENS

        try:
            # Fetch pack-specific consolidations first, then cross-pack
            consolidations = []

            if pack_id:
                result = (
                    self._db.table("memory_consolidations")
                    .select("summary, pack_id, confidence, journal_count, created_at")
                    .eq("user_id", user_id)
                    .eq("pack_id", pack_id)
                    .eq("status", "current")
                    .order("created_at", desc=True)
                    .limit(3)
                    .execute()
                )
                consolidations.extend(result.data if result and result.data else [])

            # Cross-pack consolidations
            result = (
                self._db.table("memory_consolidations")
                .select("summary, pack_id, confidence, journal_count, created_at")
                .eq("user_id", user_id)
                .is_("pack_id", "null")
                .eq("status", "current")
                .order("created_at", desc=True)
                .limit(2)
                .execute()
            )
            consolidations.extend(result.data if result and result.data else [])

            if not consolidations:
                return ""

            return self._format_consolidated_block(consolidations, max_tokens)
        except Exception as e:
            logger.warning("Fetch consolidated memory failed: %s", e)
            return ""

    def should_run(self) -> bool:
        """Check if enough time has passed since last consolidation run."""
        if not self.enabled:
            return False
        interval_seconds = cfg.MEMORY_CONSOLIDATION_INTERVAL_HOURS * 3600
        return (time.time() - self._last_run) >= interval_seconds

    def mark_run(self):
        """Mark that a consolidation run just completed."""
        self._last_run = time.time()

    async def _synthesize(self, user_msg: str) -> str:
        """Call LLM (Haiku) for memory synthesis. Returns "" on failure."""
        if not self._llm:
            return ""
        try:
            response = await self._llm.generate(
                system=_SYNTHESIS_SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
                max_tokens=300,
            )
            return response.text.strip() if response and response.text else ""
        except Exception as e:
            logger.warning("Memory synthesis LLM call failed: %s", e)
            return ""

    @staticmethod
    def _format_consolidated_block(
        consolidations: list[dict], max_tokens: int
    ) -> str:
        """Format consolidations into [CONSOLIDATED MEMORY] block."""
        char_budget = max_tokens * 4
        lines = [
            "[CONSOLIDATED MEMORY — Synthesized user patterns]",
            "The following patterns have been identified across multiple sessions.",
            "Use these to personalize without explicitly citing them.",
            "",
        ]
        header_len = sum(len(l) + 1 for l in lines)
        footer = "\n[/CONSOLIDATED MEMORY]"
        used = header_len + len(footer)

        for c in consolidations:
            summary = c.get("summary", "")
            if not summary:
                continue
            pack = c.get("pack_id") or "cross-pack"
            count = c.get("journal_count", 0)
            entry = f"- [{pack}, {count} sessions] {summary}"
            entry_len = len(entry) + 1
            if used + entry_len > char_budget:
                break
            lines.append(entry)
            used += entry_len

        if len(lines) <= 4:  # only header
            return ""

        return "\n".join(lines) + footer


# ─── Singleton ────────────────────────────────────────────

_memory_consolidation: Optional[MemoryConsolidationService] = None


def init_memory_consolidation(
    db=None, llm_provider=None
) -> MemoryConsolidationService:
    """Initialize the global MemoryConsolidationService singleton."""
    global _memory_consolidation
    _memory_consolidation = MemoryConsolidationService(db=db, llm_provider=llm_provider)
    return _memory_consolidation


def get_memory_consolidation() -> Optional[MemoryConsolidationService]:
    """Return the global MemoryConsolidationService or None."""
    return _memory_consolidation
