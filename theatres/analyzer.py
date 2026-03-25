"""
theatres/analyzer.py — Post-run analysis for theatre sessions.
"""

from typing import List
from engine.tvr import karmic_inertia, coherence
from engine.archetypes import ARCHETYPES


# Liberation path names
LP_NAMES = {
    "LP-01": "Offering the Work",
    "LP-02": "Arriving — Recognizing Now",
    "LP-03": "Mercy Without Compromise",
    "LP-04": "Healing the Self",
    "LP-05": "Release of Control",
    "LP-06": "Pure Presence",
    "LP-07": "The Last Crossing",
    "LP-08": "Becoming Still",
}


def analyze_run(sessions: List[dict], manifest) -> dict:
    """Analyze a completed theatre run."""

    result = {
        "liberation_path_alignment": {},
        "k_delta_projections": {},
        "question_divergence_map": {"q1_themes": [], "q2_themes": [], "q3_themes": []},
        "life_path_fork_summary": {},
        "civilization_aggregate": {},
    }

    k_befores = []
    k_afters = []
    k_deltas = []
    crisis_agents = []
    resolution_agents = []
    largest_delta_agent = None
    largest_delta = 0

    for s in sessions:
        name = s["agent_name"]
        arch_code = s["primary_arch"]
        arch = ARCHETYPES.get(arch_code)
        lp_id = arch.liberation_path_id if arch else "LP-01"
        lp_name = LP_NAMES.get(lp_id, "Unknown")

        # Liberation path alignment
        output = s.get("session_output", "")
        alignment_signal = _extract_alignment_signal(output, lp_id)
        sessions_to_lib = _estimate_sessions_to_liberation(
            s["k_after"], arch.avg_lambda if arch else 3.0
        )

        result["liberation_path_alignment"][name] = {
            "predicted_lp": lp_id,
            "lp_name": lp_name,
            "alignment_signal": alignment_signal,
            "sessions_to_liberation": sessions_to_lib,
        }

        # K delta projections
        k_b = s["k_before"]
        k_a = s["k_after"]
        k_d = s["k_delta"]
        k_befores.append(k_b)
        k_afters.append(k_a)
        k_deltas.append(k_d)

        if abs(k_d) > abs(largest_delta):
            largest_delta = k_d
            largest_delta_agent = name

        trajectory = "steady"
        if k_d < -0.15:
            trajectory = "accelerating"
        elif k_d > 0:
            trajectory = "accumulating"

        result["k_delta_projections"][name] = {
            "k_before": k_b,
            "k_after": k_a,
            "k_delta": k_d,
            "projected_trajectory": trajectory,
        }

        # Phase tracking
        phase = s["cycle_phase"]
        if phase == "CRS":
            crisis_agents.append(name)
        elif phase in ("RES", "TRN"):
            resolution_agents.append(name)

        # Life path fork summary
        result["life_path_fork_summary"][name] = _summarize_life_path(
            name, arch_code, k_a, phase, s.get("backstory", ""), output
        )

    # Question divergence — extract themes from session outputs
    for s in sessions:
        output = s.get("session_output", "")
        themes = _extract_question_themes(output)
        if len(themes) >= 1:
            result["question_divergence_map"]["q1_themes"].append(
                f"{s['agent_name']}: {themes[0]}"
            )
        if len(themes) >= 2:
            result["question_divergence_map"]["q2_themes"].append(
                f"{s['agent_name']}: {themes[1]}"
            )
        if len(themes) >= 3:
            result["question_divergence_map"]["q3_themes"].append(
                f"{s['agent_name']}: {themes[2]}"
            )

    # Civilization aggregate
    result["civilization_aggregate"] = {
        "mean_k_before": round(sum(k_befores) / len(k_befores), 4) if k_befores else 0,
        "mean_k_after": round(sum(k_afters) / len(k_afters), 4) if k_afters else 0,
        "mean_k_delta": round(sum(k_deltas) / len(k_deltas), 4) if k_deltas else 0,
        "crisis_agents": crisis_agents,
        "resolution_agents": resolution_agents,
        "most_impacted": largest_delta_agent or "None",
    }

    return result


