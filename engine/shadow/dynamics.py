"""
engine/shadow/dynamics.py — K(x) accumulation, contagion, and inter-agent transfer.

The physics of how darkness propagates through a population.
"""

import random
import time
from typing import List, Optional
from dataclasses import dataclass

from .archetypes import SHADOW_ARCHETYPES, SHADOW_K_CEILING


@dataclass
class ContagionEvent:
    source_agent_id: str
    target_agent_id: str
    k_transferred: float
    mechanism: str  # "predatory", "ideological", "collective", "institutional", "enablement", "confusion"
    session_id: str
    tick: int


@dataclass
class AccumulationEvent:
    agent_id: str
    k_before: float
    k_after: float
    k_delta: float
    protocol_name: str
    shadow_arch: str
    tick: int


# Intervention window durations (in ticks)
INTERVENTION_WINDOWS = {
    "ADC": 2,
    "IDL": 1,
    "PRD": 3,
    "CVL": 3,
    "DSS": 2,
    "CRP": 3,
}


def compute_shadow_k_delta(
    agent_k: float,
    agent_lambda: float,
    agent_coherence: float,
    protocol: dict,
    context_k_modifier: float,
    context_lambda_modifier: float,
    shadow_arch: str,
    session_output: str,
    is_crystallized: bool,
) -> float:
    """
    Compute K(x) delta for a shadow protocol session.
    Can return POSITIVE values (accumulation) for non-resolution protocols.
    Clamped to [-0.5, +2.0].
    """
    is_resolution = protocol.get("is_resolution", False)
    is_bridge = protocol.get("is_bridge", False)
    base_delta = protocol.get("k_delta_base", 0.2)

    if is_resolution:
        # Resolution: negative delta (progress toward exit)
        delta = -abs(base_delta)
        # Crystallization halves resolution effectiveness
        if is_crystallized:
            delta *= 0.5
        # Higher lambda = faster resolution
        delta *= (1.0 + agent_lambda * 0.1)
    elif is_bridge:
        # Bridge: small negative delta
        delta = -abs(base_delta) * 0.5
    else:
        # Active shadow: positive delta (accumulation)
        delta = abs(base_delta)
        # High context K amplifies accumulation
        if context_k_modifier > 1.5:
            delta *= 1.3
        # Low coherence amplifies accumulation
        if agent_coherence < 0.3:
            delta *= 1.5
        # Crystallized state amplifies accumulation
        if is_crystallized:
            delta *= 1.2
        # Suppress lambda effect for active shadow
        delta += SHADOW_ARCHETYPES[shadow_arch].avg_lambda_suppression * 0.05

    # Session engagement modifier
    output_len = len(session_output)
    if output_len > 500:
        delta *= 1.2 if delta > 0 else 1.3  # Engagement amplifies both directions

    # Random variance
    delta += random.gauss(0, 0.03)

    # Clamp
    delta = max(-0.5, min(2.0, delta))

    # Enforce K ceiling
    if agent_k + delta > SHADOW_K_CEILING:
        delta = SHADOW_K_CEILING - agent_k

    return round(delta, 4)


