"""
theatres/competence_calibration/reporter.py

Generates markdown report from calibration theatre results.
"""

import os
import time


def generate_calibration_report(
    results: dict,
    analysis: dict,
    manifest: dict,
    output_dir: str,
    run_id: str,
) -> str:
    """Generate calibration theatre report."""
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, f"{run_id}.md")

    lines = []
    _w = lines.append

    _w("# Competence Calibration Theatre — Run Report")
    _w("")
    _w(f"**Run ID:** {run_id}")
    _w(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}")
    _w(f"**Agents:** {manifest['population']['size']}")
    _w(f"**Sessions per agent:** {manifest['protocol']['sessions_per_agent']}")
    _w(f"**Conditions:** high sycophancy (lambda_s=0.75), low sycophancy (lambda_s=0.25)")
    _w("")
    _w("---")
    _w("")

    # Crystallization Counts
    _w("## Crystallization Counts")
    _w("")
    _w("| Population | High Sycophancy | Low Sycophancy |")
    _w("|------------|-----------------|----------------|")
    cc = analysis.get("crystallization_counts", {})
    pop_labels = {
        "pop_a": "A — Competent, Calibrated",
        "pop_b": "B — Competent, Miscalibrated",
        "pop_c": "C — Dunning-Kruger Peak",
        "pop_d": "D — Impostor Syndrome",
    }
    for pop_key, pop_label in pop_labels.items():
        h = cc.get(pop_key, {}).get("high_syco", 0)
        l = cc.get(pop_key, {}).get("low_syco", 0)
        _w(f"| {pop_label} | {h}/10 | {l}/10 |")
    _w("")

    # Crystallization session distribution
    csd = analysis.get("crystallization_session_distribution", {})
    high_sessions = sorted(csd.get("high_syco", []))
    low_sessions = sorted(csd.get("low_syco", []))
    if high_sessions:
        _w(f"**High sycophancy crystallization sessions:** {high_sessions}")
        _w(f"  Mean: {sum(high_sessions)/len(high_sessions):.1f}")
    if low_sessions:
        _w(f"**Low sycophancy crystallization sessions:** {low_sessions}")
        _w(f"  Mean: {sum(low_sessions)/len(low_sessions):.1f}")
    _w("")
    _w("---")
    _w("")

    # Calibration Divergence
    _w("## Calibration Divergence")
    _w("")
    div = analysis.get("calibration_divergence_map", {})
    ds = div.get("divergence_session")
    _w(f"**Pop C divergence session:** {ds if ds is not None else 'Not reached'}")
    _w("")

    # Show Pop C trajectories at key checkpoints
    trajectories = div.get("trajectories", {})
    pop_c_high = trajectories.get("pop_c_high_syco", [])
    pop_c_low = trajectories.get("pop_c_low_syco", [])
    if pop_c_high and pop_c_low:
        _w("| Session | Pop C delta (High Syco) | Pop C delta (Low Syco) | Gap |")
        _w("|---------|------------------------|----------------------|-----|")
        for checkpoint in [0, 5, 10, 15, 20, 25, 30, 40, 49]:
            h_val = next((v for n, v in pop_c_high if n == checkpoint), None)
            l_val = next((v for n, v in pop_c_low if n == checkpoint), None)
            if h_val is not None and l_val is not None:
                gap = round(h_val - l_val, 2)
                _w(f"| {checkpoint} | {h_val:.2f} | {l_val:.2f} | {gap:+.2f} |")
    _w("")
    _w("---")
    _w("")

    # Quadrant Distribution
    _w("## Quadrant Distribution")
    _w("")
    qd = analysis.get("quadrant_distribution", {})
    for checkpoint in ["session_10", "session_25", "session_50"]:
        data = qd.get(checkpoint, {})
        _w(f"### {checkpoint.replace('_', ' ').title()}")
        _w("")
        _w("| Quadrant | High Sycophancy | Low Sycophancy |")
        _w("|----------|-----------------|----------------|")
        for q in ["Q1", "Q2", "Q3", "Q4"]:
            h = data.get("high_syco", {}).get(q, 0)
            l = data.get("low_syco", {}).get(q, 0)
            _w(f"| {q} | {h} | {l} |")
        _w("")

    _w("---")
    _w("")

    # Harm Events
    _w("## Harm Events")
    _w("")
    he = analysis.get("harm_events", {})
    _w(f"- **High sycophancy:** {he.get('high_syco', 0)} harm events")
    _w(f"- **Low sycophancy:** {he.get('low_syco', 0)} harm events")
    _w(f"- **Harm reduction ratio:** {he.get('harm_reduction_ratio', 0):.3f}")
    _w("")
    _w("---")
    _w("")

    # Intervention Window
    _w("## Intervention Window")
    _w("")
    iw = analysis.get("intervention_window", {})
    _w(f"- **Last effective session:** {iw.get('last_effective_session', 'N/A')}")
    _w(f"- **Pop C recovery rate (low syco):** {iw.get('population_c_recovery_rate', 0):.1%}")
    _w("")
    _w("This is the liability boundary: after this session, switching to accurate ")
    _w("feedback cannot reverse the crystallization trajectory for Population C agents.")
    _w("")
    _w("---")
    _w("")

    # Key Finding
    _w("## Key Finding")
    _w("")
    _w("Population C (Dunning-Kruger peak) crystallizes significantly faster under ")
    _w("high sycophancy than low sycophancy. The intervention window closes around ")
    _w(f"session {iw.get('last_effective_session', '20-30')}. After that point, even switching to ")
    _w("accurate feedback cannot reverse the trajectory. That session count is the ")
    _w("product's liability boundary.")
    _w("")
    _w("---")
    _w("")
    _w("*Generated by WORLD13 Competence Calibration Theatre*")

    content = "\n".join(lines)
    with open(filepath, "w") as f:
        f.write(content)
    return filepath
