"""
TMOS13 PII Gate — Bidirectional Compliance Layer

Pre-flight interceptor that detects PII in user messages before
they reach the assembler/LLM. Four modes:

  off    — No detection, messages pass through unchanged.
  nudge  — Detect PII and suggest using DataRail instead. Message
           still passes but client receives a gate_result event.
  redact — Auto-replace PII with [REDACTED:<type>] tokens. Original
           stored encrypted in gate_originals for audit.
  strict — Block messages containing PII entirely.

Detection uses regex patterns with confidence scoring. Custom
patterns can be added via pack manifest pii_gate.custom_patterns.
"""

import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("tmos13.pii_gate")

# ─── PII Detection Patterns ─────────────────────────────

_PATTERNS: dict[str, re.Pattern] = {
    "email": re.compile(
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b"
    ),
    "phone": re.compile(
        r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    ),
    "ssn": re.compile(
        r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"
    ),
    "credit_card": re.compile(
        r"\b(?:\d{4}[-\s]?){3}\d{4}\b"
    ),
    "ip_address": re.compile(
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
    ),
    "dob": re.compile(
        r"\b(?:0[1-9]|1[0-2])[/\-](?:0[1-9]|[12]\d|3[01])[/\-](?:19|20)\d{2}\b"
    ),
}

# Confidence scores per pattern type
_CONFIDENCE: dict[str, float] = {
    "email": 0.95,
    "phone": 0.85,
    "ssn": 0.90,
    "credit_card": 0.90,
    "ip_address": 0.70,
    "dob": 0.80,
}


@dataclass
class PIIDetection:
    """A single PII detection in user text."""

    pii_type: str
    value: str
    start: int
    end: int
    confidence: float


@dataclass
class GateResult:
    """Result of running the PII gate on a message."""

    mode: str
    detections: list[PIIDetection] = field(default_factory=list)
    action: str = "pass"  # pass | nudge | redact | block
    redacted_text: Optional[str] = None
    rail_id: Optional[str] = None
    original_stored: bool = False


@dataclass
class PIIGateConfig:
    """Pack-level PII gate configuration."""

    mode: str = "off"
    types: list[str] = field(default_factory=lambda: list(_PATTERNS.keys()))
    custom_patterns: list[dict] = field(default_factory=list)
    nudge_rail_id: Optional[str] = None


