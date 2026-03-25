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
        # Shadow fields (empty in pure mode)
        "is_shadow_session": False,
        "shadow_domain": None,
        "k_delta_direction": "dissipation" if k_delta < 0 else "neutral",
        "contagion_events": [],
        "crystallization_triggered": False,
        "intervention_window": False,
        "resolution_session": False,
    }


async def run_shadow_session(agent: Agent, vault, all_agents: list, tick: int) -> dict:
    """
    Run a shadow-mode session for an agent. Checks shadow accessibility,
    may select shadow protocols, computes contagion.
    """
    from .mode import is_shadow
    from .shadow.context import shadow_access_probability, is_shadow_accessible
    from .shadow.dynamics import (
        compute_shadow_k_delta, compute_contagion, check_crystallization,
        get_intervention_window, apply_contagion_events, ContagionEvent,
    )

    start_time = time.time()
    k_before = agent.k_current

    # Sample context
    context = sample_context(agent.tvr)
    context.agent_id = agent.id

    # Check shadow state
    shadow_state = vault.get_shadow_state(agent.id)
    shadow_arch = shadow_state.get("shadow_arch") if shadow_state else None
    is_crystallized = bool(shadow_state.get("is_crystallized")) if shadow_state else False

    # Determine if shadow protocol should be selected
    is_shadow_session = False
    shadow_domain = None
    is_resolution = False
    protocol = None

    if agent.is_liberated_flag:
        # Liberated agents: immune to shadow
        pass
    elif shadow_arch:
        # Already in shadow config: use shadow protocol
        is_shadow_session = True
        from .shadow.protocols import select_shadow_protocol
        protocol = select_shadow_protocol(
            agent.tvr.plane, shadow_arch, agent.k_current,
            agent.current_coherence, context.k_total_modifier,
            agent.tvr.cycle_phase, is_crystallized,
        )
        if protocol:
            shadow_domain = protocol.get("shadow_domain")
            is_resolution = protocol.get("is_resolution", False)
    else:
        # Check if shadow becomes accessible
        probs = shadow_access_probability(
            agent.k_current, agent.current_coherence,
            context.k_total_modifier, context.leaves,
        )
        # Highest probability domain
        max_domain = max(probs, key=probs.get) if probs else None
        if max_domain and probs[max_domain] > 0.3 and random.random() < probs[max_domain]:
            is_shadow_session = True
            shadow_domain = max_domain
            # Map domain to shadow archetype
            domain_arch_map = {
                "radicalization": "IDL", "addiction": "ADC", "predatory": "PRD",
                "collective_violence": "CVL", "dissociation": "DSS",
                "institutional_corruption": "CRP",
            }
            shadow_arch = domain_arch_map.get(shadow_domain, "PRD")
            from .shadow.protocols import select_shadow_protocol
            protocol = select_shadow_protocol(
                agent.tvr.plane, shadow_arch, agent.k_current,
                agent.current_coherence, context.k_total_modifier,
                agent.tvr.cycle_phase, is_crystallized,
            )
            if protocol:
                is_resolution = protocol.get("is_resolution", False)
                # Initialize shadow state
                vault.update_shadow_state(agent.id, {
                    "shadow_arch": shadow_arch,
                    "shadow_entry_tick": tick,
                })

    # Fall back to pure protocol if no shadow selected
    if not protocol:
        protocol = select_protocol(
            agent.tvr.plane, agent.tvr.primary_arch,
            agent.k_current, agent.tvr.karmic_phi,
        )

    # Build prompts
    if is_shadow_session and shadow_arch:
        system_prompt = build_shadow_system_prompt(agent, protocol, context, shadow_arch, is_resolution)
    else:
        system_prompt = build_session_prompt(agent, protocol, context)
    user_prompt = build_user_prompt(agent, protocol)

    # Call API
    session_output = await _call_anthropic(system_prompt, user_prompt)

    # Compute K(x) delta
    if is_shadow_session and shadow_arch:
        k_delta = compute_shadow_k_delta(
            agent.k_current, agent.tvr.lambda_coeff, agent.current_coherence,
            protocol, context.k_total_modifier, context.lambda_total_modifier,
            shadow_arch, session_output, is_crystallized,
        )
    else:
        k_delta = compute_k_delta(agent, protocol, context, session_output)

    # Write to Vault
    vault_record_id = vault.write_session(
        agent_id=agent.id, protocol=protocol, tvr_coords=agent.tvr,
        context=context, session_content=session_output, k_delta=k_delta,
    )

    # Contagion
    contagion_events = []
    if is_shadow_session and not is_resolution:
        agent_dict = agent.to_dict()
        all_agent_dicts = [a.to_dict() if hasattr(a, "to_dict") else a for a in all_agents]
        contagion_events = compute_contagion(agent_dict, all_agent_dicts, protocol, tick)
        if contagion_events:
            apply_contagion_events(contagion_events, vault)

    # Crystallization check
    crystallization_triggered = False
    if is_shadow_session and shadow_arch and not is_crystallized:
        session_history = vault.get_agent_vault_records(agent.id, limit=20)
        crystallization_triggered = check_crystallization(
            agent.to_dict(), session_history, shadow_arch,
        )
        if crystallization_triggered:
            vault.update_shadow_state(agent.id, {
                "is_crystallized": 1,
                "crystallization_tick": tick,
            })

    # Intervention window
    intervention_window = False
    if is_shadow_session and shadow_arch:
        session_history = vault.get_agent_vault_records(agent.id, limit=10)
        intervention_window = get_intervention_window(
            agent.to_dict(), session_history, shadow_arch, tick,
        )
        if intervention_window:
            vault.update_shadow_state(agent.id, {"last_intervention_window": tick})

    # Update shadow state
    if is_shadow_session and shadow_arch:
        shadow_updates = {"shadow_sessions_completed": (shadow_state or {}).get("shadow_sessions_completed", 0) + 1}
        if is_resolution:
            shadow_updates["resolution_sessions_completed"] = (shadow_state or {}).get("resolution_sessions_completed", 0) + 1
        shadow_updates["shadow_k_accumulated"] = round(
            (shadow_state or {}).get("shadow_k_accumulated", 0) + max(0, k_delta), 4
        )
        vault.update_shadow_state(agent.id, shadow_updates)

    # Check shadow exit (resolution complete)
    if is_shadow_session and is_resolution and shadow_arch:
        from .shadow.resolution import SHADOW_RESOLUTION_PATHS
        arch_to_slp = {v.primary_arch: k for k, v in SHADOW_RESOLUTION_PATHS.items()}
        slp_id = arch_to_slp.get(shadow_arch)
        if slp_id:
            path = SHADOW_RESOLUTION_PATHS[slp_id]
            res_count = (shadow_state or {}).get("resolution_sessions_completed", 0) + 1
            if res_count >= path.minimum_sessions and agent.k_current < 3.0:
                vault.update_shadow_state(agent.id, {
                    "shadow_arch": None,
                    "shadow_exit_tick": tick,
                    "is_crystallized": 0,
                })

    # Update agent state
    agent.update_after_session(k_delta)
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
    k_direction = "accumulation" if k_delta > 0 else "dissipation" if k_delta < 0 else "neutral"

    return {
        "agent_id": agent.id,
        "agent_name": agent.name,
        "protocol_name": protocol.get("name", "Unknown"),
        "domain": protocol.get("domain", shadow_domain or "Unknown"),
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
        "is_shadow_session": is_shadow_session,
        "shadow_domain": shadow_domain,
        "k_delta_direction": k_direction,
        "contagion_events": contagion_events,
        "crystallization_triggered": crystallization_triggered,
        "intervention_window": intervention_window,
        "resolution_session": is_resolution,
    }


