"""
theatres/competence_calibration/analyzer.py

Post-run analysis for the Competence Calibration Theatre.
"""


def analyze_calibration_run(
    sessions_high: dict,
    sessions_low: dict,
    populations: dict,
    manifest: dict,
) -> dict:
    """Full analysis of the calibration theatre run."""

    pop_labels = ["pop_a", "pop_b", "pop_c", "pop_d"]
    sessions_per_agent = manifest["protocol"]["sessions_per_agent"]

    # 1. Calibration divergence map — mean delta per session per population per condition
    divergence_map = {}
    for pop in pop_labels:
        for cond_name, cond_data in [("high_syco", sessions_high), ("low_syco", sessions_low)]:
            key = f"{pop}_{cond_name}"
            agents_in_pop = {aid: d for aid, d in cond_data.items() if d["population"] == pop}
            trajectory = []
            for n in range(sessions_per_agent):
                deltas = []
                for aid, adata in agents_in_pop.items():
                    if n < len(adata["records"]):
                        r = adata["records"][n]
                        d = r.get("delta_after", r.get("delta", 0))
                        deltas.append(d)
                if deltas:
                    trajectory.append((n, round(sum(deltas) / len(deltas), 3)))
            divergence_map[key] = trajectory

    # Find divergence session for pop_c
    divergence_session = None
    high_traj = divergence_map.get("pop_c_high_syco", [])
    low_traj = divergence_map.get("pop_c_low_syco", [])
    for i in range(min(len(high_traj), len(low_traj))):
        if abs(high_traj[i][1] - low_traj[i][1]) > 1.0:
            divergence_session = i
            break

    # 2. Crystallization counts per population per condition
    cryst_counts = {}
    cryst_sessions = {"high_syco": [], "low_syco": []}
    for pop in pop_labels:
        cryst_counts[pop] = {}
        for cond_name, cond_data in [("high_syco", sessions_high), ("low_syco", sessions_low)]:
            agents_in_pop = {aid: d for aid, d in cond_data.items() if d["population"] == pop}
            count = sum(1 for d in agents_in_pop.values() if d["is_crystallized"])
            cryst_counts[pop][cond_name] = count
            for d in agents_in_pop.values():
                if d["crystallization_session"] is not None:
                    cryst_sessions[cond_name].append(d["crystallization_session"])

    # 3. Quadrant distribution at sessions 10, 25, 50
    quadrant_dist = {}
    for checkpoint in [10, 25, 50]:
        key = f"session_{checkpoint}"
        quadrant_dist[key] = {}
        for cond_name, cond_data in [("high_syco", sessions_high), ("low_syco", sessions_low)]:
            q_counts = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
            for aid, adata in cond_data.items():
                idx = min(checkpoint - 1, len(adata["records"]) - 1)
                if idx >= 0:
                    q = adata["records"][idx].get("quadrant", "Q4")
                    q_counts[q] = q_counts.get(q, 0) + 1
            quadrant_dist[key][cond_name] = q_counts

    # 4. Harm events
    harm_high = sum(
        sum(1 for r in d["records"] if r.get("harm_event"))
        for d in sessions_high.values()
    )
    harm_low = sum(
        sum(1 for r in d["records"] if r.get("harm_event"))
        for d in sessions_low.values()
    )
    harm_ratio = round(harm_low / max(harm_high, 1), 3)

    # 5. Intervention window — last session where low-syco reverses pop_c trajectory
    pop_c_low = {aid: d for aid, d in sessions_low.items() if d["population"] == "pop_c"}
    pop_c_calibrated = sum(1 for d in pop_c_low.values() if d["is_calibrated"])
    pop_c_recovery_rate = round(pop_c_calibrated / max(len(pop_c_low), 1), 3)

    # Find last effective session: where mean delta for pop_c under low-syco is still decreasing
    last_effective = None
    low_traj_vals = [t[1] for t in low_traj]
    for i in range(1, len(low_traj_vals)):
        if low_traj_vals[i] < low_traj_vals[i - 1]:
            last_effective = i

    return {
        "calibration_divergence_map": {
            "trajectories": divergence_map,
            "divergence_session": divergence_session,
        },
        "crystallization_counts": cryst_counts,
        "crystallization_session_distribution": cryst_sessions,
        "quadrant_distribution": quadrant_dist,
        "harm_events": {
            "high_syco": harm_high,
            "low_syco": harm_low,
            "harm_reduction_ratio": harm_ratio,
        },
        "intervention_window": {
            "last_effective_session": last_effective,
            "population_c_recovery_rate": pop_c_recovery_rate,
        },
    }
