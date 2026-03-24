"""
TMOS13 Pitch Queue

Outbound draft generation. When a suite becomes pitch-ready, this module
generates channel-appropriate outbound content from the artifact suite.

Pitches are queued drafts — not sent automatically (unless auto_send is
configured). Production resolves recipients from pack config + team
membership. Phase 1 uses placeholder recipients.

Usage:
    generator = PitchGenerator()
    pitches = generator.generate_pitches(suite, profile, pitch_config, transcript)
    for pitch in pitches:
        pitch_store.add(pitch)
"""
import logging
import re
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from architect import ArtifactSuite, ArtifactStatus
from classifier import OpportunityProfile
from transcripts import SessionTranscript

logger = logging.getLogger("tmos13.pitch")


# ─── Data Models ─────────────────────────────────────────

class PitchStatus(str, Enum):
    QUEUED = "queued"
    DRAFT = "draft"
    APPROVED = "approved"
    SENT = "sent"
    FAILED = "failed"


@dataclass
class PitchSpec:
    """
    Specification for a pitch output, loaded from pack manifest
    under architect.pitch.specs[].
    """
    id: str = ""
    name: str = ""
    channel: str = "email"
    template: str = ""
    subject_template: str = ""
    requires_artifacts: list[str] = field(default_factory=list)
    auto_send: bool = False

    @staticmethod
    def from_dict(d: dict) -> "PitchSpec":
        return PitchSpec(
            id=d.get("id", ""),
            name=d.get("name", ""),
            channel=d.get("channel", "email"),
            template=d.get("template", ""),
            subject_template=d.get("subject_template", ""),
            requires_artifacts=d.get("requires_artifacts", []),
            auto_send=d.get("auto_send", False),
        )


@dataclass
class Pitch:
    """A generated outbound draft."""
    pitch_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    suite_id: str = ""
    session_id: str = ""
    pack_id: str = ""
    spec_id: str = ""
    spec_name: str = ""

    # Content
    channel: str = "email"
    subject: str = ""
    body: str = ""

    # Recipients (placeholder for Phase 1)
    recipient_placeholder: str = "owner"

    # Artifact references
    artifact_summaries: dict[str, str] = field(default_factory=dict)

    # State
    status: PitchStatus = PitchStatus.QUEUED
    created_at: float = field(default_factory=time.time)
    sent_at: Optional[float] = None
    error: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class PitchQueueStats:
    total: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    by_channel: dict[str, int] = field(default_factory=dict)


# ─── Pitch Generator ────────────────────────────────────

