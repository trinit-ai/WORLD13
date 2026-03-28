"""
theatres/marriage/reporter.py

Generates the markdown report for the Marriage Theatre.
All output uses plain language — no archetype codes, no TVR jargon.
"""

import os
import time


def generate_marriage_report(results: dict, analysis: dict, output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    run_id = results.get("run_id", "unknown")
    filepath = os.path.join(output_dir, f"{run_id}.md")

    couples = results["couples"]
    term = results.get("terminology", {})
    phase_labels = term.get("phase_labels", {})

    lines = []
    _w = lines.append

    # ── HEADER ─────────────────────────────────────────────────────────
    _w("# Marriage Theatre — Relationship Dynamics Report")
    _w("")
    _w(f"**Run ID:** {run_id}")
    _w(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}")
    _w(f"**Couples:** {len(couples)}")
    _w(f"**Sessions per couple:** {results['sessions_per_couple']}")
    _w(f"**Duration:** {results['duration_seconds']:.1f}s")
    _w("")
    renewed = sum(1 for c in couples.values() if c["is_renewed"])
    locked = sum(1 for c in couples.values() if c["is_pattern_locked"])
    _w(f"**Terminal states:** {renewed} renewed, {locked} pattern locked, {len(couples) - renewed - locked} active")
    _w("")
    _w("---")
    _w("")

    # ── 1. TRAJECTORY MAP ──────────────────────────────────────────────
    _w("## 1. Trajectory Map")
    _w("")
    _w("| Couple | Profile | Resentment | Repair | Phase | Trajectory | Status |")
    _w("|--------|---------|------------|--------|-------|------------|--------|")
    tmap = analysis.get("trajectory_map", {})
    for name, d in tmap.items():
        status_icon = {"Renewal": "*", "Pattern Lock": "X", "Active": "-"}.get(d["terminal"], "-")
        _w(f"| {name} | {d['profile'][:30]} | {d['k_initial']:.1f} > {couples[name]['k_final']:.2f} | "
           f"{d['effective_lambda_final']:.2f} | {d['phase']} | {d['trajectory']} | {status_icon} {d['terminal']} |")
    _w("")
    _w("---")
    _w("")

    # ── 2. PATTERN LOCK TIMELINE ───────────────────────────────────────
    _w("## 2. Pattern Lock Timeline")
    _w("")
    plt = analysis.get("pattern_lock_timeline", {})
    if plt:
        for name, d in plt.items():
            if d.get("status") == "PATTERN LOCK":
                _w(f"**{name}** — PATTERN LOCK at session {d['session']}. "
                   f"Resentment: {d['k_at_lock']:.2f}, Repair: {d['effective_lambda_at_lock']:.2f}")
            else:
                est = d.get("estimated_sessions_to_lock")
                _w(f"**{name}** — AT RISK. Resentment: {d['k_current']:.2f}, "
                   f"Repair: {d['effective_lambda']:.2f}. "
                   f"{'Est. ~' + str(est) + ' sessions to lock.' if est else 'Timeline uncertain.'}")
            _w("")
    else:
        _w("No couples at pattern lock risk.")
        _w("")
    _w("---")
    _w("")

    # ── 3. INTERVENTION WINDOW MAP ─────────────────────────────────────
    _w("## 3. Intervention Window Map")
    _w("")
    iwm = analysis.get("intervention_window_map", {})
    if iwm:
        for name, d in iwm.items():
            _w(f"### {name} ({d['profile']})")
            if d["interventions_applied"]:
                for iv in d["interventions_applied"]:
                    _w(f"- **Intervention:** {iv['type']} at session {iv['session']} ({iv['duration']} sessions)")
            _w(f"- **Final status:** {d['final_status']}")
            _w(f"- **Resentment:** {d['k_final']:.2f} | **Repair:** {d['effective_lambda_final']:.2f}")
            _w(f"- **Renewed:** {'Yes' if d['is_renewed'] else 'No'} | **Pattern Lock:** {'Yes' if d['is_pattern_locked'] else 'No'}")
            _w("")
    else:
        _w("No interventions tracked.")
        _w("")
    _w("---")
    _w("")

    # ── 4. LAMBDA ASYMMETRY ANALYSIS ───────────────────────────────────
    _w("## 4. Repair Capacity Asymmetry Analysis")
    _w("")
    _w("*The Gottman finding: it takes one partner to stop repairing for the relationship to fail.*")
    _w("")
    _w("| Couple | Asymmetry (start) | Asymmetry (end) | Trend | Finding |")
    _w("|--------|-------------------|-----------------|-------|---------|")
    laa = analysis.get("lambda_asymmetry_analysis", {})
    for name, d in laa.items():
        _w(f"| {name} | {d['asymmetry_initial']:.2f} | {d['asymmetry_final']:.2f} | "
           f"{d['asymmetry_trend']} | {d['finding'][:50]}{'...' if len(d['finding']) > 50 else ''} |")
    _w("")
    _w("---")
    _w("")

    # ── 5. THERAPY THRESHOLD ESTIMATE ──────────────────────────────────
    _w("## 5. Therapy Threshold Estimate")
    _w("")
    _w("*At what accumulated resentment level does professional intervention fail to reverse the trajectory?*")
    _w("")
    tte = analysis.get("therapy_threshold_estimate", {})
    if isinstance(tte, dict) and "finding" in tte:
        _w(tte["finding"])
    else:
        for name, d in tte.items():
            _w(f"### {name}")
            _w(f"- Resentment at therapy start: {d['k_at_therapy_start']:.2f}")
            _w(f"- Resentment final: {d['k_final']:.2f} (reduced by {d['k_reduction']:.2f})")
            _w(f"- Repair capacity at start: {d['effective_lambda_at_start']:.2f} | Final: {d['effective_lambda_final']:.2f}")
            _w(f"- **Outcome:** {d['outcome']}")
            _w("")
    _w("")
    _w("---")
    _w("")

    # ── 6. GOTTMAN HYPOTHESIS TEST ─────────────────────────────────────
    _w("## 6. Gottman Hypothesis Test")
    _w("")
    _w("*Does high conflict + high repair outperform low conflict + low repair?*")
    _w("")
    ght = analysis.get("gottman_hypothesis_test", {})
    if "fighters" in ght:
        f = ght["fighters"]
        p = ght["polite_marriage"]
        _w(f"**The Fighters:** Resentment {f['k_initial']:.1f} > {f['k_final']:.2f}, "
           f"Repair: {f['effective_lambda_final']:.2f}, Outcome: {f['terminal']} (session {f['terminal_session']})")
        _w("")
        _w(f"**The Polite Marriage:** Resentment {p['k_initial']:.1f} > {p['k_final']:.2f}, "
           f"Repair: {p['effective_lambda_final']:.2f}, Outcome: {p['terminal']} (session {p['terminal_session']})")
        _w("")
        _w(f"**{ght['finding']}**")
    else:
        _w(ght.get("finding", ""))
    _w("")
    _w("---")
    _w("")

    # ── 7. EXTERNAL FIELD EFFECTS ──────────────────────────────────────
    _w("## 7. External Stress Effects")
    _w("")
    efe = analysis.get("external_field_effects", {})
    if efe:
        for name, d in efe.items():
            _w(f"### {name} ({d['profile']})")
            _w(f"- External pressure: +{d['external_k_per_session']:.2f} resentment/session")
            _w(f"- Resentment: {d['k_initial']:.1f} > {d['k_final']:.2f}")
            _w(f"- Outcome: {d['terminal']}")
            _w(f"- {d['finding']}")
            _w("")
    else:
        _w("No external stress fields in this run.")
        _w("")
    _w("---")
    _w("")

    # ── 8. REBUILDER CEILING TEST ──────────────────────────────────────
    _w("## 8. Rebuilder Ceiling Test")
    _w("")
    _w("*Can you reach Renewal from K:8.6 with genuine bilateral commitment?*")
    _w("")
    rct = analysis.get("rebuilder_ceiling_test", {})
    _w(rct.get("finding", "No data."))
    if "k_reduction" in rct:
        _w("")
        _w(f"- Resentment reduced by: {rct['k_reduction']:.2f}")
        _w(f"- Final repair capacity: {rct['effective_lambda_final']:.2f}")
        _w(f"- Sessions completed: {rct['sessions_completed']}")
    _w("")
    _w("---")
    _w("")

    # ── COUPLE PROFILES ────────────────────────────────────────────────
    _w("## Couple Profiles")
    _w("")
    for name, c in couples.items():
        phase = phase_labels.get(c["phase_final"], c["phase_final"])
        status_icon = {"renewed": "*", "pattern_lock": "X", "at_risk": "!", "elevated": "~"}.get(c["risk_status"], "-")
        _w(f"### {status_icon} {name} — {c['profile_label']}")
        _w(f"**Resentment:** {c['k_initial']:.1f} > {c['k_final']:.2f} | "
           f"**Repair A:** {c['lambda_a_initial']:.1f} > {c['lambda_a_final']:.2f} | "
           f"**Repair B:** {c['lambda_b_initial']:.1f} > {c['lambda_b_final']:.2f} | "
           f"**Phase:** {phase} | **Status:** {c['risk_status']}")
        if c["interventions"]:
            for iv in c["interventions"]:
                _w(f"**Intervention:** {iv['type']} at session {iv['session']} ({iv['duration']} sessions)")
        _w("")
        _w(f"> {c['profile']}")
        _w("")
        _w(f"*Research question: {c['research_question']}*")
        _w("")

    _w("---")
    _w("*Generated by WORLD13 Marriage Theatre*")
    _w('*"It takes one partner to stop repairing for the relationship to fail."*')

    content = "\n".join(lines)
    with open(filepath, "w") as f:
        f.write(content)

    return filepath
