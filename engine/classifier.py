"""
TMOS13 Opportunity Classifier

Rule-based classifier that evaluates transcripts against pack-defined
classification dimensions. Produces multi-dimensional OpportunityProfiles
with composite scoring.

Follows the same evaluation pattern as AlertClassifier in alerts.py.

Usage:
    classifier = OpportunityClassifier()
    profile = classifier.classify(transcript, classifier_config)
"""
import logging
import re
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional

from transcripts import SessionTranscript

logger = logging.getLogger("tmos13.classifier")


# ─── Data Models ─────────────────────────────────────────

@dataclass
class ClassificationDimension:
    """A single axis of classification (e.g., value, urgency, complexity)."""
    id: str = ""
    levels: list[str] = field(default_factory=list)
    default: str = ""

    @staticmethod
    def from_dict(d: dict) -> "ClassificationDimension":
        return ClassificationDimension(
            id=d.get("id", ""),
            levels=d.get("levels", []),
            default=d.get("default", ""),
        )


@dataclass
class ClassificationRule:
    """A rule that sets a dimension level based on trigger evaluation."""
    dimension: str = ""
    trigger: str = ""
    level: str = ""
    keywords: list[str] = field(default_factory=list)
    field_id: str = ""
    cartridge: str = ""
    threshold: int = 0
    priority: int = 100

    @staticmethod
    def from_dict(d: dict) -> "ClassificationRule":
        return ClassificationRule(
            dimension=d.get("dimension", ""),
            trigger=d.get("trigger", ""),
            level=d.get("level", ""),
            keywords=d.get("keywords", []),
            field_id=d.get("field_id", ""),
            cartridge=d.get("cartridge", ""),
            threshold=d.get("threshold", 0),
            priority=d.get("priority", 100),
        )


@dataclass
class OpportunityProfile:
    """The classified output — a multi-dimensional assessment of an opportunity."""
    profile_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    session_id: str = ""
    exchange_id: str = ""
    pack_id: str = ""

    # Classification results: dimension_id → level
    dimensions: dict[str, str] = field(default_factory=dict)

    # What triggered each classification
    evidence: dict[str, list[str]] = field(default_factory=dict)

    # Composite score (0.0–1.0) computed from dimension levels
    composite_score: float = 0.0

    # Contact and summary from transcript
    contact_info: Optional[dict] = None
    summary: str = ""

    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


# ─── Opportunity Classifier ─────────────────────────────

