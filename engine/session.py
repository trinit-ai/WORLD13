"""
engine/session.py — Session runner for WORLD13.

Calls the Anthropic API with a protocol as behavioral context,
runs a governed conversation turn, extracts the deliverable, computes K(x) delta.
"""

import os
import time
import json
import math
import random
from typing import Optional

from .agent import Agent
from .protocols import select_protocol
from .context import sample_context, ContextualEnvelope
from .tvr import TVRCoordinates

SESSION_MODEL = os.environ.get("WORLD13_MODEL", "claude-sonnet-4-5-20250929")


def build_session_prompt(agent: Agent, protocol: dict, context: ContextualEnvelope) -> str:
    """Build the system prompt for the session."""
    # Gather top 3 most impactful context conditions
    ctx_summary = context.summary(top_n=3) if hasattr(context, "summary") else "standard conditions"

    return f"""You are an autonomous agent in WORLD13 — a persistent civilization simulation governed by the Ventura Recursion (TVR).

AGENT IDENTITY:
- Name: {agent.name}
- Plane: {agent.tvr.plane} ({_plane_name(agent.tvr.plane)})
- Primary Archetype: {agent.tvr.primary_arch} ({_arch_name(agent.tvr.primary_arch)})
- Secondary: {agent.tvr.secondary_arch} | Tertiary: {agent.tvr.tertiary_arch}
- Current K(x): {agent.k_current:.3f} (karmic inertia — lower is closer to liberation)
- Coherence: {agent.current_coherence:.3f} (pattern recognition — higher is more aware)
- Cycle Phase: {agent.tvr.cycle_phase}
- Incarnation: {agent.tvr.incarnation_n}

PROTOCOL: {protocol.get('name', 'Unknown')}
- Domain: {protocol.get('domain', 'General')}
- This session type: {_phase_description(agent.tvr.cycle_phase)}

CONTEXTUAL CONDITIONS:
{ctx_summary}

INSTRUCTION: Conduct a single-turn session within this protocol domain. Respond as the agent would — shaped by your archetype, your plane of operation, and your current cycle phase. Produce a structured deliverable: a brief report, reflection, or outcome from this session (200-400 words). The deliverable should reflect genuine engagement with the protocol's domain.

Do not break character. Do not reference being an AI. You are {agent.name}, operating within the simulation."""


def build_user_prompt(agent: Agent, protocol: dict) -> str:
    """The user turn initiating the session."""
    phase = agent.tvr.cycle_phase
    domain = protocol.get("domain", "general practice")
    name = protocol.get("name", "session")

    prompts = {
        "ACC": f"Begin your regular {domain} session: {name}. Engage with the material as you normally would.",
        "CRS": f"You are at a crisis point in your {domain} work. The session '{name}' demands confrontation with what you've been avoiding. Face it.",
        "RES": f"Integration phase. Your {domain} session '{name}' is about resolving what the crisis revealed. Find the synthesis.",
        "TRN": f"Transition. Your {domain} session '{name}' is about letting go of what no longer serves. What do you release?",
        "LIB": f"Contemplation. In this {domain} session '{name}', you are close to liberation. What remains?",
    }
    return prompts.get(phase, prompts["ACC"])


def compute_k_delta(agent: Agent, protocol: dict, context: ContextualEnvelope,
                    session_output: str) -> float:
    """
    Compute the K(x) change from this session.
    Returns negative float (K reduction) or small positive (crisis accumulation).
    Clamped to [-0.5, +0.3].
    """
    effective_lambda = context.effective_lambda(agent.tvr.lambda_coeff)
    base_delta = -0.05 * effective_lambda

    phase = agent.tvr.cycle_phase
    if phase == "LIB":
        base_delta *= 2.5
    elif phase == "CRS":
        base_delta *= 0.5
    elif phase == "TRN":
        base_delta *= 1.8

    if context.lambda_total_modifier > 1.5:
        base_delta *= 1.5
    if context.k_total_modifier > 1.5:
        base_delta *= 0.3

    if len(session_output) > 500:
        base_delta *= 1.2

    # Small random variance
    base_delta += random.gauss(0, 0.02)

    return max(-0.5, min(0.3, base_delta))


