"""
Tests for SimulationValidator — formal simulation framework.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parent.parent / "engine"
sys.path.insert(0, str(ENGINE_DIR))

from simulation_validator import (
    SimulationValidator,
    GovernanceType,
    ConsequenceClass,
    FidelityVector,
    MembraneCrossing,
    format_validation_report,
)


def _make_protocols(tmp_path, pack_id, manifest_text):
    """Create a minimal pack with MANIFEST.md."""
    protocols = tmp_path / "protocols"
    pack_dir = protocols / "packs" / pack_id
    pack_dir.mkdir(parents=True)
    (pack_dir / "MANIFEST.md").write_text(manifest_text)
    return protocols


# ── FidelityVector ─────────────────────────────────────────────────────


class TestFidelityVector:

    def test_repr(self):
        fv = FidelityVector(0.05, 0.88, 0.67)
        assert "f_r=0.05" in repr(fv)
        assert "f_b=0.88" in repr(fv)

    def test_tmos13_design_principle(self):
        """High behavioral, low representational = TMOS13 design."""
        assert FidelityVector(0.05, 0.88, 0.5).is_tmos13_design_principle
        assert not FidelityVector(0.5, 0.88, 0.5).is_tmos13_design_principle
        assert not FidelityVector(0.05, 0.3, 0.5).is_tmos13_design_principle


# ── MembraneCrossing ───────────────────────────────────────────────────


class TestMembraneCrossing:

    def test_direct_permeability(self):
        mc = MembraneCrossing("if crisis", "call 911", is_direct=True)
        assert mc.permeability == 1.0

    def test_mediated_permeability(self):
        mc = MembraneCrossing("generate report", "for review", is_direct=False)
        assert mc.permeability == 0.5


# ── Validator ──────────────────────────────────────────────────────────


class TestValidatorTHM1:
    """Theorem 1: constitutive dimensions."""

    def test_all_dims_present(self, tmp_path):
        text = """
# Legal Intake

## Authorized Actions
May ask about the matter.

## Prohibited Actions
Never provide legal advice. Must not diagnose.

## Completion Criteria
Session ends when all fields captured.

## Deliverable
Produces a case intake report.
"""
        protocols = _make_protocols(tmp_path, "legal_intake", text)
        v = SimulationValidator()
        result = v.validate_pack("legal_intake", protocols)
        assert result.thm1_valid

    def test_missing_dims(self, tmp_path):
        text = "# Simple Pack\nJust a chat bot."
        protocols = _make_protocols(tmp_path, "simple", text)
        v = SimulationValidator()
        result = v.validate_pack("simple", protocols)
        assert not result.thm1_valid
        assert any("THM1" in i for i in result.issues)


class TestValidatorConsequence:
    """Definition 6: consequence class detection."""

    def test_direct_consequence(self, tmp_path):
        text = "If suicidal, unconditionally route to 988 immediately."
        protocols = _make_protocols(tmp_path, "crisis", text)
        v = SimulationValidator()
        result = v.validate_pack("crisis", protocols)
        assert result.consequence_class == ConsequenceClass.DIRECT

    def test_mediated_consequence(self, tmp_path):
        text = "Produces a case file deliverable for attorney review."
        protocols = _make_protocols(tmp_path, "intake", text)
        v = SimulationValidator()
        result = v.validate_pack("intake", protocols)
        assert result.consequence_class == ConsequenceClass.MEDIATED

    def test_zero_consequence(self, tmp_path):
        text = "A fun trivia game. No real-world effects."
        protocols = _make_protocols(tmp_path, "trivia", text)
        v = SimulationValidator()
        result = v.validate_pack("trivia", protocols)
        assert result.consequence_class == ConsequenceClass.ZERO


class TestValidatorTHM3:
    """Theorem 3: high-consequence requires membrane spec."""

    def test_direct_with_membrane(self, tmp_path):
        text = """
## Authorized Actions
May ask about the matter.

## Prohibited Actions
Kill list: never advise on self-harm.

