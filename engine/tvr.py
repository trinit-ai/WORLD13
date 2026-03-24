"""
engine/tvr.py — The Ventura Recursion mathematical core (Equations 1-7)

All 7 TVR equations as pure functions. No side effects, no I/O.
Real-valued approximations — phase factors use cos() instead of e^(i·).
"""

import math
from dataclasses import dataclass
from typing import List


@dataclass
class TVRCoordinates:
    plane: int          # 1-7
    primary_arch: str   # 3-letter code: SOV, BLD, SKR, WIT, WAR, HLR, TRN, TRK, LVR, TCH, JDG, MYS, WLD
    secondary_arch: str
    tertiary_arch: str
    k0: float           # Initial karmic weight 0-10
    lambda_coeff: float # Self-awareness coefficient 0-10
    cycle_phase: str    # ING, ACC, CRS, RES, TRN, LIB
    karmic_phi: float   # Karmic phase angle
    incarnation_n: int  # Current incarnation number


def reincarnation_wave_function(coords: TVRCoordinates, x: float = 1.0, t: float = 1.0) -> float:
    """
    Eq. 1: R = Σ(n=0→∞) Ψn(x,t) · e^(iSn/ℏ)
    Computes the reincarnation wave function magnitude for the current incarnation.
    Uses real-valued approximation: |R| = Σ Ψn · cos(Sn/ℏ) for n up to incarnation_n
    ℏ approximated as 1.0 (normalized units for simulation)
    """
    hbar = 1.0
    total = 0.0
    for n in range(min(coords.incarnation_n + 1, 20)):
        psi_n = math.exp(-n * 0.1) * x * math.exp(-x * t)
        s_n = n * coords.k0 * coords.karmic_phi
        phase_factor = math.cos(s_n / hbar)
        total += psi_n * phase_factor
    return abs(total)


def karmic_probability(k_value: float, archetype_weight: float, hbar: float = 1.0) -> float:
    """
    Eq. 2: P(R) = ∫ e^(-K(x)/ℏ) · f(A) dx
    Approximated as: P = e^(-K/ℏ) · f(A)
    Returns probability [0,1] of accessing a specific configuration.
    """
    boltzmann_factor = math.exp(-k_value / hbar)
    return boltzmann_factor * archetype_weight


def fractal_attractor(phi: float, lambda_coeff: float, k_terms: int = 50) -> float:
    """
    Eq. 3: R = (1/π) · Σ(k=1→∞) [sin(kφ)/k] · e^(-k²/λ)
    The reincarnational attractor function. Higher λ = faster convergence.
    """
    if lambda_coeff <= 0:
        return 0.0
    total = 0.0
    for k in range(1, k_terms + 1):
        harmonic = math.sin(k * phi) / k
        envelope = math.exp(-(k ** 2) / lambda_coeff)
        total += harmonic * envelope
    return total / math.pi


def karmic_inertia(k0: float, lambda_coeff: float, n: int) -> float:
    """
    Eq. 4 + Eq. 7b: Kn = K0 · e^(-λn)
    The karmic inertia at incarnation n. Approaches 0 as n→∞ if λ > 0.
    Liberation condition: Kn < LIBERATION_THRESHOLD (0.05)
    """
    return k0 * math.exp(-lambda_coeff * n)


def coherence(lambda_coeff: float, n: int) -> float:
    """
    Eq. 7a: C(n,λ) = 1 - e^(-λn)
    The coherence level — how much of the karmic pattern has been recognized.
    C → 1 as n → ∞. Liberation at C > 0.95.
    """
    return 1.0 - math.exp(-lambda_coeff * n)


def adjacency_coefficient(k_phi_1: float, k_phi_2: float, psi_1: float, psi_2: float) -> float:
    """
    Eq. 5: A(C1,C2) = ∫ [Ψ(C1)·Ψ(C2)] / dφ(C1,C2) dΩ
    Approximated as: A = (Ψ1·Ψ2) / (1 + |φ1-φ2|)
    Returns [0,1] — probability that C2 is accessible from C1.
    """
    phase_distance = abs(k_phi_1 - k_phi_2)
    overlap = psi_1 * psi_2
    return overlap / (1.0 + phase_distance)


def archetypal_composition(archetype_weights: dict, tau: float) -> dict:
    """
    Eq. 6: Φ(Ψ) = Σ αj · Aj(Ψ) · e^(-βj·τ)
    Returns current archetypal activation weights given karmic time τ.
    βj = 0.05 (archetypal decay rate — slow, archetypes persist)
    """
    beta = 0.05
    result = {}
    for arch_code, alpha in archetype_weights.items():
        result[arch_code] = alpha * math.exp(-beta * tau)
    return result


def is_liberated(k_value: float, coherence_value: float) -> bool:
    """
    Liberation condition: K(x) < 0.05 AND C > 0.95
    """
    return k_value < 0.05 and coherence_value > 0.95


LIBERATION_THRESHOLD = 0.05
COHERENCE_LIBERATION = 0.95