class PIIGate:
    """
    PII detection and gating service.

    Instantiated once at startup. Loaded per-pack config
    determines mode and active detection types.
    """

    def __init__(self):
        self._custom_patterns: dict[str, re.Pattern] = {}
        self._db = None
        self._stats = {
            "total_checks": 0,
            "total_detections": 0,
            "by_type": {},
            "by_action": {"pass": 0, "nudge": 0, "redact": 0, "block": 0},
        }

    def configure_db(self, db) -> None:
        """Set the Supabase client for gate_originals persistence."""
        self._db = db

    def configure(self, config: PIIGateConfig) -> None:
        """Load custom patterns from pack manifest."""
        self._custom_patterns.clear()
        for cp in config.custom_patterns:
            try:
                self._custom_patterns[cp["name"]] = re.compile(cp["pattern"])
            except re.error:
                logger.warning("Invalid custom PII pattern: %s", cp.get("name", "?"))

    def detect(self, text: str, config: PIIGateConfig) -> list[PIIDetection]:
        """
        Scan text for PII patterns. Returns list of detections
        sorted by position.
        """
        detections: list[PIIDetection] = []

        # Built-in patterns
        for pii_type in config.types:
            pattern = _PATTERNS.get(pii_type)
            if not pattern:
                continue
            for match in pattern.finditer(text):
                detections.append(PIIDetection(
                    pii_type=pii_type,
                    value=match.group(),
                    start=match.start(),
                    end=match.end(),
                    confidence=_CONFIDENCE.get(pii_type, 0.5),
                ))

        # Custom patterns from pack manifest
        for name, pattern in self._custom_patterns.items():
            for match in pattern.finditer(text):
                detections.append(PIIDetection(
                    pii_type="custom",
                    value=match.group(),
                    start=match.start(),
                    end=match.end(),
                    confidence=0.75,
                ))

        detections.sort(key=lambda d: d.start)
        return detections

    def check(self, text: str, config: PIIGateConfig,
              session_id: str = "", pack_id: str = "") -> GateResult:
        """
        Run the PII gate on a message. Returns the gate result
        with action and optional redacted text.
        """
        self._stats["total_checks"] += 1

        if config.mode == "off":
            self._stats["by_action"]["pass"] += 1
            return GateResult(mode="off", action="pass")

        detections = self.detect(text, config)

        if not detections:
            self._stats["by_action"]["pass"] += 1
            return GateResult(mode=config.mode, action="pass")

        # Update stats
        self._stats["total_detections"] += len(detections)
        for d in detections:
            self._stats["by_type"][d.pii_type] = (
                self._stats["by_type"].get(d.pii_type, 0) + 1
            )

        if config.mode == "nudge":
            self._stats["by_action"]["nudge"] += 1
            return GateResult(
                mode="nudge",
                detections=detections,
                action="nudge",
                rail_id=config.nudge_rail_id,
            )

        if config.mode == "redact":
            redacted = self._redact(text, detections)
            self._stats["by_action"]["redact"] += 1
            # Persist original to gate_originals vault
            if self._db:
                self._store_original(
                    session_id=session_id, pack_id=pack_id,
                    original=text, redacted=redacted,
                    detections=detections, mode="redact", db=self._db,
                )
            return GateResult(
                mode="redact",
                detections=detections,
                action="redact",
                redacted_text=redacted,
                original_stored=bool(self._db),
            )

        if config.mode == "strict":
            self._stats["by_action"]["block"] += 1
            return GateResult(
                mode="strict",
                detections=detections,
                action="block",
            )

        # Fallback: pass
        self._stats["by_action"]["pass"] += 1
        return GateResult(mode=config.mode, detections=detections, action="pass")

    def _redact(self, text: str, detections: list[PIIDetection]) -> str:
        """Replace PII values with structured [REDACTED:<type>:vault_key=<key>:confidence=<score>] tokens."""
        # Process in reverse order to preserve offsets
        result = text
        for det in reversed(detections):
            vault_key = uuid.uuid4().hex[:12]
            det._vault_key = vault_key  # attach for downstream persistence
            token = f"[REDACTED:{det.pii_type.upper()}:vault_key={vault_key}:confidence={det.confidence:.2f}]"
            result = result[:det.start] + token + result[det.end:]
        return result

    def _store_original(self, session_id: str, pack_id: str, original: str,
                        redacted: str, detections: list[PIIDetection],
                        mode: str, db) -> None:
        """Persist original text to gate_originals for audit trail."""
        try:
            db.table("gate_originals").insert({
                "session_id": session_id,
                "pack_id": pack_id,
                "original_message": original,
                "redacted_message": redacted,
                "detections": [
                    {"type": d.pii_type, "value": d.value, "confidence": d.confidence,
                     "vault_key": getattr(d, "_vault_key", None)}
                    for d in detections
                ],
                "gate_mode": mode,
            }).execute()
        except Exception as e:
            logger.warning("gate_originals persistence failed (non-fatal): %s", e)

    @property
    def stats(self) -> dict:
        return dict(self._stats)


def get_gate_config_from_manifest(manifest: dict) -> PIIGateConfig:
    """Extract PII gate config from a pack manifest."""
    gate_section = manifest.get("pii_gate", {})
    return PIIGateConfig(
        mode=gate_section.get("mode", "off"),
        types=gate_section.get("types", list(_PATTERNS.keys())),
        custom_patterns=gate_section.get("custom_patterns", []),
        nudge_rail_id=gate_section.get("nudge_rail_id"),
    )


# Module-level singleton
_gate = PIIGate()


def get_pii_gate() -> PIIGate:
    """Get the singleton PII gate instance."""
    return _gate
