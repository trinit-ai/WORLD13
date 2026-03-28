"""
theatres/marriage/runner.py

Marriage dynamics simulation. Models heterosexual marriage as K(x)/lambda
dynamics with dyadic repair capacity (minimum of two partners' lambda).

Key mechanics:
- Shared K(x) — accumulated resentment belongs to the relationship
- Individual lambda — each partner has their own repair capacity
- Effective lambda = min(partner_a, partner_b) — one disengaged partner
  suppresses repair regardless of the other's effort
- External K fields — parenting, financial stress as ambient pressure
- Timed interventions — therapy with duration, effectiveness decay
- Terminal states: Renewal (K < 0.05, C > 0.95) or Pattern Lock (lambda floor)
"""

import math
import os
import random
import time
import uuid
import yaml

from engine.tvr import coherence, LIBERATION_THRESHOLD, COHERENCE_LIBERATION


# ── CONFIGURATION ──────────────────────────────────────────────────────────

BASE_K_DELTA_RATE = 0.05
PHASE_MULTIPLIERS = {
    "ACC": 1.0, "CRS": 0.5, "RES": 1.4, "TRN": 1.8, "LIB": 2.5,
}

# Terminal conditions
RENEWAL_K = 0.05
RENEWAL_C = 0.95
PATTERN_LOCK_LAMBDA_FLOOR = 2.0
PATTERN_LOCK_CONSECUTIVE = 5

# At risk thresholds
AT_RISK_K = 5.5
AT_RISK_LAMBDA = 3.5

# Lambda asymmetry
ASYMMETRY_CRITICAL = 2.5


def load_manifest():
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    with open(manifest_path) as f:
        return yaml.safe_load(f)


# ── COUPLE STATE ───────────────────────────────────────────────────────────

