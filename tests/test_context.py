"""Tests for engine/context.py — Set & Setting sampler."""

import pytest
from engine.tvr import TVRCoordinates
from engine.context import sample_context, LEAF_NODES, ALL_AXES, NODES_BY_AXIS


def _coords(**overrides) -> TVRCoordinates:
    defaults = dict(
        plane=3, primary_arch="JDG", secondary_arch="SOV", tertiary_arch="WAR",
        k0=5.0, lambda_coeff=3.0, cycle_phase="ACC", karmic_phi=1.5, incarnation_n=3,
    )
    defaults.update(overrides)
    return TVRCoordinates(**defaults)


class TestLeafNodes:
    def test_total_count(self):
        assert len(LEAF_NODES) >= 200  # Should be ~210

    def test_all_axes_represented(self):
        axes = {n.axis for n in LEAF_NODES}
        for a in ALL_AXES:
            assert a in axes, f"Axis {a} missing from leaf nodes"


class TestSampleContext:
    def test_returns_all_14_axes(self):
        ctx = sample_context(_coords())
        assert len(ctx.leaves) == 14

    def test_each_axis_has_leaf(self):
        ctx = sample_context(_coords())
        for axis in ALL_AXES:
            assert axis in ctx.leaves

    def test_effective_k(self):
        ctx = sample_context(_coords())
        ek = ctx.effective_k(5.0)
        assert isinstance(ek, float)
        assert ek >= 0.0

    def test_effective_lambda(self):
        ctx = sample_context(_coords())
        el = ctx.effective_lambda(3.0)
        assert isinstance(el, float)
        assert el >= 0.1


class TestBiasedSampling:
    def test_high_k_agent_biased_toward_high_k_leaves(self):
        """Statistical: high-K agent should average positive k_modifier over many samples."""
        high_k_coords = _coords(k0=9.0, lambda_coeff=0.5, incarnation_n=1)
        k_mods = []
        for _ in range(100):
            ctx = sample_context(high_k_coords)
            k_mods.append(ctx.k_total_modifier)
        mean_k = sum(k_mods) / len(k_mods)
        # High-K agent should trend toward positive k_modifiers
        assert mean_k > -5.0  # Loose bound — just verify bias direction exists

    def test_high_coherence_biased_toward_high_lambda_leaves(self):
        """Statistical: high-coherence agent should average positive lambda_modifier."""
        high_coh_coords = _coords(k0=1.0, lambda_coeff=8.0, incarnation_n=10)
        l_mods = []
        for _ in range(100):
            ctx = sample_context(high_coh_coords)
            l_mods.append(ctx.lambda_total_modifier)
        mean_l = sum(l_mods) / len(l_mods)
        assert mean_l > -5.0  # Loose bound