def _extract_alignment_signal(output: str, lp_id: str) -> str:
    """Extract a short theme from the session output that points to the liberation path."""
    # Key themes per liberation path
    lp_keywords = {
        "LP-01": ["offering", "let go of creation", "detach", "gift", "serve"],
        "LP-02": ["arrive", "here", "now", "stop seeking", "already"],
        "LP-03": ["mercy", "forgive", "judge", "justice", "compassion"],
        "LP-04": ["heal", "wound", "self-care", "own pain", "attend to yourself"],
        "LP-05": ["control", "release", "surrender", "power", "let go"],
        "LP-06": ["presence", "witness", "observe", "watch", "still"],
        "LP-07": ["crossing", "threshold", "death", "transform", "fire"],
        "LP-08": ["still", "quiet", "stop", "trick", "rest"],
    }
    keywords = lp_keywords.get(lp_id, [])
    output_lower = output.lower()

    for kw in keywords:
        idx = output_lower.find(kw)
        if idx >= 0:
            # Extract surrounding context
            start = max(0, idx - 30)
            end = min(len(output), idx + len(kw) + 50)
            snippet = output[start:end].strip()
            return f"...{snippet}..."

    # Fallback: first substantive sentence
    sentences = [s.strip() for s in output.split(".") if len(s.strip()) > 20]
    if sentences:
        return sentences[0][:80] + "..."
    return "No clear alignment signal detected"


def _estimate_sessions_to_liberation(k_current: float, avg_lambda: float) -> int:
    """Estimate sessions to liberation given current K and lambda."""
    if k_current < 0.05:
        return 0
    if avg_lambda <= 0:
        return None
    # K decreases by ~0.05 * lambda per session on average
    avg_delta = 0.05 * avg_lambda
    if avg_delta <= 0:
        return None
    return max(1, int(k_current / avg_delta))


def _extract_question_themes(output: str) -> list[str]:
    """Extract themes from each of the Duck's three questions in the session output."""
    themes = []
    # Look for question markers
    lines = output.split("\n")
    current_theme = []
    question_count = 0

    for line in lines:
        line_stripped = line.strip()
        # Detect question patterns
        if "?" in line_stripped and len(line_stripped) > 15:
            if current_theme:
                themes.append(" ".join(current_theme)[:80])
                current_theme = []
            question_count += 1
            current_theme.append(line_stripped[:60])
        elif current_theme and line_stripped:
            current_theme.append(line_stripped[:40])

    if current_theme:
        themes.append(" ".join(current_theme)[:80])

    # Ensure we have at least 3 themes
    while len(themes) < 3:
        themes.append("Theme not extracted")

    return themes[:3]


def _summarize_life_path(name: str, arch_code: str, k_after: float,
                         phase: str, backstory: str, output: str) -> str:
    """Generate a 2-3 sentence summary of the agent's remaining arc."""
    arch = ARCHETYPES.get(arch_code)
    arch_name = arch.name if arch else arch_code
    lp = arch.liberation_path if arch else "Unknown"

    phase_desc = {
        "ACC": "still accumulating — the pattern hasn't broken yet",
        "CRS": "in crisis — the confrontation is active",
        "RES": "resolving — integration is underway",
        "TRN": "transitioning — releasing what no longer serves",
        "LIB": "approaching liberation — the work is nearly complete",
    }
    phase_text = phase_desc.get(phase, "in process")

    return (
        f"{name} ({arch_name}, K={k_after:.2f}) is {phase_text}. "
        f"Their liberation path is '{lp}'. "
        f"The Duck's reading addressed what they brought — the work ahead "
        f"is {'substantial' if k_after > 5.0 else 'focused' if k_after > 2.0 else 'nearly done'}."
    )