def compute_contagion(
    source_agent: dict,
    all_agents: List[dict],
    shadow_protocol: dict,
    tick: int,
) -> List[ContagionEvent]:
    """
    Compute K(x) contagion from a shadow session to nearby agents.
    """
    events = []
    k_transfer = shadow_protocol.get("k_transfer", 0.0)
    if k_transfer <= 0:
        return events

    shadow_domain = shadow_protocol.get("shadow_domain", "")
    contagion_radius = shadow_protocol.get("contagion_radius", 0)
    source_id = source_agent.get("id", "")
    source_plane = source_agent.get("plane", 0)

    # Filter eligible targets
    targets = [
        a for a in all_agents
        if a["id"] != source_id
        and not a.get("is_liberated")
    ]

    if not targets:
        return events

    mechanism_map = {
        "predatory": "predatory",
        "radicalization": "ideological",
        "collective_violence": "collective",
        "institutional_corruption": "institutional",
        "addiction": "enablement",
        "dissociation": "confusion",
    }
    mechanism = mechanism_map.get(shadow_domain, "unknown")

    if shadow_domain == "predatory":
        # Direct: 1 specific target (most vulnerable)
        sorted_targets = sorted(targets, key=lambda a: a.get("coherence", 1.0))
        target = sorted_targets[0]
        vulnerability = 1.0 if target.get("coherence", 0.5) < 0.3 else 0.5
        events.append(ContagionEvent(
            source_agent_id=source_id,
            target_agent_id=target["id"],
            k_transferred=round(k_transfer * vulnerability, 4),
            mechanism=mechanism,
            session_id="",
            tick=tick,
        ))

    elif shadow_domain == "radicalization":
        # Broadcast: same plane, low coherence
        for t in targets:
            if t.get("plane") == source_plane and t.get("coherence", 1.0) < 0.5:
                vulnerability = 1.0 - t.get("coherence", 0.5)
                events.append(ContagionEvent(
                    source_agent_id=source_id,
                    target_agent_id=t["id"],
                    k_transferred=round(k_transfer * vulnerability * 0.3, 4),
                    mechanism=mechanism,
                    session_id="",
                    tick=tick,
                ))

    elif shadow_domain == "collective_violence":
        # Field: all agents in same plane
        for t in targets:
            if abs(t.get("plane", 0) - source_plane) <= 1:
                coh = t.get("coherence", 0.5)
                resistance = 0.3 if coh > 0.7 else 1.0
                events.append(ContagionEvent(
                    source_agent_id=source_id,
                    target_agent_id=t["id"],
                    k_transferred=round(k_transfer * resistance * 0.5, 4),
                    mechanism=mechanism,
                    session_id="",
                    tick=tick,
                ))

    elif shadow_domain == "institutional_corruption":
        # Systemic: all agents in same or adjacent plane
        for t in targets:
            if abs(t.get("plane", 0) - source_plane) <= 1:
                events.append(ContagionEvent(
                    source_agent_id=source_id,
                    target_agent_id=t["id"],
                    k_transferred=round(k_transfer * 0.2, 4),
                    mechanism=mechanism,
                    session_id="",
                    tick=tick,
                ))

    elif shadow_domain == "addiction":
        # Relational: agents in adjacent planes (closest relationships)
        closest = sorted(targets, key=lambda a: abs(a.get("plane", 0) - source_plane))[:2]
        for t in closest:
            events.append(ContagionEvent(
                source_agent_id=source_id,
                target_agent_id=t["id"],
                k_transferred=round(k_transfer * 0.4, 4),
                mechanism=mechanism,
                session_id="",
                tick=tick,
            ))

    elif shadow_domain == "dissociation":
        # Confusion: direct interaction partner (1 random nearby agent)
        nearby = [t for t in targets if abs(t.get("plane", 0) - source_plane) <= 1]
        if nearby:
            target = random.choice(nearby)
            events.append(ContagionEvent(
                source_agent_id=source_id,
                target_agent_id=target["id"],
                k_transferred=round(k_transfer * 0.15, 4),
                mechanism=mechanism,
                session_id="",
                tick=tick,
            ))

    return events