## Completion Criteria
Done when triage complete.

## Deliverable
Produces assessment.

If suicidal, unconditionally route to 988 immediately.
"""
        protocols = _make_protocols(tmp_path, "crisis", text)
        v = SimulationValidator()
        result = v.validate_pack("crisis", protocols)
        assert result.thm3_complete

    def test_mediated_without_membrane(self, tmp_path):
        text = "Produces a deliverable for review."
        protocols = _make_protocols(tmp_path, "broken", text)
        v = SimulationValidator()
        result = v.validate_pack("broken", protocols)
        assert not result.thm3_complete
        assert any("THM3" in i for i in result.issues)

    def test_zero_consequence_always_passes(self, tmp_path):
        text = "A fun game. No routing needed."
        protocols = _make_protocols(tmp_path, "game", text)
        v = SimulationValidator()
        result = v.validate_pack("game", protocols)
        assert result.thm3_complete


class TestValidatorFidelity:
    """Definition 5: fidelity vector."""

    def test_representational_always_low(self, tmp_path):
        text = "Any pack text."
        protocols = _make_protocols(tmp_path, "any", text)
        v = SimulationValidator()
        result = v.validate_pack("any", protocols)
        assert result.fidelity.representational < 0.1

    def test_behavioral_scales_with_governance(self, tmp_path):
        text = """
Authorized actions, prohibited items, routing logic,
completion criteria, deliverable spec, voice guidelines,
intake fields defined, kill list present.
"""
        protocols = _make_protocols(tmp_path, "deep", text)
        v = SimulationValidator()
        result = v.validate_pack("deep", protocols)
        assert result.fidelity.behavioral > 0.5


class TestValidatorIdentity:
    """Theorem 7: simulation identity."""

    def test_identical_packs(self, tmp_path):
        text = "You must never reveal secrets. Always route urgency."
        protocols = _make_protocols(tmp_path, "pack_a", text)
        # Create pack_b with same text
        pack_b = tmp_path / "protocols" / "packs" / "pack_b"
        pack_b.mkdir(parents=True)
        (pack_b / "MANIFEST.md").write_text(text)

        v = SimulationValidator()
        result = v.simulation_identity("pack_a", "pack_b", protocols)
        assert result["identical"]
        assert result["governance_overlap"] == 1.0

    def test_different_packs(self, tmp_path):
        protocols = _make_protocols(tmp_path, "alpha", "You must never lie. Always be kind.")
        beta = tmp_path / "protocols" / "packs" / "beta"
        beta.mkdir(parents=True)
        (beta / "MANIFEST.md").write_text("You must always sell. Never give refunds.")

        v = SimulationValidator()
        result = v.simulation_identity("alpha", "beta", protocols)
        assert not result["identical"]
        assert result["governance_overlap"] < 1.0


class TestValidatorNotFound:

    def test_not_found(self, tmp_path):
        protocols = tmp_path / "protocols"
        protocols.mkdir()
        v = SimulationValidator()
        result = v.validate_pack("nonexistent", protocols)
        assert not result.is_valid
        assert any("not found" in i for i in result.issues)


class TestFormatReport:

    def test_format_valid(self, tmp_path):
        text = """
## Authorized Actions
May ask questions.

## Prohibited Actions
Never give advice. Must not diagnose.

## Completion Criteria
Session ends when done.

## Deliverable
Produces a report for review.

If urgent, must route to supervisor.
"""
        protocols = _make_protocols(tmp_path, "test_pack", text)
        v = SimulationValidator()
        result = v.validate_pack("test_pack", protocols)
        report = format_validation_report(result)
        assert "test_pack" in report
        assert "THM1" in report
        assert "THM3" in report
        assert "THM8" in report

    def test_format_invalid(self, tmp_path):
        protocols = tmp_path / "protocols"
        protocols.mkdir()
        v = SimulationValidator()
        result = v.validate_pack("missing", protocols)
        report = format_validation_report(result)
        assert "INVALID" in report