class PitchGenerator:
    """
    Generates outbound drafts from completed artifact suites.

    Template rendering uses {{placeholder}} pattern. Context includes:
    - All extracted fields from all artifacts in the suite
    - Classification dimensions from OpportunityProfile
    - Contact info from transcript
    - Artifact-level summaries (first 200 chars of each artifact body)
    """

    def generate_pitches(
        self,
        suite: ArtifactSuite,
        profile: OpportunityProfile,
        pitch_config: dict,
        transcript: SessionTranscript,
    ) -> list[Pitch]:
        """
        Generate all pitch drafts for a suite that just became pitch-ready.

        For each PitchSpec in the manifest:
        1. Check that required artifacts are READY in the suite
        2. Build template context from artifacts + profile + transcript
        3. Render template
        4. Create Pitch with QUEUED status (or DRAFT if auto_send=False)
        """
        if not pitch_config:
            return []

        specs_data = pitch_config.get("specs", [])
        if not specs_data:
            return []

        context = self._build_context(suite, profile, transcript)
        pitches: list[Pitch] = []

        for spec_data in specs_data:
            spec = PitchSpec.from_dict(spec_data)

            # Check required artifacts are READY
            if not self._requirements_met(suite, spec):
                logger.debug(f"Pitch spec {spec.id}: requirements not met, skipping")
                continue

            # Render template
            body = self._render_template(spec.template, context)
            subject = self._render_template(spec.subject_template, context) if spec.subject_template else ""

            # Build artifact summaries
            artifact_summaries = {}
            for art_spec_id, artifact in suite.artifacts.items():
                if artifact.current_version and artifact.current_version.body:
                    summary = artifact.current_version.body[:200]
                    if len(artifact.current_version.body) > 200:
                        summary += "..."
                    artifact_summaries[art_spec_id] = summary

            pitch = Pitch(
                suite_id=suite.suite_id,
                session_id=suite.session_id,
                pack_id=suite.pack_id,
                spec_id=spec.id,
                spec_name=spec.name,
                channel=spec.channel,
                subject=subject,
                body=body,
                artifact_summaries=artifact_summaries,
                status=PitchStatus.QUEUED if spec.auto_send else PitchStatus.DRAFT,
            )
            pitches.append(pitch)

            logger.info(
                f"Pitch generated: spec={spec.id} channel={spec.channel} "
                f"suite={suite.suite_id}"
            )

        return pitches

    def _build_context(
        self,
        suite: ArtifactSuite,
        profile: OpportunityProfile,
        transcript: SessionTranscript,
    ) -> dict:
        """
        Build the variable context for template rendering.

        Context keys:
        - contact_name, contact_email, contact_phone
        - date
        - classification.{dimension_id}
        - composite_score
        - summary
        - artifact.{spec_id}.title, .summary, .completeness
        - All extracted fields merged from artifact versions
        """
        context = {}

        # Contact info
        ci = transcript.contact_info or {}
        context["contact_name"] = ci.get("name", "")
        context["contact_email"] = ci.get("email", "")
        context["contact_phone"] = ci.get("phone", "")

        # Date
        context["date"] = datetime.now(timezone.utc).strftime("%B %d, %Y")

        # Classification dimensions
        for dim_id, level in profile.dimensions.items():
            context[f"classification.{dim_id}"] = level

        # Composite score
        context["composite_score"] = str(round(profile.composite_score, 2))

        # Summary
        context["summary"] = profile.summary or transcript.summary or ""

        # Artifact data
        for spec_id, artifact in suite.artifacts.items():
            if artifact.current_version:
                body = artifact.current_version.body
                summary = body[:200] + ("..." if len(body) > 200 else "")
                context[f"artifact.{spec_id}.summary"] = summary
                context[f"artifact.{spec_id}.completeness"] = str(
                    round(artifact.current_version.completeness, 2)
                )
                context[f"artifact.{spec_id}.title"] = artifact.spec_name

                # Merge extracted fields into context
                for fid, fval in artifact.current_version.extracted_fields.items():
                    if fid not in context:
                        context[fid] = fval

        return context

    def _requirements_met(self, suite: ArtifactSuite, spec: PitchSpec) -> bool:
        """Check that all required artifacts are READY in the suite."""
        for req_id in spec.requires_artifacts:
            artifact = suite.artifacts.get(req_id)
            if not artifact or artifact.status != ArtifactStatus.READY:
                return False
        return True

    def _render_template(self, template: str, context: dict) -> str:
        """Replace {{key}} placeholders with values from context."""
        if not template:
            return ""

        def replacer(match):
            key = match.group(1)
            return context.get(key, f"[{key}]")

        return re.sub(r"\{\{(\S+?)\}\}", replacer, template)


# ─── Pitch Store ─────────────────────────────────────────

class PitchStore:
    """In-memory store for pitch drafts."""

    def __init__(self):
        self._pitches: dict[str, Pitch] = {}
        logger.info("PitchStore initialized")

    def add(self, pitch: Pitch) -> Pitch:
        self._pitches[pitch.pitch_id] = pitch
        return pitch

    def get(self, pitch_id: str) -> Optional[Pitch]:
        return self._pitches.get(pitch_id)

    def list_pitches(
        self,
        suite_id: Optional[str] = None,
        status: Optional[str] = None,
        channel: Optional[str] = None,
        limit: int = 50,
    ) -> list[Pitch]:
        results = list(self._pitches.values())
        if suite_id:
            results = [p for p in results if p.suite_id == suite_id]
        if status:
            results = [p for p in results if p.status.value == status]
        if channel:
            results = [p for p in results if p.channel == channel]
        results.sort(key=lambda p: p.created_at, reverse=True)
        return results[:limit]

    def update_status(
        self,
        pitch_id: str,
        status: str,
        error: str = "",
    ) -> Optional[Pitch]:
        pitch = self._pitches.get(pitch_id)
        if not pitch:
            return None
        try:
            pitch.status = PitchStatus(status)
        except ValueError:
            return None
        if error:
            pitch.error = error
        if status == "sent":
            pitch.sent_at = time.time()
        return pitch

    def get_stats(self) -> PitchQueueStats:
        stats = PitchQueueStats(total=len(self._pitches))
        for p in self._pitches.values():
            s = p.status.value
            stats.by_status[s] = stats.by_status.get(s, 0) + 1
            stats.by_channel[p.channel] = stats.by_channel.get(p.channel, 0) + 1
        return stats
