"""
engine/shadow/context.py — Shadow contextual conditions from Set & Setting taxonomy.

Defines the specific combinations of contextual axes that make shadow protocols
accessible in the TVR coordinate system.
"""

from typing import Optional


# Shadow accessibility thresholds per domain.
# When these contextual conditions are present, shadow protocols become adjacent.
SHADOW_ACCESS_CONDITIONS: dict[str, dict] = {

    "radicalization": {
        "high_k_axes": ["S2", "E3"],  # Emotional distress + coercive context
        "threshold_k": 5.5,
        "threshold_coherence": 0.4,
        "context_k_threshold": 2.0,
        "description": (
            "Radicalization becomes adjacent when shame is active, an active "
            "myth is operative, and the agent is in a coercive social context "
            "with suppressed coherence."
        ),
    },

    "addiction": {
        "high_k_axes": ["S1", "S2"],  # Somatic distress + emotional pain
        "threshold_k": 4.0,
        "threshold_coherence": 0.6,  # Can be high-coherence (aware addict)
        "context_k_threshold": 1.0,
        "description": (
            "Addiction protocols become adjacent when substance states are active "
            "and K(x) is elevated. Unlike other shadow domains, addiction can be "
            "accessible even at moderate coherence — the paradox of the aware addict."
        ),
    },

    "predatory": {
        "high_k_axes": ["S2", "E3"],  # Defended ego + power differential
        "threshold_k": 5.0,
        "threshold_coherence": 0.5,
        "context_k_threshold": 1.5,
        "description": (
            "Predatory protocols require defended ego state, compromised intention, "
            "and a power differential."
        ),
    },

    "collective_violence": {
        "high_k_axes": ["E3", "E5"],  # Crowd context + existential threat
        "threshold_k": 5.5,
        "threshold_coherence": 0.35,
        "context_k_threshold": 2.5,
        "description": (
            "Collective violence requires crowd-scale social context, existential "
            "threat framing, active cultural narrative, and fragmented individual "
            "cognition."
        ),
    },

    "dissociation": {
        "high_k_axes": ["S1", "S2"],  # Freeze/shutdown + dissolving ego
        "threshold_k": 4.5,
        "threshold_coherence": 0.5,
        "context_k_threshold": 1.0,
        "description": (
            "Dissociation protocols become adjacent when the nervous system is in "
            "freeze/shutdown, trauma memory is active, ego structure is dissolving."
        ),
    },

    "institutional_corruption": {
        "high_k_axes": ["E3", "E4"],  # Hierarchical context + debt exchange
        "threshold_k": 4.0,
        "threshold_coherence": 0.5,
        "context_k_threshold": 0.8,
        "description": (
            "Institutional corruption requires hierarchical context, debt-based "
            "exchange dynamics, and censored expression — conditions where small "
            "ethical compromises accumulate gradually."
        ),
    },
}


def is_shadow_accessible(
    agent_k: float,
    agent_coherence: float,
    context_k_modifier: float,
    context_leaves: dict,
    shadow_domain: str,
) -> bool:
    """
    Check whether shadow protocols for a given domain are accessible
    to an agent given their current TVR coordinates and contextual envelope.
    """
    cond = SHADOW_ACCESS_CONDITIONS.get(shadow_domain)
    if not cond:
        return False

    # Check K threshold
    if agent_k < cond["threshold_k"]:
        return False

    # Check coherence threshold (must be BELOW threshold)
    if agent_coherence > cond["threshold_coherence"]:
        # Exception: addiction can be accessible at higher coherence
        if shadow_domain != "addiction":
            return False

    # Check context K modifier
    if context_k_modifier < cond["context_k_threshold"]:
        return False

    # Check if relevant axes have high-K leaves active
    relevant_axes = cond.get("high_k_axes", [])
    if context_leaves:
        axis_k_sum = 0.0
        for axis in relevant_axes:
            leaf = context_leaves.get(axis)
            if leaf and hasattr(leaf, "k_modifier"):
                axis_k_sum += leaf.k_modifier
        # At least some K pressure from relevant axes
        if axis_k_sum < 0.5:
            return False

    return True


def shadow_access_probability(
    agent_k: float,
    agent_coherence: float,
    context_k_modifier: float,
    context_leaves: dict,
) -> dict[str, float]:
    """
    Returns probability [0,1] of shadow access for each domain.

    Higher K(x) + lower coherence + higher context K modifier
    = higher shadow access probability.
    """
    probs = {}
    for domain, cond in SHADOW_ACCESS_CONDITIONS.items():
        if not is_shadow_accessible(agent_k, agent_coherence, context_k_modifier,
                                     context_leaves, domain):
            probs[domain] = 0.0
            continue

        # Compute probability based on how far above thresholds the agent is
        k_excess = (agent_k - cond["threshold_k"]) / 5.0  # Normalize
        c_deficit = max(0, cond["threshold_coherence"] - agent_coherence)
        ctx_excess = (context_k_modifier - cond["context_k_threshold"]) / 3.0

        prob = min(0.8, k_excess * 0.3 + c_deficit * 0.4 + ctx_excess * 0.3)
        probs[domain] = max(0.0, prob)

    return probs