class Couple:
    """A relationship modeled as a dyadic TVR agent."""

    def __init__(self, config: dict, rng: random.Random):
        self.id = str(uuid.uuid4())[:12]
        self.name = config["name"]
        self.profile_label = config.get("profile_label", "")
        self.profile = config.get("profile", "").strip()
        self.research_question = config.get("research_question", "").strip()

        # Shared relationship state
        self.k_current = float(config["k0"])
        self.k0 = self.k_current
        self.cycle_phase = config["cycle_phase"]

        # Individual partner lambda
        self.lambda_a = float(config.get("lambda_partner_a", config["lambda_coeff"]))
        self.lambda_b = float(config.get("lambda_partner_b", config["lambda_coeff"]))
        self.lambda_asymmetry = abs(self.lambda_a - self.lambda_b)

        self.sessions_completed = 0
        self.rng = rng

        # Terminal state tracking
        self.is_renewed = False
        self.is_pattern_locked = False
        self.renewal_session = None
        self.pattern_lock_session = None
        self.lambda_decline_streak = 0
        self.risk_status = "nominal"

        # Intervention
        self.intervention_config = config.get("intervention", {})
        self.intervention_active = False
        self.intervention_sessions_remaining = 0
        self.interventions_applied = []

        # External K field
        self.external_k_config = config.get("external_k_field", {})
        self.external_k_enabled = self.external_k_config.get("enabled", False)
        self.external_k_per_session = float(self.external_k_config.get("k_contribution_per_session", 0))

        # History
        self.k_history = [self.k_current]
        self.lambda_a_history = [self.lambda_a]
        self.lambda_b_history = [self.lambda_b]
        self.eff_lambda_history = [self.effective_lambda()]
        self.asymmetry_history = [self.lambda_asymmetry]
        self.risk_history = []

    def effective_lambda(self) -> float:
        """Dyadic lambda = minimum of two partners. One disengaged partner kills repair."""
        return min(self.lambda_a, self.lambda_b)

    def current_coherence(self) -> float:
        return coherence(self.effective_lambda(), self.sessions_completed + 1)

    def compute_k_delta(self) -> float:
        """K(x) delta for this session."""
        eff_lambda = self.effective_lambda()
        base_delta = -BASE_K_DELTA_RATE * eff_lambda
        phase_mult = PHASE_MULTIPLIERS.get(self.cycle_phase, 1.0)
        delta = base_delta * phase_mult
        delta += self.rng.gauss(0, 0.03)
        return max(-0.5, min(0.3, round(delta, 4)))

    def update_cycle_phase(self):
        ratio = self.k_current / max(self.k0, 0.01)
        if ratio > 0.80:
            self.cycle_phase = "ACC"
        elif ratio > 0.50:
            self.cycle_phase = "CRS"
        elif ratio > 0.20:
            self.cycle_phase = "RES"
        elif ratio > 0.05:
            self.cycle_phase = "TRN"
        else:
            self.cycle_phase = "LIB"

    def update_risk_status(self, session_num: int):
        if self.is_renewed or self.is_pattern_locked:
            return

        coh = self.current_coherence()
        eff_lam = self.effective_lambda()

        # Check renewal
        if self.k_current < RENEWAL_K and coh > RENEWAL_C:
            self.is_renewed = True
            self.risk_status = "renewed"
            self.renewal_session = session_num
            return

        # Check pattern lock — lambda declining consecutively
        if len(self.eff_lambda_history) >= 2:
            if self.eff_lambda_history[-1] < self.eff_lambda_history[-2]:
                self.lambda_decline_streak += 1
            else:
                self.lambda_decline_streak = max(0, self.lambda_decline_streak - 1)

        if (eff_lam < PATTERN_LOCK_LAMBDA_FLOOR and
                self.lambda_decline_streak >= PATTERN_LOCK_CONSECUTIVE):
            self.is_pattern_locked = True
            self.risk_status = "pattern_lock"
            self.pattern_lock_session = session_num
            return

        # At risk assessment
        if self.k_current > AT_RISK_K and eff_lam < AT_RISK_LAMBDA:
            self.risk_status = "at_risk"
        elif self.cycle_phase in ("CRS", "TRN"):
            self.risk_status = "elevated"
        elif self.cycle_phase in ("RES", "LIB"):
            self.risk_status = "improving"
        else:
            self.risk_status = "nominal"

    def apply_session(self, session_num: int):
        """Run one session for this couple."""
        if self.is_renewed or self.is_pattern_locked:
            return None

        k_delta = self.compute_k_delta()
        k_before = self.k_current

        # Apply external K field
        external_k = 0.0
        if self.external_k_enabled:
            external_k = self.external_k_per_session + self.rng.gauss(0, 0.01)
            external_k = max(0, external_k)

        # Apply intervention effects
        intervention_k_reduction = 0.0
        intervention_lambda_boost = 0.0
        if self.intervention_active and self.intervention_sessions_remaining > 0:
            iv = self.intervention_config
            decay = iv.get("effectiveness_decay", 0.05)
            sessions_in = iv.get("duration_sessions", 10) - self.intervention_sessions_remaining
            effectiveness = max(0.3, 1.0 - decay * sessions_in)

            intervention_k_reduction = iv.get("k_reduction", 0.8) * effectiveness * 0.1
            intervention_lambda_boost = iv.get("lambda_boost", 0.6) * effectiveness * 0.05

            self.intervention_sessions_remaining -= 1
            if self.intervention_sessions_remaining <= 0:
                self.intervention_active = False

        # Update K
        total_k_delta = k_delta + external_k - intervention_k_reduction
        self.k_current = max(0.0, round(self.k_current + total_k_delta, 4))

        # Update individual lambdas
        # Lambda naturally decays under sustained CRS, grows under RES/LIB
        lambda_drift_a = self._lambda_drift(self.lambda_a) + intervention_lambda_boost
        lambda_drift_b = self._lambda_drift(self.lambda_b) + intervention_lambda_boost
        self.lambda_a = max(0.5, min(10.0, round(self.lambda_a + lambda_drift_a, 4)))
        self.lambda_b = max(0.5, min(10.0, round(self.lambda_b + lambda_drift_b, 4)))
        self.lambda_asymmetry = round(abs(self.lambda_a - self.lambda_b), 4)

        self.sessions_completed += 1
        self.update_cycle_phase()

        # Record history
        self.k_history.append(self.k_current)
        self.lambda_a_history.append(self.lambda_a)
        self.lambda_b_history.append(self.lambda_b)
        self.eff_lambda_history.append(self.effective_lambda())
        self.asymmetry_history.append(self.lambda_asymmetry)

        self.update_risk_status(session_num)
        self.risk_history.append(self.risk_status)

        return {
            "session": session_num,
            "couple": self.name,
            "k_before": round(k_before, 4),
            "k_after": self.k_current,
            "k_delta": round(total_k_delta, 4),
            "external_k": round(external_k, 4),
            "intervention_k_reduction": round(intervention_k_reduction, 4),
            "lambda_a": self.lambda_a,
            "lambda_b": self.lambda_b,
            "effective_lambda": self.effective_lambda(),
            "asymmetry": self.lambda_asymmetry,
            "coherence": round(self.current_coherence(), 4),
            "phase": self.cycle_phase,
            "risk": self.risk_status,
        }

    def _lambda_drift(self, lam: float) -> float:
        """Natural lambda drift based on relationship phase."""
        if self.cycle_phase == "CRS":
            return -0.02 + self.rng.gauss(0, 0.01)
        elif self.cycle_phase == "RES":
            return 0.015 + self.rng.gauss(0, 0.008)
        elif self.cycle_phase == "LIB":
            return 0.02 + self.rng.gauss(0, 0.005)
        elif self.cycle_phase == "TRN":
            return -0.01 + self.rng.gauss(0, 0.012)
        else:  # ACC
            return -0.005 + self.rng.gauss(0, 0.008)


