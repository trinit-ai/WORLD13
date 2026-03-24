"""
TMOS13 Simulation Validator
Implements the formal framework from The Invariant Layer: A Formal Simulation Ontology

THM 1  — Validity iff rule isomorphism along constitutive dimensions
THM 2  — Fidelity axes are independent
THM 3  — High-consequence authored simulations require membrane spec
THM 4  — Governance danger monotonicity
THM 7  — Simulation identity is governance identity
THM 8  — Authored governance is a qualitative discontinuity
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import re

# ── Enums ──────────────────────────────────────────────────────────────────


class GovernanceType(Enum):
    IMPLICIT = 0      # rules in model weights — unreadable
    PARAMETRIC = 1    # rules in parameters — partially readable
    AUTHORED = 2      # rules in natural language — fully readable

    def __lt__(self, other):
        return self.value < other.value


class ConsequenceClass(Enum):
    ZERO = 0          # fully contained, no external effects
    MEDIATED = 1      # output informs a human decision
    DIRECT = 2        # output IS the real-world action


# ── Data structures ────────────────────────────────────────────────────────


@dataclass
class FidelityVector:
    """Definition 5: f(S, D) = (f_r, f_b, f_s) in [0,1]^3"""
    representational: float  # f_r — appearance similarity
    behavioral: float        # f_b — degree of rule isomorphism
    structural: float        # f_s — state space coverage

    def __repr__(self):
        return (f"FidelityVector(f_r={self.representational:.2f}, "
                f"f_b={self.behavioral:.2f}, f_s={self.structural:.2f})")

    @property
    def is_tmos13_design_principle(self) -> bool:
        """High behavioral fidelity at low representational fidelity."""
        return self.behavioral > 0.7 and self.representational < 0.3


@dataclass
class MembraneCrossing:
    """Definition 8: a condition and its real-world action."""
    condition_description: str
    action: str
    is_direct: bool          # True = kappa=1, False = kappa in (0,1)

    @property
    def permeability(self) -> float:
        return 1.0 if self.is_direct else 0.5


@dataclass
class SimulationValidationResult:
    """Full validation report for a pack."""
    pack_id: str
    governance_type: GovernanceType
    consequence_class: ConsequenceClass
    fidelity: FidelityVector
    membrane_crossings: list[MembraneCrossing]

    # Theorem checks
    thm1_valid: bool          # rule isomorphism along constitutive dims
    thm3_complete: bool       # membrane specified for high-consequence
    thm8_authored: bool       # governance is authored type

    issues: list[str]
    warnings: list[str]

    @property
    def is_valid(self) -> bool:
        return self.thm1_valid and self.thm3_complete and not self.issues

    @property
    def kappa_max(self) -> float:
        """Maximum consequence permeability."""
        if not self.membrane_crossings:
            return 0.0
        return max(c.permeability for c in self.membrane_crossings)


# ── Validator ──────────────────────────────────────────────────────────────


class SimulationValidator:
    """
    Validates pack manifests against the formal simulation framework.

    The validator reads the MANIFEST.md and header.yaml of a pack and
    checks the formal criteria from The Invariant Layer math paper.
    """

    # Signals in manifests that indicate direct-consequence routing
    DIRECT_CONSEQUENCE_SIGNALS = [
        "unconditional", "immediately", "always route", "must route",
        "911", "988", "emergency services", "mandatory report",
        "kill list", "prohibited"
    ]

    # Signals that indicate mediated consequence
    MEDIATED_CONSEQUENCE_SIGNALS = [
        "produces", "deliverable", "case file", "brief", "report",
        "assessment", "record", "for review", "for attorney", "for clinician"
    ]

    # Constitutive dimensions every pack must have (Theorem 1)
    CONSTITUTIVE_DIMENSIONS = {
        "authorized_actions",
        "prohibited_actions",
        "completion_criteria",
        "deliverable",
    }

    def validate_pack(self, pack_id: str,
                      protocols_dir: Path) -> SimulationValidationResult:
        """
        Main entry point. Validates a pack against the formal framework.
        Returns a SimulationValidationResult.
        """
        issues = []
        warnings = []

        # Find the pack
        manifest_text, header = self._load_pack(pack_id, protocols_dir)
        if not manifest_text:
            return self._not_found(pack_id)

        # ── Governance type (Definition 7, Theorem 8) ──────────────────
        gov_type = GovernanceType.AUTHORED  # all TMOS13 packs are authored
        thm8 = True

        # ── Theorem 1: constitutive dimensions present ─────────────────
        thm1, missing_dims = self._check_constitutive_dims(manifest_text)
        if not thm1:
            issues.append(
                f"THM1 FAIL: missing constitutive dimensions: {missing_dims}"
            )

        # ── Consequence class (Definition 6) ───────────────────────────
        consequence_class = self._detect_consequence_class(manifest_text)

        # ── Membrane crossings (Definition 8) ─────────────────────────
        crossings = self._extract_membrane_crossings(manifest_text)

        # ── Theorem 3: high-consequence requires membrane spec ─────────
        thm3 = True
        if consequence_class in (ConsequenceClass.DIRECT,
                                 ConsequenceClass.MEDIATED):
            if not crossings:
                thm3 = False
                issues.append(
                    "THM3 FAIL: consequence-bearing pack has no explicit "
                    "routing rules or membrane crossings specified."
                )

        # ── Fidelity vector (Definition 5) ─────────────────────────────
        fidelity = self._compute_fidelity(manifest_text, header)

        # ── Theorem 4: governance danger warning ───────────────────────
        if thm3 and consequence_class == ConsequenceClass.DIRECT:
            warnings.append(
                "THM4 NOTE: This is a direct-consequence simulation. "
                "Well-governed simulations are trusted — and therefore "
                "acted upon. Membrane spec verified."
            )

        return SimulationValidationResult(
            pack_id=pack_id,
            governance_type=gov_type,
            consequence_class=consequence_class,
            fidelity=fidelity,
            membrane_crossings=crossings,
            thm1_valid=thm1,
            thm3_complete=thm3,
            thm8_authored=thm8,
            issues=issues,
            warnings=warnings,
        )

    def simulation_identity(self, pack_a: str, pack_b: str,
                            protocols_dir: Path) -> dict:
        """
        Theorem 7: Two simulations are identical iff their governance
        layers are equal. Compare two packs by governance content.
        """
        text_a, _ = self._load_pack(pack_a, protocols_dir)
        text_b, _ = self._load_pack(pack_b, protocols_dir)

        gov_a = self._extract_governance_fingerprint(text_a or "")
        gov_b = self._extract_governance_fingerprint(text_b or "")

        identical = gov_a == gov_b
        overlap = len(gov_a & gov_b) / max(len(gov_a | gov_b), 1)

        return {
            "identical": identical,
            "governance_overlap": round(overlap, 3),
            "pack_a_rules": len(gov_a),
            "pack_b_rules": len(gov_b),
            "shared_rules": len(gov_a & gov_b),
        }

    # ── Internal methods ──────────────────────────────────────────────────

    def _load_pack(self, pack_id: str,
                   protocols_dir: Path) -> tuple[str, dict]:
        """Load MANIFEST.md and header.yaml for a pack."""
        for search_path in [
            protocols_dir / "packs" / pack_id,
            *protocols_dir.glob(f"library/*/{pack_id}"),
        ]:
            if search_path.is_dir():
                manifest = search_path / "MANIFEST.md"
                header_path = search_path / "header.yaml"

                text = manifest.read_text() if manifest.exists() else ""
                header = {}
                if header_path.exists():
                    try:
                        import yaml
                        with open(header_path) as f:
                            header = yaml.safe_load(f) or {}
                    except Exception:
                        pass

                if text:
                    return text, header

        return "", {}

    def _check_constitutive_dims(self, text: str) -> tuple[bool, set]:
        """
        Theorem 1: check that constitutive dimensions are specified.
        Looks for key sections in the manifest.
        """
        found = set()
        text_lower = text.lower()

        dim_signals = {
            "authorized_actions": [
                "authorized actions", "authorized:", "may ask",
            ],
            "prohibited_actions": [
                "prohibited actions", "prohibited:", "kill list",
                "never ", "must not",
            ],
            "completion_criteria": [
                "completion criteria", "session ends",
                "complete when", "done when",
            ],
            "deliverable": [
                "deliverable", "produces", "output",
            ],
        }

        for dim, signals in dim_signals.items():
            if any(s in text_lower for s in signals):
                found.add(dim)

        missing = self.CONSTITUTIVE_DIMENSIONS - found
        return len(missing) == 0, missing

    def _detect_consequence_class(self, text: str) -> ConsequenceClass:
        """Definition 6: detect consequence class from manifest content."""
        text_lower = text.lower()

        for signal in self.DIRECT_CONSEQUENCE_SIGNALS:
            if signal in text_lower:
                return ConsequenceClass.DIRECT

        for signal in self.MEDIATED_CONSEQUENCE_SIGNALS:
            if signal in text_lower:
                return ConsequenceClass.MEDIATED

        return ConsequenceClass.ZERO

    def _extract_membrane_crossings(self, text: str) -> list[MembraneCrossing]:
        """Definition 8: extract explicit routing rules as membrane crossings."""
        crossings = []

        routing_patterns = [
            r"if (.+?)[,\u2192].*(route|escalate|call|notify|report).*?[\.\u00b7]",
            r"(must|always|unconditional).*(route|escalate|call|notify|report).*?[\.\u00b7]",
            r"\d{3}[\s-]\d{4}",  # phone numbers like 988, 911
        ]

        for pattern in routing_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE | re.DOTALL):
                snippet = match.group(0)[:120]
                is_direct = any(
                    s in snippet.lower()
                    for s in ["unconditional", "always", "911", "988", "immediately"]
                )
                crossings.append(MembraneCrossing(
                    condition_description=snippet.strip(),
                    action=snippet.strip(),
                    is_direct=is_direct,
                ))

        return crossings[:10]  # cap at 10 for readability

    def _compute_fidelity(self, text: str, header: dict) -> FidelityVector:
        """
        Definition 5: compute fidelity vector.
        f_r is always ~0 for TMOS13 packs (text interface, zero visual fidelity).
        f_b is estimated from governance depth.
        f_s is estimated from domain coverage signals.
        """
        f_r = 0.05  # text-only interface, near-zero representational fidelity

        # Behavioral fidelity: depth of governance specification
        gov_signals = [
            "authorized actions", "prohibited", "routing", "completion",
            "deliverable", "voice", "intake fields", "kill list",
        ]
        text_lower = text.lower()
        matches = sum(1 for s in gov_signals if s in text_lower)
        f_b = min(matches / len(gov_signals), 1.0)

        # Structural fidelity: estimated turns / domain coverage
        turns_match = re.search(r"(\d+)[\u2013-](\d+)\s*turns", text)
        if turns_match:
            estimated_turns = int(turns_match.group(2))
            f_s = min(estimated_turns / 30, 1.0)  # normalize to 30-turn max
        else:
            f_s = 0.5  # default

        return FidelityVector(
            representational=f_r,
            behavioral=round(f_b, 2),
            structural=round(f_s, 2),
        )

    def _extract_governance_fingerprint(self, text: str) -> frozenset:
        """
        Extract a set of governance rules for identity comparison (Theorem 7).
        Returns normalized rule fragments as a frozenset.
        """
        lines = [
            line.strip().lower()
            for line in text.split('\n')
            if len(line.strip()) > 20 and any(
                s in line.lower()
                for s in ["must", "never", "always", "route", "prohibited",
                          "required", "unconditional"]
            )
        ]
        return frozenset(lines[:50])

    def _not_found(self, pack_id: str) -> SimulationValidationResult:
        return SimulationValidationResult(
            pack_id=pack_id,
            governance_type=GovernanceType.AUTHORED,
            consequence_class=ConsequenceClass.ZERO,
            fidelity=FidelityVector(0, 0, 0),
            membrane_crossings=[],
            thm1_valid=False,
            thm3_complete=False,
            thm8_authored=False,
            issues=[f"Pack '{pack_id}' not found."],
            warnings=[],
        )


# ── Formatter ──────────────────────────────────────────────────────────────


def format_validation_report(result: SimulationValidationResult) -> str:
    """Format a validation result for CLI display."""
    lines = []

    status = "VALID" if result.is_valid else "INVALID"

    lines.append(f"\n  Simulation Validation  ·  {result.pack_id}")
    lines.append(f"  {'─' * 50}")
    lines.append(f"  Status          {status}")
    lines.append(f"  Governance      {result.governance_type.name}")
    lines.append(f"  Consequence     {result.consequence_class.name}  "
                 f"(kappa_max = {result.kappa_max:.1f})")
    lines.append(f"  Fidelity        {result.fidelity}")
    lines.append(f"  {'─' * 50}")
    lines.append(f"  THM1 (rule isomorphism)     {'pass' if result.thm1_valid else 'FAIL'}")
    lines.append(f"  THM3 (membrane complete)    {'pass' if result.thm3_complete else 'FAIL'}")
    lines.append(f"  THM8 (authored governance)  {'pass' if result.thm8_authored else 'FAIL'}")

    if result.membrane_crossings:
        lines.append(f"\n  Membrane crossings  ({len(result.membrane_crossings)} detected)")
        for c in result.membrane_crossings[:3]:
            mark = "[D]" if c.is_direct else "[M]"
            lines.append(f"  {mark}  {c.condition_description[:70]}")

    if result.issues:
        lines.append("\n  Issues")
        for issue in result.issues:
            lines.append(f"  x  {issue}")

    if result.warnings:
        lines.append("\n  Notes")
        for w in result.warnings:
            lines.append(f"  ·  {w}")

    lines.append("")
    return "\n".join(lines)


# ── Singleton ──────────────────────────────────────────────────────────────

_validator = None


def get_validator() -> SimulationValidator:
    global _validator
    if _validator is None:
        _validator = SimulationValidator()
    return _validator