class OpportunityClassifier:
    """
    Evaluates transcripts against pack-defined classification dimensions.
    Same evaluation pattern as AlertClassifier.
    """

    _TRIGGER_HANDLERS = {
        "keywords": "_eval_keywords",
        "contact_present": "_eval_contact_present",
        "field_extracted": "_eval_field_extracted",
        "turn_count": "_eval_turn_count",
        "cartridge_visited": "_eval_cartridge_visited",
    }

    def classify(
        self,
        transcript: SessionTranscript,
        classifier_config: dict,
        extracted_data=None,
        exchange_id: str = "",
    ) -> OpportunityProfile:
        """
        Classify a transcript across all dimensions defined in the config.

        Args:
            transcript: The session transcript to evaluate.
            classifier_config: The "classification" section from the pack manifest.
            extracted_data: Optional ExtractedData from deliverable pipeline.
            exchange_id: Optional ambassador exchange ID.

        Returns:
            OpportunityProfile with dimension levels and composite score.
        """
        profile = OpportunityProfile(
            session_id=transcript.session_id,
            exchange_id=exchange_id,
            pack_id=transcript.pack_id,
            contact_info=transcript.contact_info,
            summary=transcript.summary or "",
        )

        if not classifier_config:
            return profile

        # Load dimensions
        dimensions_data = classifier_config.get("dimensions", [])
        dimensions = [ClassificationDimension.from_dict(d) for d in dimensions_data]
        dim_map = {d.id: d for d in dimensions}

        # Load rules
        rules_data = classifier_config.get("rules", [])
        rules = [ClassificationRule.from_dict(r) for r in rules_data]

        # Initialize dimensions with defaults
        for dim in dimensions:
            profile.dimensions[dim.id] = dim.default
            profile.evidence[dim.id] = []

        # Group rules by dimension
        rules_by_dim: dict[str, list[ClassificationRule]] = {}
        for rule in rules:
            if rule.dimension not in rules_by_dim:
                rules_by_dim[rule.dimension] = []
            rules_by_dim[rule.dimension].append(rule)

        # Evaluate each dimension
        for dim_id, dim_rules in rules_by_dim.items():
            if dim_id not in dim_map:
                logger.warning(f"Rule references unknown dimension: {dim_id}")
                continue

            # Sort by priority (lower number = evaluated first, wins if matches)
            dim_rules.sort(key=lambda r: r.priority)

            best_level = None
            best_priority = float("inf")

            for rule in dim_rules:
                handler_name = self._TRIGGER_HANDLERS.get(rule.trigger)
                if not handler_name:
                    logger.warning(f"Unknown classification trigger: {rule.trigger}")
                    continue

                handler = getattr(self, handler_name)
                result = handler(transcript, rule, extracted_data)

                if result is not None:
                    if rule.priority < best_priority:
                        best_priority = rule.priority
                        best_level = rule.level
                    profile.evidence[dim_id].append(result)

            if best_level is not None:
                profile.dimensions[dim_id] = best_level

        # Compute composite score
        profile.composite_score = self._compute_score(profile.dimensions, dim_map)

        logger.info(
            f"Classified session={transcript.session_id}: "
            f"dims={profile.dimensions} score={profile.composite_score:.2f}"
        )
        return profile

    def _compute_score(
        self,
        dimensions: dict[str, str],
        dim_map: dict[str, ClassificationDimension],
    ) -> float:
        """
        Composite score: sum of (level_index / max_level_index) across dimensions,
        divided by dimension count.
        """
        if not dimensions or not dim_map:
            return 0.0

        total = 0.0
        count = 0

        for dim_id, level in dimensions.items():
            dim = dim_map.get(dim_id)
            if not dim or not dim.levels:
                continue

            max_idx = len(dim.levels) - 1
            if max_idx == 0:
                total += 1.0 if level in dim.levels else 0.0
            else:
                try:
                    idx = dim.levels.index(level)
                    total += idx / max_idx
                except ValueError:
                    pass  # unknown level, contributes 0
            count += 1

        return round(total / count, 4) if count else 0.0

    # ─── Trigger Evaluators ──────────────────────────────

    def _eval_keywords(
        self,
        transcript: SessionTranscript,
        rule: ClassificationRule,
        extracted_data=None,
    ) -> Optional[str]:
        """Trigger: keywords — fires when any keyword found in user messages."""
        if not rule.keywords:
            return None

        all_user_text = " ".join(
            e.content for e in transcript.entries if e.role == "user"
        ).lower()

        matched = []
        for kw in rule.keywords:
            pattern = re.escape(kw.lower())
            if re.search(r"\b" + pattern + r"\b", all_user_text):
                matched.append(kw)

        if matched:
            return f"Keywords: {', '.join(matched)}"
        return None

    def _eval_contact_present(
        self,
        transcript: SessionTranscript,
        rule: ClassificationRule,
        extracted_data=None,
    ) -> Optional[str]:
        """Trigger: contact_present — fires when name + email or phone collected."""
        ci = transcript.contact_info
        if not ci:
            return None

        has_name = bool(ci.get("name"))
        has_email = bool(ci.get("email"))
        has_phone = bool(ci.get("phone"))

        if has_name and (has_email or has_phone):
            return f"Contact present: {ci.get('name')}"
        return None

    def _eval_field_extracted(
        self,
        transcript: SessionTranscript,
        rule: ClassificationRule,
        extracted_data=None,
    ) -> Optional[str]:
        """Trigger: field_extracted — fires when a specific field exists in extracted data."""
        if not extracted_data or not rule.field_id:
            return None

        fields = getattr(extracted_data, "fields", {})
        if rule.field_id in fields:
            return f"Field extracted: {rule.field_id}"
        return None

    def _eval_turn_count(
        self,
        transcript: SessionTranscript,
        rule: ClassificationRule,
        extracted_data=None,
    ) -> Optional[str]:
        """Trigger: turn_count — fires when session meets or exceeds threshold."""
        threshold = rule.threshold if rule.threshold > 0 else 10
        if transcript.turn_count >= threshold:
            return f"Turn count: {transcript.turn_count} >= {threshold}"
        return None

    def _eval_cartridge_visited(
        self,
        transcript: SessionTranscript,
        rule: ClassificationRule,
        extracted_data=None,
    ) -> Optional[str]:
        """Trigger: cartridge_visited — fires when cartridge in history."""
        if not rule.cartridge:
            return None

        if rule.cartridge in transcript.cartridge_history:
            return f"Cartridge visited: {rule.cartridge}"
        return None


# ─── Opportunity Store ───────────────────────────────────

class OpportunityStore:
    """In-memory store for classified opportunity profiles."""

    def __init__(self):
        self._profiles: dict[str, OpportunityProfile] = {}
        self._session_index: dict[str, str] = {}  # session_id → profile_id
        logger.info("OpportunityStore initialized")

    def add(self, profile: OpportunityProfile) -> OpportunityProfile:
        """Store a classified profile."""
        self._profiles[profile.profile_id] = profile
        if profile.session_id:
            self._session_index[profile.session_id] = profile.profile_id
        return profile

    def get(self, profile_id: str) -> Optional[OpportunityProfile]:
        """Get a profile by ID."""
        return self._profiles.get(profile_id)

    def get_by_session(self, session_id: str) -> Optional[OpportunityProfile]:
        """Get a profile by session ID."""
        pid = self._session_index.get(session_id)
        if pid:
            return self._profiles.get(pid)
        return None

    def list_profiles(
        self,
        pack_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[OpportunityProfile]:
        """List profiles with optional filters."""
        results = list(self._profiles.values())
        if pack_id:
            results = [p for p in results if p.pack_id == pack_id]
        results.sort(key=lambda p: p.created_at, reverse=True)
        return results[:limit]

    def get_stats(self) -> dict:
        """Return store statistics."""
        by_pack: dict[str, int] = {}
        total_score = 0.0
        for p in self._profiles.values():
            by_pack[p.pack_id] = by_pack.get(p.pack_id, 0) + 1
            total_score += p.composite_score
        n = len(self._profiles) or 1
        return {
            "total_profiles": len(self._profiles),
            "avg_composite_score": round(total_score / n, 4),
            "by_pack": by_pack,
        }
