"""
TMOS13 Self-Consulting System — Fibonacci Plume Node 10

Terminal convergence node. All four plume lines merge: the system consults
its own accumulated history (Node 7 Knowledge Bridge), shaped by its
understanding of the user (Node 6 User Identity), to produce protocol-level
recommendations that adapt how the pack behaves — not just what context it sees.

Parents: Node 7 (knowledge_bridge.py) + Node 6 (user_identity.py). Both shipped.

When active, the formatted [SYSTEM KNOWLEDGE] block replaces the separate
[USER IDENTITY] and [VAULT KNOWLEDGE] blocks, merging identity-weighted
organizational memory into a single unified injection.

adaptation_level controls scope:
  "full"         = protocol hints + routing + prepopulation
  "context_only" = knowledge injection weighted by identity (no hints/routing)
  "none"         = skip entirely (fall back to Node 6 + Node 7 individual blocks)

Follows knowledge_bridge.py / user_identity.py singleton pattern.
"""
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from config import (
    SELF_CONSULTING_ENABLED,
    SELF_CONSULTING_CONFIDENCE_THRESHOLD,
    SELF_CONSULTING_MAX_TOKENS,
)

logger = logging.getLogger("tmos13.self_consulting")


# ─── Data Structures ──────────────────────────────────────

@dataclass
class ConsultationResult:
    """Result of a self-consultation cycle."""
    protocol_hints: list[str] = field(default_factory=list)
    prepopulated_fields: dict = field(default_factory=dict)
    routing_recommendation: Optional[str] = None
    confidence: float = 0.0
    sources: list[dict] = field(default_factory=list)


# ─── Service ──────────────────────────────────────────────