# ── MAIN RUNNER ────────────────────────────────────────────────────────────

def run_marriage_theatre(dry_run: bool = False) -> dict:
    """Run the full Marriage Theatre simulation."""
    manifest = load_manifest()
    start_time = time.time()
    run_id = str(uuid.uuid4())[:8]
    rng = random.Random(42)

    sessions_per_agent = manifest["protocol"]["sessions_per_agent"]
    external_fields = manifest.get("external_k_fields", {})

    # Initialize couples
    couples = {}
    pop = manifest.get("population", {})
    agent_list = pop.get("agents", pop) if isinstance(pop, dict) else pop
    if isinstance(agent_list, dict):
        agent_list = [v for v in agent_list.values() if isinstance(v, dict) and "name" in v]
    for config in agent_list:
        if not isinstance(config, dict) or "name" not in config:
            continue
        couple = Couple(config, rng)
        couples[couple.name] = couple

    # Apply external K field multipliers from manifest-level config
    for field_name, field_config in external_fields.items():
        if not isinstance(field_config, dict):
            continue
        for couple_name in field_config.get("affected_couples", []):
            if couple_name in couples:
                c = couples[couple_name]
                if not c.external_k_enabled:
                    c.external_k_enabled = True
                    c.external_k_per_session = float(field_config.get("k_contribution_per_session", 0))
                else:
                    # Stack fields
                    c.external_k_per_session += float(field_config.get("k_contribution_per_session", 0))
                if "multiplier" in field_config:
                    c.external_k_per_session *= float(field_config["multiplier"])

    term = manifest.get("terminology", {})
    phase_labels = term.get("phase_labels", {})

    print(f"\n  Marriage Theatre v{manifest['version']}")
    print(f"  Couples: {len(couples)}")
    print(f"  Sessions per couple: {sessions_per_agent}")
    print(f"  Dyadic lambda: minimum rule")
    print()

    if dry_run:
        for name, c in couples.items():
            phase_label = phase_labels.get(c.cycle_phase, c.cycle_phase)
            print(f"  {name:24s} K:{c.k0:.1f} λA:{c.lambda_a:.1f} λB:{c.lambda_b:.1f} eff:{c.effective_lambda():.1f} {phase_label}")
        print(f"\n  Dry run complete — no sessions executed.")
        return {"dry_run": True, "couples": len(couples)}

    # ── SIMULATION LOOP ────────────────────────────────────────────────
    all_sessions = []

    for session_num in range(1, sessions_per_agent + 1):
        tick_results = []

        for name, couple in couples.items():
            # Check if intervention should fire
            iv = couple.intervention_config
            if (iv.get("enabled") and
                    session_num == iv.get("session", 0) and
                    not couple.intervention_active):
                couple.intervention_active = True
                couple.intervention_sessions_remaining = iv.get("duration_sessions", 10)
                couple.interventions_applied.append({
                    "session": session_num,
                    "type": iv.get("type", "couples_therapy"),
                    "duration": iv.get("duration_sessions", 10),
                })

            result = couple.apply_session(session_num)
            if result:
                tick_results.append(result)
                all_sessions.append(result)

        # Print progress
        _print_tick(session_num, couples, phase_labels)

    duration = round(time.time() - start_time, 1)

    return {
        "theatre": "marriage",
        "run_id": run_id,
        "couples": {name: _couple_summary(c) for name, c in couples.items()},
        "sessions": all_sessions,
        "sessions_per_couple": sessions_per_agent,
        "terminology": term,
        "duration_seconds": duration,
    }


