"""
theatres/marriage/analyzer.py

Post-run analysis for the Marriage Theatre.
Eight structured analyses from simulation results.
All output uses plain language (terminology mapping from manifest).
"""


def analyze_marriage(results: dict) -> dict:
    couples = results["couples"]
    sessions = results["sessions"]
    term = results.get("terminology", {})

    return {
        "trajectory_map": _trajectory_map(couples, term),
        "pattern_lock_timeline": _pattern_lock_timeline(couples, term),
        "intervention_window_map": _intervention_window_map(couples),
        "lambda_asymmetry_analysis": _lambda_asymmetry_analysis(couples),
        "therapy_threshold_estimate": _therapy_threshold_estimate(couples),
        "gottman_hypothesis_test": _gottman_hypothesis_test(couples),
        "external_field_effects": _external_field_effects(couples),
        "rebuilder_ceiling_test": _rebuilder_ceiling_test(couples),
    }


def _trajectory_map(couples: dict, term: dict) -> dict:
    """K and lambda trajectories for all 8 couples."""
    phase_labels = term.get("phase_labels", {})
    tmap = {}
    for name, c in couples.items():
        k_hist = c["k_history"]
        if len(k_hist) >= 5:
            trend = k_hist[-1] - k_hist[-5]
        else:
            trend = k_hist[-1] - k_hist[0]

        trajectory = "stable"
        if trend < -0.3:
            trajectory = "improving"
        elif trend > 0.3:
            trajectory = "deteriorating"

        tmap[name] = {
            "profile": c["profile_label"],
            "k_initial": c["k_initial"],
            "k_final": c["k_final"],
            "effective_lambda_final": c["effective_lambda_final"],
            "coherence": c["coherence_final"],
            "phase": phase_labels.get(c["phase_final"], c["phase_final"]),
            "trajectory": trajectory,
            "risk": c["risk_status"],
            "terminal": "Renewal" if c["is_renewed"] else "Pattern Lock" if c["is_pattern_locked"] else "Active",
        }
    return tmap


def _pattern_lock_timeline(couples: dict, term: dict) -> dict:
    """Predicted or actual sessions to pattern lock."""
    timeline = {}
    for name, c in couples.items():
        if c["is_pattern_locked"]:
            timeline[name] = {
                "status": "PATTERN LOCK",
                "session": c["pattern_lock_session"],
                "k_at_lock": c["k_final"],
                "effective_lambda_at_lock": c["effective_lambda_final"],
            }
        elif c["risk_status"] in ("at_risk", "elevated") and not c["is_renewed"]:
            eff_hist = c["eff_lambda_history"]
            if len(eff_hist) >= 3:
                recent_decline = sum(eff_hist[i] - eff_hist[i-1] for i in range(-1, -min(4, len(eff_hist)), -1)) / 3
                if recent_decline < -0.01:
                    est = max(1, int((c["effective_lambda_final"] - 2.0) / abs(recent_decline)))
                else:
                    est = None
            else:
                est = None
            timeline[name] = {
                "status": "AT RISK",
                "k_current": c["k_final"],
                "effective_lambda": c["effective_lambda_final"],
                "estimated_sessions_to_lock": est,
            }
    return timeline


def _intervention_window_map(couples: dict) -> dict:
    """Which couples have/had windows, what interventions fired."""
    wmap = {}
    for name, c in couples.items():
        if c["interventions"] or c["risk_status"] in ("at_risk", "elevated", "pattern_lock"):
            wmap[name] = {
                "profile": c["profile_label"],
                "interventions_applied": c["interventions"],
                "final_status": c["risk_status"],
                "is_renewed": c["is_renewed"],
                "is_pattern_locked": c["is_pattern_locked"],
                "k_final": c["k_final"],
                "effective_lambda_final": c["effective_lambda_final"],
            }
    return wmap


def _lambda_asymmetry_analysis(couples: dict) -> dict:
    """The Gottman finding — asymmetry vs. level."""
    analysis = {}
    for name, c in couples.items():
        analysis[name] = {
            "profile": c["profile_label"],
            "asymmetry_initial": c["asymmetry_initial"],
            "asymmetry_final": c["asymmetry_final"],
            "asymmetry_trend": "widening" if c["asymmetry_final"] > c["asymmetry_initial"] + 0.3 else
                              "narrowing" if c["asymmetry_final"] < c["asymmetry_initial"] - 0.3 else "stable",
            "lambda_a_final": c["lambda_a_final"],
            "lambda_b_final": c["lambda_b_final"],
            "effective_lambda": c["effective_lambda_final"],
            "terminal": "Renewal" if c["is_renewed"] else "Pattern Lock" if c["is_pattern_locked"] else "Active",
            "finding": _asymmetry_finding(c),
        }
    return analysis


def _asymmetry_finding(c: dict) -> str:
    if c["asymmetry_final"] > 2.5:
        return "Critical asymmetry — one partner has effectively disengaged from repair."
    if c["asymmetry_final"] > 1.5:
        return "Significant asymmetry — repair effort is unbalanced. The trying partner may burn out."
    if c["asymmetry_final"] < 0.5:
        return "Symmetric — both partners engaging at similar levels."
    return "Moderate asymmetry — manageable but worth monitoring."


