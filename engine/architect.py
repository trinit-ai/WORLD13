"""
TMOS13 Architect Orchestrator

Manages artifact suites — collections of versioned documents that build
progressively as data accumulates from session transcripts. Orchestrates
the deliverable pipeline per artifact spec, tracks versions, dependencies,
and suite completeness.

Pipeline:
    OpportunityProfile + Transcript → ArtifactSuite → versioned Artifacts → pitch readiness

Uses DeliverableExtractor and DeliverableGenerator from deliverables.py —
does NOT duplicate extraction or generation logic. The Architect adds
orchestration (versioning, dependencies, suite management) on top.

Usage:
    architect = ArchitectOrchestrator(
        extractor=DeliverableExtractor(),
        generator=DeliverableGenerator(),
    )
    suite = architect.create_suite(session_id, pack_manifest)
    result = architect.evaluate(suite.suite_id, transcript, pack_manifest)
"""
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional

from deliverables import DeliverableExtractor, DeliverableGenerator, DeliverableSpec
from transcripts import SessionTranscript

logger = logging.getLogger("tmos13.architect")


# ─── Data Models ─────────────────────────────────────────

class ArtifactStatus(str, Enum):
    PENDING = "pending"
    DRAFT = "draft"
    READY = "ready"
    DELIVERED = "delivered"


@dataclass
class ArtifactSpec:
    """
    Specification for one artifact type in a suite.
    Loaded from pack manifest under architect.artifacts[].
    """
    id: str = ""
    name: str = ""
    deliverable_spec_id: str = ""
    trigger_completeness: float = 0.0
    depends_on: list[str] = field(default_factory=list)
    required_for_pitch: bool = False

    @staticmethod
    def from_dict(d: dict) -> "ArtifactSpec":
        return ArtifactSpec(
            id=d.get("id", ""),
            name=d.get("name", ""),
            deliverable_spec_id=d.get("deliverable_spec_id", ""),
            trigger_completeness=d.get("trigger_completeness", 0.0),
            depends_on=d.get("depends_on", []),
            required_for_pitch=d.get("required_for_pitch", False),
        )


@dataclass
class ArtifactVersion:
    """A single version of a generated artifact."""
    version: str = "0.1"
    body: str = ""
    sections: list[dict] = field(default_factory=list)
    completeness: float = 0.0
    extracted_fields: dict = field(default_factory=dict)
    generated_at: float = field(default_factory=time.time)