async def run_session(agent: Agent, vault) -> dict:
    """
    Run one full session for an agent:
    1. Select protocol  2. Sample context  3. Build prompts
    4. Call Anthropic API  5. Compute K(x) delta
    6. Write to Vault  7. Update agent state  8. Return summary
    """
    start_time = time.time()
    k_before = agent.k_current

    # 1. Select protocol
    protocol = select_protocol(
        agent.tvr.plane, agent.tvr.primary_arch,
        agent.k_current, agent.tvr.karmic_phi,
    )

    # 2. Sample context
    context = sample_context(agent.tvr)
    context.agent_id = agent.id

    # 3. Build prompts
    system_prompt = build_session_prompt(agent, protocol, context)
    user_prompt = build_user_prompt(agent, protocol)

    # 4. Call Anthropic API
    session_output = await _call_anthropic(system_prompt, user_prompt)

    # 5. Compute K(x) delta
    k_delta = compute_k_delta(agent, protocol, context, session_output)

    # 6. Write to Vault
    vault_record_id = vault.write_session(
        agent_id=agent.id,
        protocol=protocol,
        tvr_coords=agent.tvr,
        context=context,
        session_content=session_output,
        k_delta=k_delta,
    )

    # 7. Update agent state
    agent.update_after_session(k_delta)

    # Update agent in vault DB
    vault.update_agent(agent.id, {
        "k_current": round(agent.k_current, 4),
        "coherence": round(agent.current_coherence, 4),
        "cycle_phase": agent.tvr.cycle_phase,
        "incarnation_n": agent.tvr.incarnation_n,
        "sessions_completed": agent.sessions_completed,
        "liberation_events": agent.liberation_events,
        "is_liberated": 1 if agent.is_liberated_flag else 0,
        "last_session_at": agent.last_session_at,
    })

    duration = time.time() - start_time

    # 8. Return summary
    return {
        "agent_id": agent.id,
        "agent_name": agent.name,
        "protocol_name": protocol.get("name", "Unknown"),
        "domain": protocol.get("domain", "Unknown"),
        "plane": agent.tvr.plane,
        "k_before": round(k_before, 4),
        "k_after": round(agent.k_current, 4),
        "k_delta": round(k_delta, 4),
        "coherence_after": round(agent.current_coherence, 4),
        "cycle_phase": agent.tvr.cycle_phase,
        "context_summary": context.summary(top_n=3) if hasattr(context, "summary") else "",
        "session_excerpt": session_output[:200],
        "is_liberated": agent.is_liberated_flag,
        "vault_record_id": vault_record_id,
        "duration_seconds": round(duration, 2),
    }


async def _call_anthropic(system_prompt: str, user_prompt: str) -> str:
    """Call the Anthropic API. Falls back to synthetic output on failure."""
    try:
        import anthropic
        client = anthropic.AsyncAnthropic()
        response = await client.messages.create(
            model=SESSION_MODEL,
            max_tokens=600,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text
    except Exception as e:
        # Fallback: synthesize a session output
        return _synthetic_output(system_prompt, user_prompt, str(e))


def _synthetic_output(system_prompt: str, user_prompt: str, error: str = "") -> str:
    """Generate a fallback session output when the API is unavailable."""
    return (
        f"[Synthetic session — API unavailable: {error[:100]}]\n\n"
        "The agent engaged with the protocol domain as prescribed by their archetypal orientation. "
        "The session proceeded through standard phases: opening awareness, engagement with material, "
        "and integration of insights. Karmic patterns were noted but not fully resolved. "
        "The work continues in the next session cycle."
    )


def _plane_name(plane_id: int) -> str:
    names = {1: "Material/Physical", 2: "Vital/Relational", 3: "Mental/Formal",
             4: "Integrative/Professional", 5: "Creative/Expressive",
             6: "Self/Reflective", 7: "Transpersonal/Unitive"}
    return names.get(plane_id, "Unknown")


def _arch_name(code: str) -> str:
    names = {"SOV": "Sovereign", "BLD": "Builder", "SKR": "Seeker", "WIT": "Witness",
             "WAR": "Warrior", "HLR": "Healer", "TRN": "Transmuter", "TRK": "Trickster",
             "LVR": "Lover", "TCH": "Teacher", "JDG": "Judge", "MYS": "Mystic", "WLD": "World"}
    return names.get(code, code)


def _phase_description(phase: str) -> str:
    descs = {
        "ACC": "Accumulation — routine engagement, building patterns",
        "CRS": "Crisis — confrontation with unresolved material",
        "RES": "Resolution — integration and synthesis",
        "TRN": "Transition — releasing what no longer serves",
        "LIB": "Liberation — approaching zero karmic inertia",
    }
    return descs.get(phase, "Standard engagement")