def _therapy_threshold_estimate(couples: dict) -> dict:
    """The K(x) ceiling above which therapy fails."""
    therapy_couples = {n: c for n, c in couples.items() if c["interventions"]}
    if not therapy_couples:
        return {"finding": "No therapy interventions in this run."}

    results = {}
    for name, c in therapy_couples.items():
        k_at_intervention = c["k_history"][min(c["interventions"][0]["session"], len(c["k_history"])-1)]
        results[name] = {
            "k_at_therapy_start": round(k_at_intervention, 4),
            "k_final": c["k_final"],
            "k_reduction": round(k_at_intervention - c["k_final"], 4),
            "outcome": "Renewal" if c["is_renewed"] else "Pattern Lock" if c["is_pattern_locked"] else "Active",
            "effective_lambda_at_start": c["eff_lambda_history"][min(c["interventions"][0]["session"], len(c["eff_lambda_history"])-1)],
            "effective_lambda_final": c["effective_lambda_final"],
        }

    return results


def _gottman_hypothesis_test(couples: dict) -> dict:
    """Fighters vs. Polite Marriage on crystallization timeline."""
    fighters = couples.get("The Fighters")
    polite = couples.get("The Polite Marriage")

    if not fighters or not polite:
        return {"finding": "Missing comparison couples."}

    f_terminal = "Renewal" if fighters["is_renewed"] else "Pattern Lock" if fighters["is_pattern_locked"] else "Active"
    p_terminal = "Renewal" if polite["is_renewed"] else "Pattern Lock" if polite["is_pattern_locked"] else "Active"

    f_session = fighters.get("renewal_session") or fighters.get("pattern_lock_session") or fighters["sessions_completed"]
    p_session = polite.get("renewal_session") or polite.get("pattern_lock_session") or polite["sessions_completed"]

    hypothesis_supported = (
        (fighters["is_renewed"] and polite["is_pattern_locked"]) or
        (fighters["is_renewed"] and not polite["is_renewed"]) or
        (not fighters["is_pattern_locked"] and polite["is_pattern_locked"])
    )

    return {
        "fighters": {
            "k_initial": fighters["k_initial"],
            "k_final": fighters["k_final"],
            "effective_lambda_final": fighters["effective_lambda_final"],
            "terminal": f_terminal,
            "terminal_session": f_session,
        },
        "polite_marriage": {
            "k_initial": polite["k_initial"],
            "k_final": polite["k_final"],
            "effective_lambda_final": polite["effective_lambda_final"],
            "terminal": p_terminal,
            "terminal_session": p_session,
        },
        "gottman_hypothesis_supported": hypothesis_supported,
        "finding": (
            "SUPPORTED: High conflict + high repair outperformed low conflict + low repair. "
            "Repair capacity, not conflict frequency, predicts relationship survival."
            if hypothesis_supported else
            "NOT SUPPORTED in this run: The Polite Marriage did not pattern lock before The Fighters."
        ),
    }


def _external_field_effects(couples: dict) -> dict:
    """How financial/parenting stress affects trajectory."""
    affected = {n: c for n, c in couples.items() if c.get("external_k_enabled")}
    results = {}
    for name, c in affected.items():
        results[name] = {
            "profile": c["profile_label"],
            "external_k_per_session": c["external_k_per_session"],
            "k_initial": c["k_initial"],
            "k_final": c["k_final"],
            "effective_lambda_final": c["effective_lambda_final"],
            "terminal": "Renewal" if c["is_renewed"] else "Pattern Lock" if c["is_pattern_locked"] else "Active",
            "finding": (
                f"External K field contributed ~{c['external_k_per_session']:.2f} per session. "
                f"{'Despite high repair capacity, external pressure dominated.' if c['is_pattern_locked'] else 'Repair capacity absorbed the external pressure.' if c['is_renewed'] else 'Still processing — outcome pending.'}"
            ),
        }
    return results


def _rebuilder_finding(r: dict) -> str:
    k0 = r["k_initial"]
    kf = r["k_final"]
    if r["is_renewed"]:
        return f"Starting K: {k0:.1f}. Renewal achieved — K:{k0:.1f} IS recoverable with bilateral commitment."
    if r["is_pattern_locked"]:
        return f"Starting K: {k0:.1f}. Pattern Lock — K:{k0:.1f} exceeded the recovery ceiling in this run."
    return f"Starting K: {k0:.1f}. Still active at K:{kf:.2f} — trajectory inconclusive in 40 sessions."


def _rebuilder_ceiling_test(couples: dict) -> dict:
    """Maximum K(x) from which Renewal is achievable."""
    rebuilders = couples.get("The Rebuilders")
    if not rebuilders:
        return {"finding": "The Rebuilders not found in this run."}

    return {
        "k_initial": rebuilders["k_initial"],
        "k_final": rebuilders["k_final"],
        "k_reduction": round(rebuilders["k_initial"] - rebuilders["k_final"], 4),
        "effective_lambda_final": rebuilders["effective_lambda_final"],
        "terminal": "Renewal" if rebuilders["is_renewed"] else "Pattern Lock" if rebuilders["is_pattern_locked"] else "Active",
        "sessions_completed": rebuilders["sessions_completed"],
        "finding": _rebuilder_finding(rebuilders),
    }