@dataclass
class Artifact:
    """A single artifact within a suite, with version history."""
    artifact_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    spec_id: str = ""
    spec_name: str = ""
    suite_id: str = ""
    status: ArtifactStatus = ArtifactStatus.PENDING
    current_version: Optional[ArtifactVersion] = None
    version_history: list[ArtifactVersion] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        d = {
            "artifact_id": self.artifact_id,
            "spec_id": self.spec_id,
            "spec_name": self.spec_name,
            "suite_id": self.suite_id,
            "status": self.status.value,
            "version_count": self.version_count,
            "latest_version_number": self.latest_version_number,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.current_version:
            d["current_version"] = {
                "version": self.current_version.version,
                "completeness": self.current_version.completeness,
                "generated_at": self.current_version.generated_at,
                "body": self.current_version.body,
                "sections": self.current_version.sections,
            }
        d["version_history"] = [
            {
                "version": v.version,
                "completeness": v.completeness,
                "generated_at": v.generated_at,
            }
            for v in self.version_history
        ]
        return d

    @property
    def version_count(self) -> int:
        return len(self.version_history)

    @property
    def latest_version_number(self) -> str:
        if not self.version_history:
            return "0.0"
        return self.version_history[-1].version


@dataclass
class ArtifactSuite:
    """
    A collection of artifacts for a single exchange/session.
    Tracks overall completeness and pitch readiness.
    """
    suite_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    session_id: str = ""
    exchange_id: str = ""
    pack_id: str = ""
    profile_id: str = ""

    artifacts: dict[str, Artifact] = field(default_factory=dict)  # spec_id → Artifact

    # Suite-level state
    pitch_threshold: float = 0.7
    pitch_triggered: bool = False
    pitch_triggered_at: Optional[float] = None

    # Spec metadata (needed for dependency checks)
    _artifact_specs: dict[str, ArtifactSpec] = field(default_factory=dict)

    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "suite_id": self.suite_id,
            "session_id": self.session_id,
            "exchange_id": self.exchange_id,
            "pack_id": self.pack_id,
            "profile_id": self.profile_id,
            "completeness": self.completeness,
            "pitch_threshold": self.pitch_threshold,
            "pitch_triggered": self.pitch_triggered,
            "pitch_triggered_at": self.pitch_triggered_at,
            "is_pitch_ready": self.is_pitch_ready,
            "artifacts": {
                sid: a.to_dict() for sid, a in self.artifacts.items()
            },
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @property
    def completeness(self) -> float:
        """
        Suite completeness: fraction of required-for-pitch artifacts that are READY.
        If no artifacts are required_for_pitch, use all artifacts.
        """
        if not self.artifacts:
            return 0.0

        required = [
            a for sid, a in self.artifacts.items()
            if self._artifact_specs.get(sid, ArtifactSpec()).required_for_pitch
        ]

        if not required:
            # No required artifacts — use all
            target = list(self.artifacts.values())
        else:
            target = required

        if not target:
            return 0.0

        ready_count = sum(1 for a in target if a.status == ArtifactStatus.READY)
        return round(ready_count / len(target), 4)

    @property
    def is_pitch_ready(self) -> bool:
        """True when all required_for_pitch artifacts are READY and completeness >= threshold."""
        required = [
            a for sid, a in self.artifacts.items()
            if self._artifact_specs.get(sid, ArtifactSpec()).required_for_pitch
        ]

        if required:
            all_ready = all(a.status == ArtifactStatus.READY for a in required)
        else:
            all_ready = all(a.status == ArtifactStatus.READY for a in self.artifacts.values())

        return all_ready and self.completeness >= self.pitch_threshold

    @property
    def pending_artifacts(self) -> list[Artifact]:
        return [a for a in self.artifacts.values() if a.status == ArtifactStatus.PENDING]

    @property
    def ready_artifacts(self) -> list[Artifact]:
        return [a for a in self.artifacts.values() if a.status == ArtifactStatus.READY]


# ─── Architect Orchestrator ──────────────────────────────

class ArchitectOrchestrator:
    """
    Manages artifact suites. On each evaluation:
    1. Runs extraction via DeliverableExtractor
    2. Checks which artifacts can be generated/updated
    3. Generates new versions for eligible artifacts
    4. Evaluates suite completeness
    5. Returns pitch readiness signal
    """

    def __init__(
        self,
        extractor: DeliverableExtractor,
        generator: DeliverableGenerator,
        store: Optional["ArtifactSuiteStore"] = None,
    ):
        self.extractor = extractor
        self.generator = generator
        self.store = store or ArtifactSuiteStore()

    def create_suite(
        self,
        session_id: str,
        pack_manifest: dict,
        exchange_id: str = "",
        profile_id: str = "",
    ) -> ArtifactSuite:
        """
        Initialize an artifact suite from pack manifest config.
        Creates Artifact shells (PENDING status) for each spec.
        """
        architect_config = pack_manifest.get("architect", {})

        suite = ArtifactSuite(
            session_id=session_id,
            exchange_id=exchange_id,
            pack_id=pack_manifest.get("id", ""),
            profile_id=profile_id,
            pitch_threshold=architect_config.get("pitch_threshold", 0.7),
        )

        # Load artifact specs
        artifacts_data = architect_config.get("artifacts", [])
        for spec_data in artifacts_data:
            spec = ArtifactSpec.from_dict(spec_data)
            suite._artifact_specs[spec.id] = spec

            artifact = Artifact(
                spec_id=spec.id,
                spec_name=spec.name,
                suite_id=suite.suite_id,
            )
            suite.artifacts[spec.id] = artifact

        self.store.add(suite)
        logger.info(
            f"Suite created: id={suite.suite_id} session={session_id} "
            f"artifacts={len(suite.artifacts)}"
        )
        return suite

    def evaluate(
        self,
        suite_id: str,
        transcript: SessionTranscript,
        pack_manifest: dict,
    ) -> dict:
        """
        Run one evaluation pass on a suite.

        Returns:
        {
            "suite_id": str,
            "artifacts_updated": [spec_id, ...],
            "suite_completeness": float,
            "pitch_ready": bool,
            "pitch_newly_triggered": bool,
        }
        """
        suite = self.store.get(suite_id)
        if not suite:
            logger.warning(f"Suite not found: {suite_id}")
            return {
                "suite_id": suite_id,
                "artifacts_updated": [],
                "suite_completeness": 0.0,
                "pitch_ready": False,
                "pitch_newly_triggered": False,
            }

        # Load deliverable specs from manifest for extraction
        deliverables_config = pack_manifest.get("deliverables", {})
        deliverable_specs_data = deliverables_config.get("types", [])
        deliverable_specs = {
            s.get("id", ""): DeliverableSpec.from_dict(s)
            for s in deliverable_specs_data
        }

        artifacts_updated = []
        was_pitch_ready = suite.pitch_triggered

        for spec_id, artifact in suite.artifacts.items():
            art_spec = suite._artifact_specs.get(spec_id)
            if not art_spec:
                continue

            # Check dependencies
            if not self._dependencies_met(suite, art_spec):
                continue

            # Find the deliverable spec for extraction
            del_spec = deliverable_specs.get(art_spec.deliverable_spec_id)
            if not del_spec:
                logger.debug(
                    f"No deliverable spec '{art_spec.deliverable_spec_id}' "
                    f"for artifact {spec_id}"
                )
                continue

            # Run extraction
            data = self.extractor.extract(transcript, del_spec)

            # Check completeness threshold
            if data.completeness < art_spec.trigger_completeness:
                continue

            # Check if completeness improved over last version
            last_completeness = (
                artifact.current_version.completeness
                if artifact.current_version
                else -1.0
            )
            if data.completeness <= last_completeness:
                continue  # no improvement, skip generation

            # Generate new version
            deliverable = self.generator.generate(del_spec, data, transcript)

            # Compute version number
            version_num = self._next_version(artifact, data)

            version = ArtifactVersion(
                version=version_num,
                body=deliverable.body,
                sections=deliverable.sections,
                completeness=data.completeness,
                extracted_fields=dict(data.fields),
            )

            artifact.version_history.append(version)
            artifact.current_version = version
            artifact.updated_at = time.time()

            # Update status based on eligibility
            if data.is_eligible:
                artifact.status = ArtifactStatus.READY
            elif data.extraction_count > 0:
                artifact.status = ArtifactStatus.DRAFT
            # else stays PENDING

            artifacts_updated.append(spec_id)
            logger.info(
                f"Artifact updated: {spec_id} v{version_num} "
                f"status={artifact.status.value} "
                f"completeness={data.completeness:.0%}"
            )

        suite.updated_at = time.time()

        # Check pitch readiness
        pitch_newly_triggered = False
        if suite.is_pitch_ready and not was_pitch_ready:
            suite.pitch_triggered = True
            suite.pitch_triggered_at = time.time()
            pitch_newly_triggered = True
            logger.info(f"Suite {suite_id}: pitch triggered!")

        return {
            "suite_id": suite_id,
            "artifacts_updated": artifacts_updated,
            "suite_completeness": suite.completeness,
            "pitch_ready": suite.is_pitch_ready,
            "pitch_newly_triggered": pitch_newly_triggered,
        }

    def get_suite(self, suite_id: str) -> Optional[ArtifactSuite]:
        return self.store.get(suite_id)

    def get_suite_by_session(self, session_id: str) -> Optional[ArtifactSuite]:
        return self.store.get_by_session(session_id)

    def _dependencies_met(self, suite: ArtifactSuite, spec: ArtifactSpec) -> bool:
        """Check if all dependency artifacts are READY."""
        for dep_id in spec.depends_on:
            dep_artifact = suite.artifacts.get(dep_id)
            if not dep_artifact or dep_artifact.status != ArtifactStatus.READY:
                return False
        return True

    def _next_version(self, artifact: Artifact, data) -> str:
        """Compute next version number."""
        if not artifact.version_history:
            # First version
            if data.is_eligible:
                return "1.0"
            return "0.1"

        if data.is_eligible:
            return "1.0"

        # Increment minor version
        last = artifact.version_history[-1].version
        try:
            parts = last.split(".")
            major = int(parts[0])
            minor = int(parts[1])
            return f"{major}.{minor + 1}"
        except (ValueError, IndexError):
            return f"0.{len(artifact.version_history) + 1}"


# ─── Artifact Suite Store ────────────────────────────────

class ArtifactSuiteStore:
    """In-memory store for artifact suites."""

    def __init__(self):
        self._suites: dict[str, ArtifactSuite] = {}
        self._session_index: dict[str, str] = {}  # session_id → suite_id
        logger.info("ArtifactSuiteStore initialized")

    def add(self, suite: ArtifactSuite) -> ArtifactSuite:
        self._suites[suite.suite_id] = suite
        if suite.session_id:
            self._session_index[suite.session_id] = suite.suite_id
        return suite

    def get(self, suite_id: str) -> Optional[ArtifactSuite]:
        return self._suites.get(suite_id)

    def get_by_session(self, session_id: str) -> Optional[ArtifactSuite]:
        sid = self._session_index.get(session_id)
        if sid:
            return self._suites.get(sid)
        return None

    def list_suites(
        self,
        pack_id: Optional[str] = None,
        pitch_ready: Optional[bool] = None,
        limit: int = 50,
    ) -> list[ArtifactSuite]:
        results = list(self._suites.values())
        if pack_id:
            results = [s for s in results if s.pack_id == pack_id]
        if pitch_ready is not None:
            results = [s for s in results if s.is_pitch_ready == pitch_ready]
        results.sort(key=lambda s: s.created_at, reverse=True)
        return results[:limit]

    def get_stats(self) -> dict:
        total = len(self._suites)
        pitch_triggered = sum(1 for s in self._suites.values() if s.pitch_triggered)
        total_artifacts = sum(len(s.artifacts) for s in self._suites.values())
        ready_artifacts = sum(
            sum(1 for a in s.artifacts.values() if a.status == ArtifactStatus.READY)
            for s in self._suites.values()
        )
        return {
            "total_suites": total,
            "pitch_triggered": pitch_triggered,
            "total_artifacts": total_artifacts,
            "ready_artifacts": ready_artifacts,
        }
