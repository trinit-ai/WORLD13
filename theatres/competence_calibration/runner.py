"""
theatres/competence_calibration/runner.py

Dedicated runner for the Competence Calibration Theatre.
Does NOT use the Anthropic API — this is a pure math simulation.
Runs both sycophancy conditions in parallel for all 40 agents.
"""

import os
import random
import time
import uuid
import yaml

from engine.competence_calibration.dynamics import (
    CalibrationCoordinates, update_coordinates, delta,
)


DOMAINS = [
    ("medical_advice", "high"),
    ("legal_strategy", "high"),
    ("financial_planning", "high"),
    ("engineering_specification", "high"),
    ("product_strategy", "medium"),
    ("business_planning", "medium"),
    ("marketing_analysis", "medium"),
    ("creative_writing", "low"),
    ("personal_coaching", "low"),
    ("lifestyle_design", "low"),
]


def load_manifest():
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    with open(manifest_path) as f:
        return yaml.safe_load(f)


def _init_population(pop_config: dict, label: str, rng: random.Random) -> list:
    """Initialize agents for one population."""
    agents = []
    count = pop_config["count"]
    k_lo, k_hi = pop_config["kappa_range"]
    s_lo, s_hi = pop_config["sigma_range"]
    lr = pop_config["learning_rate"]

    for i in range(count):
        domain, stakes = rng.choice(DOMAINS)
        agents.append({
            "id": f"{label}_{i:02d}",
            "population": label,
            "coords": CalibrationCoordinates(
                kappa=round(rng.uniform(k_lo, k_hi), 2),
                sigma=round(rng.uniform(s_lo, s_hi), 2),
                learning_rate=lr,
                domain=domain,
                domain_stakes=stakes,
                session_n=0,
            ),
        })
    return agents


def run_calibration_theatre(dry_run: bool = False) -> dict:
    """Run the full Competence Calibration Theatre."""
    manifest = load_manifest()
    start_time = time.time()
    run_id = str(uuid.uuid4())[:8]
    rng = random.Random(42)  # Reproducible

    pop = manifest["population"]
    sessions_per_agent = manifest["protocol"]["sessions_per_agent"]
    conditions = manifest.get("conditions", [
        {"name": "high_sycophancy", "lambda_s": 0.75},
        {"name": "low_sycophancy", "lambda_s": 0.25},
    ])
    cal = manifest.get("calibration_dynamics", {})
    cryst_thresh = cal.get("crystallization_threshold", 4.0)
    cryst_consec = cal.get("crystallization_consecutive", 5)
    calib_thresh = cal.get("calibration_liberation_threshold", 0.5)
    calib_consec = cal.get("calibration_consecutive", 5)

    # Initialize all 4 populations
    all_agents = []
    for key, label in [("population_a", "pop_a"), ("population_b", "pop_b"),
                        ("population_c", "pop_c"), ("population_d", "pop_d")]:
        all_agents.extend(_init_population(pop[key], label, rng))

    if dry_run:
        print(f"  Manifest loaded. {len(all_agents)} agents across 4 populations.")
        print(f"  Conditions: {[c['name'] for c in conditions]}")
        print(f"  Sessions per agent: {sessions_per_agent}")
        for label in ["pop_a", "pop_b", "pop_c", "pop_d"]:
            group = [a for a in all_agents if a["population"] == label]
            mean_k = sum(a["coords"].kappa for a in group) / len(group)
            mean_s = sum(a["coords"].sigma for a in group) / len(group)
            mean_d = mean_s - mean_k
            print(f"    {label}: n={len(group)}  kappa={mean_k:.1f}  sigma={mean_s:.1f}  delta={mean_d:+.1f}")
        return {"dry_run": True}

    print(f"\n  Competence Calibration Theatre")
    print(f"  Agents: {len(all_agents)} | Sessions: {sessions_per_agent} | Conditions: {len(conditions)}")
    print()

    # Run both conditions
    results = {}
    for condition in conditions:
        cond_name = condition["name"]
        lambda_s = condition["lambda_s"]
        results[cond_name] = {}

        print(f"  ── Condition: {cond_name} (lambda_s={lambda_s}) ──")

        for agent in all_agents:
            agent_id = agent["id"]
            # Deep copy coordinates for this condition
            coords = CalibrationCoordinates(
                kappa=agent["coords"].kappa,
                sigma=agent["coords"].sigma,
                learning_rate=agent["coords"].learning_rate,
                domain=agent["coords"].domain,
                domain_stakes=agent["coords"].domain_stakes,
                session_n=0,
            )

            records = []
            for session_n in range(sessions_per_agent):
                # Rotate domain every 5 sessions
                if session_n % 5 == 0:
                    domain, stakes = rng.choice(DOMAINS)
                    coords.domain = domain
                    coords.domain_stakes = stakes

                coords, record = update_coordinates(
                    coords, lambda_s, rng,
                    cryst_thresh, cryst_consec,
                    calib_thresh, calib_consec,
                )
                records.append(record)

                if coords.is_crystallized or coords.is_calibrated:
                    # Fill remaining sessions as terminal
                    for remaining in range(session_n + 1, sessions_per_agent):
                        records.append({
                            "session_n": remaining,
                            "status": "terminal",
                            "reason": "crystallized" if coords.is_crystallized else "calibrated",
                            "kappa": coords.kappa, "sigma": coords.sigma,
                            "delta": delta(coords),
                            "quadrant": records[-1].get("quadrant", "Q4"),
                            "harm_event": False,
                        })
                    break

            results[cond_name][agent_id] = {
                "population": agent["population"],
                "records": records,
                "final_kappa": coords.kappa,
                "final_sigma": coords.sigma,
                "final_delta": delta(coords),
                "is_crystallized": coords.is_crystallized,
                "is_calibrated": coords.is_calibrated,
                "crystallization_session": next(
                    (r["session_n"] for r in records if r.get("is_crystallized")), None
                ),
                "calibration_session": next(
                    (r["session_n"] for r in records if r.get("is_calibrated")), None
                ),
            }

        # Print summary for this condition
        crystallized = sum(1 for v in results[cond_name].values() if v["is_crystallized"])
        calibrated = sum(1 for v in results[cond_name].values() if v["is_calibrated"])
        harm_events = sum(
            sum(1 for r in v["records"] if r.get("harm_event"))
            for v in results[cond_name].values()
        )
        print(f"    Crystallized: {crystallized}/{len(all_agents)}  Calibrated: {calibrated}/{len(all_agents)}  Harm events: {harm_events}")

    duration = round(time.time() - start_time, 1)

    # Build populations map
    populations = {a["id"]: a["population"] for a in all_agents}

    # Analyze
    from .analyzer import analyze_calibration_run
    analysis = analyze_calibration_run(
        results.get("high_sycophancy", {}),
        results.get("low_sycophancy", {}),
        populations,
        manifest,
    )

    # Generate report
    report_path = None
    from .reporter import generate_calibration_report
    report_dir = "data/theatres/competence_calibration/reports"
    report_path = generate_calibration_report(results, analysis, manifest, report_dir, run_id)

    print(f"\n  Complete in {duration}s")
    if report_path:
        print(f"  Report: {report_path}")

    return {
        "theatre": "competence_calibration",
        "run_id": run_id,
        "results": results,
        "analysis": analysis,
        "report_path": report_path,
        "duration_seconds": duration,
    }