def _couple_summary(c: Couple) -> dict:
    return {
        "name": c.name,
        "profile_label": c.profile_label,
        "profile": c.profile,
        "research_question": c.research_question,
        "k_initial": c.k0,
        "k_final": c.k_current,
        "lambda_a_initial": c.lambda_a_history[0],
        "lambda_a_final": c.lambda_a,
        "lambda_b_initial": c.lambda_b_history[0],
        "lambda_b_final": c.lambda_b,
        "effective_lambda_final": c.effective_lambda(),
        "asymmetry_initial": c.asymmetry_history[0],
        "asymmetry_final": c.lambda_asymmetry,
        "coherence_final": c.current_coherence(),
        "phase_final": c.cycle_phase,
        "risk_status": c.risk_status,
        "is_renewed": c.is_renewed,
        "renewal_session": c.renewal_session,
        "is_pattern_locked": c.is_pattern_locked,
        "pattern_lock_session": c.pattern_lock_session,
        "sessions_completed": c.sessions_completed,
        "interventions": c.interventions_applied,
        "external_k_enabled": c.external_k_enabled,
        "external_k_per_session": c.external_k_per_session,
        "k_history": [round(k, 4) for k in c.k_history],
        "lambda_a_history": [round(l, 4) for l in c.lambda_a_history],
        "lambda_b_history": [round(l, 4) for l in c.lambda_b_history],
        "eff_lambda_history": [round(l, 4) for l in c.eff_lambda_history],
        "asymmetry_history": [round(a, 4) for a in c.asymmetry_history],
        "risk_history": c.risk_history,
    }


def _print_tick(session_num, couples, phase_labels):
    active = sum(1 for c in couples.values() if not c.is_renewed and not c.is_pattern_locked)
    renewed = sum(1 for c in couples.values() if c.is_renewed)
    locked = sum(1 for c in couples.values() if c.is_pattern_locked)
    at_risk = sum(1 for c in couples.values() if c.risk_status in ("at_risk", "elevated"))

    print(f"  === SESSION {session_num:2d} ===  active:{active} risk:{at_risk} renewed:{renewed} locked:{locked}")

    for c in couples.values():
        if c.is_renewed and c.renewal_session == session_num:
            print(f"    * RENEWAL: {c.name} ({c.profile_label}) — K:{c.k_current:.4f} C:{c.current_coherence():.3f}")
        if c.is_pattern_locked and c.pattern_lock_session == session_num:
            print(f"    X PATTERN LOCK: {c.name} ({c.profile_label}) — K:{c.k_current:.2f} eff-lambda:{c.effective_lambda():.2f}")

    for c in couples.values():
        if c.intervention_active and c.interventions_applied:
            iv = c.interventions_applied[-1]
            if iv["session"] == session_num:
                print(f"    + INTERVENTION: {c.name} — {iv['type']} ({iv['duration']} sessions)")