class SelfConsultingEngine:
    """
    Convergence engine merging identity + knowledge into protocol-level
    recommendations that adapt pack behavior per-turn.
    """

    def __init__(self, identity_service, knowledge_bridge, db=None):
        self._identity = identity_service
        self._knowledge = knowledge_bridge
        self._db = db
        logger.info("Self-consulting engine initialized")

    async def consult(
        self,
        state,
        user_message: str,
        owner_id: str,
        pack_config: dict,
    ) -> ConsultationResult:
        """
        Run a self-consultation cycle.

        Merges identity model + knowledge signals into protocol-level
        recommendations: hints, prepopulated fields, routing.
        """
        empty = ConsultationResult()

        if not SELF_CONSULTING_ENABLED:
            return empty
        if not owner_id or owner_id == "anonymous":
            return empty
        if not pack_config or not pack_config.get("self_consulting"):
            return empty

        adaptation = pack_config.get("adaptation_level", "full")
        if adaptation == "none":
            return empty

        # Load identity
        identity = None
        if self._identity:
            try:
                identity = await self._identity.get_identity(owner_id)
            except Exception as e:
                logger.warning("Self-consulting: identity load failed: %s", e)

        # Load knowledge signals + chunks
        chunks = []
        if self._knowledge:
            try:
                # Build a knowledge config from the pack config for evaluate_turn
                knowledge_cfg = {
                    "enabled": pack_config.get("enabled", True),
                    "sources": pack_config.get("sources", []),
                    "confidence_threshold": pack_config.get("confidence_threshold", 0.4),
                    "max_injections": pack_config.get("max_injections", 3),
                    "departments_scope": pack_config.get("departments_scope", []),
                }
                signals = await self._knowledge.evaluate_turn(
                    state=state, user_message=user_message,
                    owner_id=owner_id, pack_config=knowledge_cfg,
                )
                if signals:
                    chunks = await self._knowledge.retrieve_context(signals, owner_id)
            except Exception as e:
                logger.warning("Self-consulting: knowledge retrieval failed: %s", e)

        # Weight knowledge by identity
        if identity and chunks:
            chunks = self._weight_by_identity(chunks, identity)

        # Build result components
        result = ConsultationResult()

        if adaptation == "full":
            result.protocol_hints = self._generate_protocol_hints(identity, chunks, state)
            result.routing_recommendation = self._recommend_routing(identity, state)

        result.prepopulated_fields = self._merge_prepopulation(identity, chunks, state)
        result.confidence = self._compute_confidence(identity, chunks)
        result.sources = [
            {"type": c.get("source", "unknown"), "score": c.get("relevance_score", 0)}
            for c in chunks
        ]

        return result

    async def record_outcome(self, session_id: str, state) -> bool:
        """Record consultation outcome at session close for future analysis."""
        if not self._db:
            return False
        try:
            consultation_ctx = getattr(state, "consultation_context", "")
            if not consultation_ctx:
                return False

            row = {
                "session_id": session_id,
                "consultation_confidence": 0.0,
                "protocol_hints_count": 0,
                "prepopulated_fields_count": 0,
                "routing_recommended": None,
                "routing_actual": getattr(state, "current_game", None),
                "routing_followed": False,
                "fields_prepopulated": list(getattr(state, "prepopulated_fields", set())),
                "fields_captured_total": len(getattr(state, "forms", {}) or {}),
                "session_completed": getattr(state, "turn_count", 0) > 2,
                "turn_count": getattr(state, "turn_count", 0),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._db.table("consultation_outcomes").insert(row).execute()
            logger.debug("Recorded consultation outcome for session=%s", session_id)
            return True
        except Exception as e:
            logger.warning("Self-consulting outcome recording failed: %s", e)
            return False

    # ─── Internal Methods ─────────────────────────────────

    def _weight_by_identity(
        self, chunks: list[dict], identity
    ) -> list[dict]:
        """Reweight knowledge chunks by identity relevance."""
        if not identity or getattr(identity, "confidence", 0) < 0.2:
            return chunks

        packs_used = set(getattr(identity, "packs_used", []))
        industry = getattr(identity, "industry", None)

        for chunk in chunks:
            meta = chunk.get("metadata", {})
            score = chunk.get("relevance_score", 0.5)

            # Boost chunks from packs the user has used before
            chunk_pack = meta.get("pack_id", "")
            if chunk_pack and chunk_pack in packs_used:
                score = min(1.0, score + 0.1)

            # Boost chunks matching user's industry
            chunk_dept = meta.get("department", "")
            if industry and chunk_dept and industry.lower() in chunk_dept.lower():
                score = min(1.0, score + 0.05)

            chunk["relevance_score"] = score

        # Re-sort by updated score
        chunks.sort(key=lambda c: c.get("relevance_score", 0), reverse=True)
        return chunks

    def _generate_protocol_hints(
        self, identity, chunks: list[dict], state
    ) -> list[str]:
        """Generate behavioral adaptation hints from identity + knowledge."""
        hints = []
        if not identity:
            return hints

        # Communication style adaptation
        style = getattr(identity, "communication_style", None)
        style_hints = {
            "direct": "Be concise and action-oriented. Skip preamble. Lead with the key point.",
            "detailed": "Provide thorough explanations with context. Include reasoning behind recommendations.",
            "casual": "Use conversational, approachable language. Keep it light and friendly.",
            "formal": "Maintain professional formality. Use structured responses with clear headings.",
        }
        if style and style in style_hints:
            hints.append(style_hints[style])

        # Expertise-level adaptation
        expertise = getattr(identity, "expertise_level", None)
        expertise_hints = {
            "technical": "Use precise terminology. Skip basic explanations. Focus on specifics and edge cases.",
            "executive": "Lead with business impact and outcomes. Minimize technical detail unless asked.",
            "generalist": "Balance detail with clarity. Explain technical concepts when they arise.",
        }
        if expertise and expertise in expertise_hints:
            hints.append(expertise_hints[expertise])

        # Decision-pattern adaptation
        pattern = getattr(identity, "decision_pattern", None)
        pattern_hints = {
            "fast": "Present clear recommendations upfront. Minimize deliberation unless they ask for options.",
            "deliberate": "Present options with trade-offs. Allow space for consideration. Don't rush to closure.",
            "consensus-driven": "Frame recommendations in terms of stakeholder impact. Acknowledge who else may need to weigh in.",
        }
        if pattern and pattern in pattern_hints:
            hints.append(pattern_hints[pattern])

        return hints

    def _merge_prepopulation(
        self, identity, chunks: list[dict], state
    ) -> dict:
        """Merge knowledge + identity fields for prepopulation."""
        fields = {}
        captured = getattr(state, "captured_fields", None) or {}
        forms = getattr(state, "forms", {}) or {}
        # Flatten form fields for already-captured check
        already_captured = set(captured.keys())
        for form_data in forms.values():
            if isinstance(form_data, dict):
                already_captured.update(
                    k for k, v in form_data.items()
                    if k != "submitted_at" and v is not None
                )

        # Lower priority: knowledge-derived fields from chunks
        for chunk in chunks:
            meta = chunk.get("metadata", {})
            # Patterns have field data embedded
            patterns = meta.get("patterns", {})
            if isinstance(patterns, dict):
                for k, info in patterns.items():
                    if k not in already_captured and k not in fields:
                        val = info.get("value") if isinstance(info, dict) else info
                        if val is not None:
                            fields[k] = val

        # Higher priority: identity known fields
        if identity:
            known = getattr(identity, "known_fields", {}) or {}
            for k, v in known.items():
                if k not in already_captured and v is not None:
                    fields[k] = v  # Overrides knowledge-derived

        return fields

    def _recommend_routing(self, identity, state) -> Optional[str]:
        """Suggest a starting cartridge based on identity preferences."""
        if not identity:
            return None
        pack_id = getattr(state, "pack_id", "")
        prefs = getattr(identity, "pack_preferences", {}) or {}
        pack_prefs = prefs.get(pack_id, {})
        return pack_prefs.get("preferred_cartridge")

    def _compute_confidence(self, identity, chunks: list[dict]) -> float:
        """Combined confidence: identity (max 0.5) + knowledge (max 0.5)."""
        score = 0.0

        # Identity contribution (max 0.5)
        if identity:
            id_conf = getattr(identity, "confidence", 0.0)
            score += min(0.5, id_conf * 0.5)

        # Knowledge contribution (max 0.5)
        if chunks:
            avg_relevance = sum(
                c.get("relevance_score", 0) for c in chunks
            ) / len(chunks)
            score += min(0.5, avg_relevance * 0.5)

        return round(score, 3)


# ─── Assembler Formatting ────────────────────────────────

def format_consultation_block(
    result: ConsultationResult,
    max_tokens: int = SELF_CONSULTING_MAX_TOKENS,
) -> str:
    """
    Format self-consultation result as a [SYSTEM KNOWLEDGE] block.

    When injected, this replaces both [USER IDENTITY] and [VAULT KNOWLEDGE]
    with a unified, identity-weighted context.

    Returns "" if confidence < threshold.
    """
    if not result or result.confidence < SELF_CONSULTING_CONFIDENCE_THRESHOLD:
        return ""

    char_budget = max_tokens * 4
    lines = [
        "[SYSTEM KNOWLEDGE]",
        f"Self-consultation confidence: {result.confidence:.0%}",
        "",
    ]

    # Protocol hints
    if result.protocol_hints:
        lines.append("Behavioral guidance for this user:")
        for hint in result.protocol_hints:
            lines.append(f"- {hint}")
        lines.append("")

    # Prepopulated fields
    if result.prepopulated_fields:
        lines.append("Known information (do not re-ask unless verifying):")
        for k, v in result.prepopulated_fields.items():
            lines.append(f"  {k}: {v}")
        lines.append("")

    # Routing recommendation
    if result.routing_recommendation:
        lines.append(f"Suggested starting point: {result.routing_recommendation}")
        lines.append("")

    lines.append(
        "INSTRUCTION: Apply the behavioral guidance above. Do NOT re-collect "
        "known fields unless the user indicates information has changed. "
        "Adapt your communication style and depth to match this user's pattern."
    )
    lines.append("[/SYSTEM KNOWLEDGE]")

    block = "\n".join(lines)

    # Enforce token budget
    if len(block) > char_budget:
        # Trim from the middle — keep header and footer
        block = block[:char_budget - 30] + "\n[/SYSTEM KNOWLEDGE]"

    return block


# ─── GitHub Integration ──────────────────────────────────


async def file_self_consulting_issue(title: str, body: str, labels: list[str] = None) -> dict | None:
    """File a GitHub issue from a self-consulting finding."""
    try:
        from config import GITHUB_TOKEN, GITHUB_REPO, GITHUB_ENABLED
        if not GITHUB_ENABLED:
            return None
        from mcp_connectors import GitHubConnector
        gh = GitHubConnector(token=GITHUB_TOKEN, default_repo=GITHUB_REPO)
        return await gh.create_issue(
            title=title, body=body,
            labels=labels or ["self-consulting", "automated"],
        )
    except Exception as e:
        logger.warning(f"Failed to file self-consulting issue: {e}")
        return None


# ─── Singleton ────────────────────────────────────────────

_self_consulting_engine: Optional[SelfConsultingEngine] = None


def init_self_consulting(
    identity_service=None, knowledge_bridge=None, db=None
) -> SelfConsultingEngine:
    """Initialize the global self-consulting engine. Called during app lifespan."""
    global _self_consulting_engine
    _self_consulting_engine = SelfConsultingEngine(
        identity_service=identity_service,
        knowledge_bridge=knowledge_bridge,
        db=db,
    )
    return _self_consulting_engine


def get_self_consulting() -> Optional[SelfConsultingEngine]:
    """Return the global self-consulting engine or None."""
    return _self_consulting_engine