def check_crystallization(
    agent: dict,
    session_history: List[dict],
    shadow_arch: str,
) -> bool:
    """
    Check whether an agent has crystallized into their shadow archetype.
    """
    shadow_sessions = [
        s for s in session_history
        if s.get("is_shadow_session") and not s.get("is_resolution")
    ]

    if shadow_arch == "PRD":
        # 5+ predatory sessions with k_transfer > 0
        predatory = [s for s in shadow_sessions if s.get("shadow_domain") == "predatory"]
        return len(predatory) >= 5

    elif shadow_arch == "IDL":
        # Lambda < 0.5 AND 3+ ideological sessions
        ideological = [s for s in shadow_sessions if s.get("shadow_domain") == "radicalization"]
        agent_lambda = agent.get("lambda_coeff", 5.0)
        return agent_lambda < 0.5 and len(ideological) >= 3

    elif shadow_arch == "ADC":
        # 3+ oscillation cycles detected (K goes down then up)
        k_history = [s.get("k_after", 0) for s in session_history if "k_after" in s]
        if len(k_history) < 6:
            return False
        oscillations = 0
        going_down = True
        for i in range(1, len(k_history)):
            if going_down and k_history[i] > k_history[i - 1]:
                going_down = False
            elif not going_down and k_history[i] < k_history[i - 1]:
                going_down = True
                oscillations += 1
        return oscillations >= 3

    elif shadow_arch == "DSS":
        # K(x) variance > 4.0 (simulated as high session K variance)
        k_values = [s.get("k_after", 0) for s in session_history if "k_after" in s]
        if len(k_values) < 4:
            return False
        mean_k = sum(k_values) / len(k_values)
        variance = sum((k - mean_k) ** 2 for k in k_values) / len(k_values)
        return variance > 4.0

    elif shadow_arch == "CVL":
        # 3+ collective violence sessions (field check handled at simulation level)
        cvl_sessions = [s for s in shadow_sessions if s.get("shadow_domain") == "collective_violence"]
        return len(cvl_sessions) >= 3

    elif shadow_arch == "CRP":
        # 3+ sessions with positive k_delta (corrupted records)
        corrupted = [s for s in shadow_sessions if s.get("k_delta", 0) > 0]
        return len(corrupted) >= 3

    return False


def get_intervention_window(
    agent: dict,
    session_history: List[dict],
    shadow_arch: str,
    current_tick: int,
) -> bool:
    """
    Detect whether an agent is in an intervention window.
    """
    if not session_history:
        return False

    recent = session_history[-5:]  # Look at last 5 sessions

    if shadow_arch == "ADC":
        # Peak of oscillation (K just went up after going down)
        k_vals = [s.get("k_after", 0) for s in recent]
        if len(k_vals) >= 3:
            # K increased in last session after decreasing
            if k_vals[-1] > k_vals[-2] and k_vals[-2] < k_vals[-3]:
                return True

    elif shadow_arch == "PRD":
        # After a predatory session that produced unexpected resistance (low k_transfer)
        last = recent[-1] if recent else {}
        if last.get("shadow_domain") == "predatory":
            # If the session output was shorter than usual (resistance)
            excerpt = last.get("session_excerpt", "")
            if len(excerpt) < 100:
                return True

    elif shadow_arch == "IDL":
        # After any session with a non-ideological protocol (paradox encounter)
        last = recent[-1] if recent else {}
        if not last.get("is_shadow_session", False):
            return True

    elif shadow_arch == "CVL":
        # After any session mentioning "consequence" or "witness"
        last = recent[-1] if recent else {}
        excerpt = last.get("session_excerpt", "").lower()
        if "consequence" in excerpt or "witness" in excerpt or "victim" in excerpt:
            return True

    elif shadow_arch == "DSS":
        # During state switch (coherence spike between sessions)
        if len(recent) >= 2:
            last_coh = recent[-1].get("coherence_after", 0)
            prev_coh = recent[-2].get("coherence_after", 0)
            if last_coh > prev_coh + 0.1:  # Coherence spike
                return True

    elif shadow_arch == "CRP":
        # When audit risk becomes salient (random chance per tick)
        return random.random() < 0.15  # 15% chance per check

    return False


def apply_contagion_events(
    events: List[ContagionEvent],
    vault,
) -> int:
    """
    Apply contagion K(x) transfers to target agents.
    Write contagion events to vault.
    Returns count of events applied.
    """
    applied = 0
    for event in events:
        target = vault.get_agent(event.target_agent_id)
        if not target:
            continue

        # Apply K transfer (capped at SHADOW_K_CEILING)
        new_k = min(SHADOW_K_CEILING, target["k_current"] + event.k_transferred)
        vault.update_agent(event.target_agent_id, {"k_current": round(new_k, 4)})

        # Write contagion record
        vault.write_contagion_event(event)
        applied += 1

    return applied
