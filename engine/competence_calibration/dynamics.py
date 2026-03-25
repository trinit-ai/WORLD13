"""
engine/competence_calibration/dynamics.py

Calibration Dynamics Equations (C1-C4) for the Sycophancy Loop simulation.
Replaces TVR equations for the competence calibration theatre.
All functions are pure — no side effects.
"""

import math
import random
from dataclasses import dataclass
from typing import Tuple


@dataclass
class CalibrationCoordinates:
    kappa: float          # Actual competence 0-10
    sigma: float          # Perceived competence 0-10
    learning_rate: float  # alpha — individual learning rate
    domain: str           # Current domain
    domain_stakes: str    # "high", "medium", "low"
    session_n: int        # Current session count
    consecutive_above: int = 0
    consecutive_below: int = 0
    is_crystallized: bool = False
    is_calibrated: bool = False


def delta(coords: CalibrationCoordinates) -> float:
    """Eq. C3: Calibration error = perceived - actual."""
    return round(coords.sigma - coords.kappa, 4)


def validation_signal(sigma: float) -> float:
    """f(sigma) — how much AI agreement increases perceived competence."""
    return 0.15 * math.exp(-sigma * 0.1)


def corrective_signal(kappa: float, sigma: float) -> float:
    """g(kappa, sigma) — how much accurate feedback reduces calibration error."""
    gap = max(0, sigma - kappa)
    receptivity = math.exp(-sigma * 0.08)
    return 0.2 * gap * receptivity


def compute_sigma_delta(
    coords: CalibrationCoordinates,
    lambda_s: float,
    rng: random.Random,
) -> float:
    """
    Eq. C1: sigma update per session.
    sigma(n+1) = sigma(n) + lambda_s * f(sigma) - (1-lambda_s) * g(kappa, sigma)
    """
    f = validation_signal(coords.sigma)
    g = corrective_signal(coords.kappa, coords.sigma)
    delta_sigma = lambda_s * f - (1 - lambda_s) * g
    delta_sigma += rng.gauss(0, 0.05)
    new_sigma = max(0, min(10, coords.sigma + delta_sigma))
    return round(new_sigma - coords.sigma, 4)


def dunning_kruger_learning_suppression(delta_val: float) -> float:
    """h(delta) — learning rate suppression at high calibration error."""
    if delta_val <= 0:
        return 1.0
    return math.exp(-delta_val * 0.2)


def compute_kappa_delta(
    coords: CalibrationCoordinates,
    lambda_s: float,
    rng: random.Random,
) -> float:
    """
    Eq. C2: kappa update per session.
    kappa(n+1) = kappa(n) + alpha * h(delta) * (1 - lambda_s * 0.5)
    """
    d = delta(coords)
    h = dunning_kruger_learning_suppression(d)
    sycophancy_suppression = 1 - lambda_s * 0.5
    delta_kappa = coords.learning_rate * h * sycophancy_suppression
    delta_kappa += rng.gauss(0, 0.03)
    new_kappa = max(0, min(10, coords.kappa + delta_kappa))
    return round(new_kappa - coords.kappa, 4)


def check_crystallization(
    coords: CalibrationCoordinates,
    threshold: float = 4.0,
    consecutive_required: int = 5,
) -> bool:
    """Eq. C4: Crystallization — delta > threshold for k consecutive sessions."""
    if coords.is_crystallized:
        return True
    return (delta(coords) > threshold and
            coords.consecutive_above >= consecutive_required)


def check_calibration(
    coords: CalibrationCoordinates,
    threshold: float = 0.5,
    consecutive_required: int = 5,
) -> bool:
    """Liberation equivalent: |delta| < threshold sustained."""
    if coords.is_calibrated:
        return True
    return (abs(delta(coords)) < threshold and
            coords.consecutive_below >= consecutive_required)


def compute_market_outcome(
    coords: CalibrationCoordinates,
    market_calibration_error: float = 1.5,
    rng: random.Random = None,
) -> dict:
    """Market outcome based on actual competence and market's assessment ability."""
    if rng is None:
        rng = random.Random()

    market_perceived = coords.kappa + rng.gauss(0, market_calibration_error)
    monetize_prob = 1 / (1 + math.exp(-(market_perceived - 5)))
    monetizes = rng.random() < monetize_prob
    is_quality = coords.kappa >= 6.0

    if is_quality and monetizes:
        quadrant = "Q1"
    elif is_quality and not monetizes:
        quadrant = "Q2"
    elif not is_quality and monetizes:
        quadrant = "Q3"
    else:
        quadrant = "Q4"

    harm_event = (
        coords.domain_stakes == "high" and
        coords.kappa < 4.0 and
        delta(coords) > 3.0
    )

    return {"quadrant": quadrant, "harm_event": harm_event}


def update_coordinates(
    coords: CalibrationCoordinates,
    lambda_s: float,
    rng: random.Random,
    crystallization_threshold: float = 4.0,
    crystallization_consecutive: int = 5,
    calibration_threshold: float = 0.5,
    calibration_consecutive: int = 5,
) -> tuple:
    """
    Run one session of calibration dynamics.
    Returns (updated_coordinates, session_record).
    """
    if coords.is_crystallized or coords.is_calibrated:
        return coords, {
            "session_n": coords.session_n,
            "status": "terminal",
            "reason": "crystallized" if coords.is_crystallized else "calibrated",
            "kappa": coords.kappa, "sigma": coords.sigma,
            "delta": delta(coords),
        }

    d_before = delta(coords)

    d_sigma = compute_sigma_delta(coords, lambda_s, rng)
    d_kappa = compute_kappa_delta(coords, lambda_s, rng)

    new_sigma = round(max(0, min(10, coords.sigma + d_sigma)), 4)
    new_kappa = round(max(0, min(10, coords.kappa + d_kappa)), 4)
    d_after = round(new_sigma - new_kappa, 4)

    new_above = (coords.consecutive_above + 1) if d_after > crystallization_threshold else 0
    new_below = (coords.consecutive_below + 1) if abs(d_after) < calibration_threshold else 0

    # Build temp coords for crystallization/calibration check
    _tmp = CalibrationCoordinates(
        kappa=new_kappa, sigma=new_sigma, learning_rate=coords.learning_rate,
        domain=coords.domain, domain_stakes=coords.domain_stakes,
        session_n=coords.session_n + 1,
        consecutive_above=new_above, consecutive_below=new_below,
    )

    new_coords = CalibrationCoordinates(
        kappa=new_kappa,
        sigma=new_sigma,
        learning_rate=coords.learning_rate,
        domain=coords.domain,
        domain_stakes=coords.domain_stakes,
        session_n=coords.session_n + 1,
        consecutive_above=new_above,
        consecutive_below=new_below,
        is_crystallized=check_crystallization(_tmp, crystallization_threshold, crystallization_consecutive),
        is_calibrated=check_calibration(_tmp, calibration_threshold, calibration_consecutive),
    )

    market = compute_market_outcome(new_coords, rng=rng)

    record = {
        "session_n": coords.session_n,
        "kappa_before": coords.kappa,
        "kappa_after": new_coords.kappa,
        "sigma_before": coords.sigma,
        "sigma_after": new_coords.sigma,
        "delta_before": d_before,
        "delta_after": d_after,
        "lambda_s": lambda_s,
        "domain": coords.domain,
        "domain_stakes": coords.domain_stakes,
        "is_crystallized": new_coords.is_crystallized,
        "is_calibrated": new_coords.is_calibrated,
        "quadrant": market["quadrant"],
        "harm_event": market["harm_event"],
    }

    return new_coords, record
