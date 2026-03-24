"""
TMOS13 AI-to-AI Session Guardrails — Fibonacci Plume Node 4

Prevents runaway autonomous sessions between AI ambassadors.
Structurally distinct from distillation_guard (which detects adversarial
humans). These guardrails enforce turn budgets and stall detection for
AI-to-AI exchanges.

Design principle (from Recursion Test ontology): "AI must never run
unattended without bounded constraints." Every AI session gets a turn
budget, stall detection, and mandatory human approval for delivery.

Follows vault_rag.py pattern: pure functions, env config, no class needed.
"""
import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("tmos13.ai_guardrails")

# ─── Configuration ─────────────────────────────────────────

TMOS13_AI_GUARDRAILS_ENABLED = os.environ.get(
    "TMOS13_AI_GUARDRAILS_ENABLED", "true"
).lower() in ("true", "1", "yes")

TMOS13_MAX_AI_TURNS = int(os.environ.get("TMOS13_MAX_AI_TURNS", "30"))

TMOS13_AI_STALL_REMINDER = int(os.environ.get("TMOS13_AI_STALL_REMINDER", "3"))

TMOS13_AI_STALL_TERMINATE = int(os.environ.get("TMOS13_AI_STALL_TERMINATE", "5"))

# Minimum response length (chars) to count as substantive
_MIN_SUBSTANTIVE_LENGTH = 20

_STALL_REMINDER_TEXT = (
    "[SYSTEM: This AI-to-AI session appears stalled. "
    "Please provide a substantive response or the session will be terminated. "
    "Remaining turns: {remaining}]"
)


# ─── Result Type ───────────────────────────────────────────

@dataclass
class GuardrailResult:
    """Result of an AI session guardrail check."""
    allowed: bool = True
    action: str = "continue"          # continue | inject_reminder | terminate
    reason: str = ""
    remaining_turns: int = 0
    inject_text: str = ""


# ─── Core Check ───────────────────────────────────────────

def check_ai_session(state, assistant_response: str = "") -> GuardrailResult:
    """
    Check AI session health. Called once per turn for AI sessions.

    Mutates state: increments ai_turn_count, tracks ai_empty_turns.

    Returns GuardrailResult with action:
      - "continue": session proceeds normally
      - "inject_reminder": stall detected, inject reminder text
      - "terminate": session must end (turn limit or stall limit)
    """
    if not TMOS13_AI_GUARDRAILS_ENABLED:
        return GuardrailResult(allowed=True, action="continue")

    if not getattr(state, "is_ai_session", False):
        return GuardrailResult(allowed=True, action="continue")

    # Increment turn counter
    state.ai_turn_count = getattr(state, "ai_turn_count", 0) + 1
    remaining = max(0, TMOS13_MAX_AI_TURNS - state.ai_turn_count)

    # Hard turn limit
    if state.ai_turn_count > TMOS13_MAX_AI_TURNS:
        logger.warning(
            "AI guardrail TERMINATE: turn limit reached session=%s turns=%d",
            getattr(state, "session_id", "?"), state.ai_turn_count,
        )
        return GuardrailResult(
            allowed=False,
            action="terminate",
            reason=f"AI session turn limit reached ({TMOS13_MAX_AI_TURNS} turns).",
            remaining_turns=0,
        )

    # Stall detection
    response_stripped = (assistant_response or "").strip()
    if len(response_stripped) < _MIN_SUBSTANTIVE_LENGTH:
        state.ai_empty_turns = getattr(state, "ai_empty_turns", 0) + 1
    else:
        state.ai_empty_turns = 0

    # Stall terminate
    if state.ai_empty_turns >= TMOS13_AI_STALL_TERMINATE:
        logger.warning(
            "AI guardrail TERMINATE: stall limit session=%s empty_turns=%d",
            getattr(state, "session_id", "?"), state.ai_empty_turns,
        )
        return GuardrailResult(
            allowed=False,
            action="terminate",
            reason=f"AI session terminated: {state.ai_empty_turns} consecutive empty responses.",
            remaining_turns=remaining,
        )

    # Stall reminder
    if state.ai_empty_turns >= TMOS13_AI_STALL_REMINDER:
        logger.info(
            "AI guardrail REMINDER: stall detected session=%s empty_turns=%d",
            getattr(state, "session_id", "?"), state.ai_empty_turns,
        )
        return GuardrailResult(
            allowed=True,
            action="inject_reminder",
            reason="Stall detected in AI session.",
            remaining_turns=remaining,
            inject_text=_STALL_REMINDER_TEXT.format(remaining=remaining),
        )

    return GuardrailResult(
        allowed=True,
        action="continue",
        remaining_turns=remaining,
    )


# ─── Schema Validation ───────────────────────────────────

def validate_ai_session_creation(pack_manifest: dict) -> tuple[bool, str]:
    """
    Validate that a pack is eligible for AI-to-AI sessions.

    Requires:
      - deliverables.enabled = true
      - At least one deliverable type defined
      - Guardrails not globally disabled

    Returns (allowed, error_message). error_message is "" on success.
    """
    if not TMOS13_AI_GUARDRAILS_ENABLED:
        return False, "AI guardrails are disabled globally."

    deliverables = pack_manifest.get("deliverables", {})
    if not deliverables.get("enabled"):
        return False, "Pack does not have deliverables enabled."

    types = deliverables.get("types", [])
    if not types:
        return False, "Pack has no deliverable types defined."

    return True, ""
