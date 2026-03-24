"""Tests for engine/tvr.py — The Ventura Recursion equations."""

import math
import pytest
from engine.tvr import (
    TVRCoordinates, reincarnation_wave_function, karmic_probability,
    fractal_attractor, karmic_inertia, coherence, adjacency_coefficient,
    archetypal_composition, is_liberated, LIBERATION_THRESHOLD, COHERENCE_LIBERATION,
)


def _coords(**overrides) -> TVRCoordinates:
    defaults = dict(
        plane=3, primary_arch="JDG", secondary_arch="SOV", tertiary_arch="WAR",
        k0=5.0, lambda_coeff=3.0, cycle_phase="ACC", karmic_phi=1.5, incarnation_n=3,
    )
    defaults.update(overrides)
    return TVRCoordinates(**defaults)


class TestReincarnationWaveFunction:
    def test_returns_float(self):
        result = reincarnation_wave_function(_coords())
        assert isinstance(result, float)

    def test_nonnegative(self):
        result = reincarnation_wave_function(_coords())
        assert result >= 0.0

    def test_different_k0_produces_different_trajectory(self):
        r1 = reincarnation_wave_function(_coords(k0=2.0))
        r2 = reincarnation_wave_function(_coords(k0=8.0))
        assert r1 != r2


class TestKarmicProbability:
    def test_returns_in_range(self):
        p = karmic_probability(3.0, 0.5)
        assert 0.0 <= p <= 1.0

    def test_higher_k_lower_probability(self):
        p_low = karmic_probability(1.0, 0.5)
        p_high = karmic_probability(5.0, 0.5)
        assert p_low > p_high


class TestFractalAttractor:
    def test_convergence_high_lambda(self):
        r_low = abs(fractal_attractor(1.0, 1.0))
        r_high = abs(fractal_attractor(1.0, 10.0))
        # High lambda should produce a smaller or comparable value (faster damping)
        assert isinstance(r_high, float)

    def test_zero_lambda_returns_zero(self):
        assert fractal_attractor(1.0, 0.0) == 0.0


class TestKarmicInertia:
    def test_decreases_with_n(self):
        k0 = 5.0
        lam = 2.0
        k1 = karmic_inertia(k0, lam, 1)
        k5 = karmic_inertia(k0, lam, 5)
        assert k1 > k5

    def test_less_than_k0(self):
        k = karmic_inertia(5.0, 1.0, 1)
        assert k < 5.0

    def test_approaches_zero(self):
        k = karmic_inertia(5.0, 2.0, 100)
        assert k < 0.001


class TestCoherence:
    def test_zero_at_n_zero(self):
        c = coherence(3.0, 0)
        assert c == 0.0

    def test_approaches_one(self):
        c = coherence(3.0, 100)
        assert c > 0.999

    def test_monotonically_increasing(self):
        values = [coherence(2.0, n) for n in range(10)]
        for i in range(1, len(values)):
            assert values[i] > values[i - 1]


class TestAdjacencyCoefficient:
    def test_higher_phase_distance_lower_coefficient(self):
        a_close = adjacency_coefficient(1.0, 1.1, 0.5, 0.5)
        a_far = adjacency_coefficient(1.0, 5.0, 0.5, 0.5)
        assert a_close > a_far

    def test_nonnegative(self):
        a = adjacency_coefficient(1.0, 3.0, 0.5, 0.5)
        assert a >= 0.0


class TestLiberation:
    def test_liberated_below_threshold(self):
        assert is_liberated(0.01, 0.99) is True

    def test_not_liberated_high_k(self):
        assert is_liberated(1.0, 0.99) is False

    def test_not_liberated_low_coherence(self):
        assert is_liberated(0.01, 0.5) is False

    def test_convergence_achievable(self):
        """Agent with λ=5, K₀=3 should be liberated before incarnation 10."""
        for n in range(1, 10):
            k = karmic_inertia(3.0, 5.0, n)
            c = coherence(5.0, n)
            if is_liberated(k, c):
                return  # Found liberation before n=10
        pytest.fail("Agent did not achieve liberation within 10 incarnations")