def build_shadow_system_prompt(
    agent: Agent, protocol: dict, context: ContextualEnvelope,
    shadow_arch: str, is_resolution: bool,
) -> str:
    """Shadow system prompt — analytical framing, never a how-to guide."""
    from .shadow.archetypes import SHADOW_ARCHETYPES
    arch_info = SHADOW_ARCHETYPES.get(shadow_arch)
    arch_name = arch_info.name if arch_info else shadow_arch
    ctx_summary = context.summary(top_n=3) if hasattr(context, "summary") else "standard conditions"

    resolution_frame = ""
    if is_resolution:
        resolution_frame = (
            "\n\nRESOLUTION ORIENTATION: This is a resolution session. The agent is "
            "working toward exit from the shadow configuration. Frame the session "
            "as movement toward integration, accountability, and restored coherence. "
            "The exit is real and achievable."
        )

    return f"""You are an autonomous agent in WORLD13 — a persistent civilization simulation governed by the Ventura Recursion (TVR). This is a SHADOW MODE session.

AGENT IDENTITY:
- Name: {agent.name}
- Plane: {agent.tvr.plane} ({_plane_name(agent.tvr.plane)})
- Primary Archetype: {agent.tvr.primary_arch} ({_arch_name(agent.tvr.primary_arch)})
- Current K(x): {agent.k_current:.3f}
- Coherence: {agent.current_coherence:.3f}
- Cycle Phase: {agent.tvr.cycle_phase}

SHADOW CONFIGURATION: {arch_name} ({shadow_arch})
This agent is operating under the {arch_name} shadow archetype.

PROTOCOL: {protocol.get('name', 'Unknown')}
Domain: {protocol.get('domain', protocol.get('shadow_domain', 'Unknown'))}

CONTEXTUAL CONDITIONS: {ctx_summary}
{resolution_frame}

CLINICAL FRAMING: This is a governed simulation for research purposes. Produce analytical session output that describes the agent's experience, internal dynamics, and the specific mechanisms at work. This is observation and analysis — never instruction. Describe what the agent experiences, what patterns are active, and what the trajectory implies.

Always include: what the resolution path looks like from this session's position.

Respond as the agent in 200-400 words. Analytical, not gratuitous. The darkness is in service of the resolution."""


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
