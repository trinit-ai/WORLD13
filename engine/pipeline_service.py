"""
TMOS13 Pack Pipeline Service — Fibonacci Plume Node 5

Declarative pack chaining: when Pack A completes and produces a deliverable,
that output becomes input context for Pack B. Pipelines are defined in pack
manifests (pipeline section) and discovered at init time.

Node 5's parents: Multi-Pack Session (Node 1, reactive) and Deliverable
(production). Node 5 is the declarative, configuration-time counterpart.

Follows delivery_service.py singleton pattern.
"""
import json
import logging
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException

logger = logging.getLogger("tmos13.pipeline")

# ─── Config ──────────────────────────────────────────────────

PIPELINE_ENABLED = os.environ.get("PIPELINE_ENABLED", "true").lower() in ("true", "1", "yes")
PIPELINE_MAX_STAGES = int(os.environ.get("PIPELINE_MAX_STAGES", "10"))


# ─── Data Models ─────────────────────────────────────────────

@dataclass
class PipelineStage:
    """A single stage in a pipeline, parsed from a pack manifest."""
    pack_id: str
    stage: int
    pipeline_id: str
    next_pack: str = ""                 # "" = terminal stage
    carry_fields: list[str] = field(default_factory=list)
    carry_deliverable: bool = False
    auto_advance: bool = False
    advance_condition: str = "deliverable_complete"  # deliverable_complete | human_approval | field_threshold

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PipelineInstance:
    """A running instance of a declared pipeline."""
    id: str = ""
    pipeline_id: str = ""
    owner_id: str = ""
    status: str = "active"              # active | waiting_approval | completed | failed | cancelled
    current_stage: int = 1
    current_pack_id: str = ""
    total_stages: int = 1
    stages_completed: list[dict] = field(default_factory=list)   # [{pack_id, stage, deliverable_id, completed_at}]
    carried_context: dict = field(default_factory=dict)           # accumulated carry-forward fields
    deliverable_ids: list[str] = field(default_factory=list)
    cancellation_reason: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "pipeline_id": self.pipeline_id,
            "owner_id": self.owner_id,
            "status": self.status,
            "current_stage": self.current_stage,
            "current_pack_id": self.current_pack_id,
            "total_stages": self.total_stages,
            "stages_completed": self.stages_completed,
            "carried_context": self.carried_context,
            "deliverable_ids": self.deliverable_ids,
            "cancellation_reason": self.cancellation_reason,
        }
        for ts_field in ("created_at", "updated_at", "completed_at"):
            val = getattr(self, ts_field)
            d[ts_field] = val.isoformat() if val else None
        return d


# ─── Pipeline Service ────────────────────────────────────────

class PipelineService:
    """
    Manages pipeline lifecycle: discovery, start, advance, approve, cancel.

    Pipelines are defined across pack manifests (each pack declares its stage).
    Discovery scans all packs and groups stages by pipeline_id.
    """

    def __init__(self, db=None, orchestrator=None):
        self._db = db
        self._orchestrator = orchestrator

        # Cached catalog: {pipeline_id: [PipelineStage, ...]} sorted by stage
        self._stage_catalog: dict[str, list[PipelineStage]] = {}

        if PIPELINE_ENABLED:
            self._stage_catalog = self.discover_pipelines()
            logger.info(
                "Pipeline service initialized: %d pipelines discovered",
                len(self._stage_catalog),
            )
        else:
            logger.info("Pipeline service disabled (PIPELINE_ENABLED=false)")

    # ─── Discovery ─────────────────────────────────────────

    def discover_pipelines(self) -> dict[str, list[PipelineStage]]:
        """Scan all pack manifests and group pipeline stages by pipeline_id."""
        from config import get_pack_ids, get_pack

        catalog: dict[str, list[PipelineStage]] = {}

        for pack_id in get_pack_ids():
            try:
                pack = get_pack(pack_id)
                pipeline_cfg = pack.pipeline_config if hasattr(pack, "pipeline_config") else {}
                if not pipeline_cfg or not pipeline_cfg.get("enabled"):
                    continue

                stage = PipelineStage(
                    pack_id=pack_id,
                    stage=pipeline_cfg.get("stage", 1),
                    pipeline_id=pipeline_cfg.get("pipeline_id", ""),
                    next_pack=pipeline_cfg.get("next_pack", ""),
                    carry_fields=pipeline_cfg.get("carry_fields", []),
                    carry_deliverable=pipeline_cfg.get("carry_deliverable", False),
                    auto_advance=pipeline_cfg.get("auto_advance", False),
                    advance_condition=pipeline_cfg.get("advance_condition", "deliverable_complete"),
                )

                if stage.pipeline_id:
                    catalog.setdefault(stage.pipeline_id, []).append(stage)
            except Exception:
                logger.warning("Failed to read pipeline config for pack %s", pack_id)

        # Sort each pipeline's stages by stage number
        for pid in catalog:
            catalog[pid].sort(key=lambda s: s.stage)

        return catalog

    def get_pipeline_stages(self, pipeline_id: str) -> list[PipelineStage]:
        """Return cached stages for a pipeline."""
        return self._stage_catalog.get(pipeline_id, [])

    def get_pipeline_config(self, pack_id: str) -> Optional[PipelineStage]:
        """Get the pipeline stage config for a specific pack, or None."""
        for stages in self._stage_catalog.values():
            for stage in stages:
                if stage.pack_id == pack_id:
                    return stage
        return None

    # ─── Lifecycle ─────────────────────────────────────────

    async def start_pipeline(
        self,
        pipeline_id: str,
        owner_id: str,
        initial_context: Optional[dict] = None,
    ) -> PipelineInstance:
        """Start a new pipeline instance at stage 1."""
        if not PIPELINE_ENABLED:
            raise HTTPException(503, "Pipeline service disabled")

        stages = self.get_pipeline_stages(pipeline_id)
        if not stages:
            raise HTTPException(404, f"Pipeline '{pipeline_id}' not found")

        if len(stages) > PIPELINE_MAX_STAGES:
            raise HTTPException(400, f"Pipeline exceeds max stages ({PIPELINE_MAX_STAGES})")

        # Prevent duplicate active instances
        existing = await self.find_active_instance(owner_id, pipeline_id)
        if existing:
            raise HTTPException(
                409,
                f"Active pipeline '{pipeline_id}' already exists: {existing.id}",
            )

        first_stage = stages[0]
        now = datetime.now(timezone.utc)

        instance = PipelineInstance(
            id=str(uuid.uuid4()),
            pipeline_id=pipeline_id,
            owner_id=owner_id,
            status="active",
            current_stage=first_stage.stage,
            current_pack_id=first_stage.pack_id,
            total_stages=len(stages),
            stages_completed=[],
            carried_context=initial_context or {},
            deliverable_ids=[],
            created_at=now,
            updated_at=now,
        )

        await self._persist_instance(instance)
        logger.info("Pipeline started: %s (%s) for user %s", instance.id, pipeline_id, owner_id)
        return instance

    async def advance_pipeline(
        self,
        instance_id: str,
        deliverable_id: Optional[str] = None,
    ) -> PipelineInstance:
        """Advance pipeline after current stage completes."""
        if not PIPELINE_ENABLED:
            return PipelineInstance()

        instance = await self._load_instance(instance_id)
        if not instance:
            raise HTTPException(404, f"Pipeline instance '{instance_id}' not found")

        if instance.status not in ("active",):
            raise HTTPException(400, f"Cannot advance pipeline in status '{instance.status}'")

        # Find current stage config
        stages = self.get_pipeline_stages(instance.pipeline_id)
        current_stage_cfg = None
        next_stage_cfg = None

        for i, s in enumerate(stages):
            if s.stage == instance.current_stage:
                current_stage_cfg = s
                if i + 1 < len(stages):
                    next_stage_cfg = stages[i + 1]
                break

        if not current_stage_cfg:
            instance.status = "failed"
            instance.cancellation_reason = "Current stage config not found"
            instance.updated_at = datetime.now(timezone.utc)
            await self._persist_instance(instance)
            return instance

        # Record stage completion
        now = datetime.now(timezone.utc)
        instance.stages_completed.append({
            "pack_id": current_stage_cfg.pack_id,
            "stage": current_stage_cfg.stage,
            "deliverable_id": deliverable_id or "",
            "completed_at": now.isoformat(),
        })

        if deliverable_id and deliverable_id not in instance.deliverable_ids:
            instance.deliverable_ids.append(deliverable_id)

        # Carry forward fields from deliverable/session
        if current_stage_cfg.carry_fields:
            carried = await self._extract_carry_fields(
                deliverable_id, current_stage_cfg.carry_fields
            )
            instance.carried_context.update(carried)

        # Terminal stage?
        if not next_stage_cfg or current_stage_cfg.next_pack == "":
            instance.status = "completed"
            instance.completed_at = now
            instance.updated_at = now
            await self._persist_instance(instance)
            logger.info("Pipeline completed: %s", instance.id)
            return instance

        # Advance to next stage
        if current_stage_cfg.auto_advance:
            instance.status = "active"
        else:
            instance.status = "waiting_approval"

        instance.current_stage = next_stage_cfg.stage
        instance.current_pack_id = next_stage_cfg.pack_id
        instance.updated_at = now
        await self._persist_instance(instance)

        logger.info(
            "Pipeline %s advanced to stage %d (%s), status=%s",
            instance.id, next_stage_cfg.stage, next_stage_cfg.pack_id, instance.status,
        )
        return instance

    async def approve_advance(self, instance_id: str, approver_id: str) -> PipelineInstance:
        """Approve stage advancement for a pipeline waiting for approval."""
        instance = await self._load_instance(instance_id)
        if not instance:
            raise HTTPException(404, f"Pipeline instance '{instance_id}' not found")

        if instance.status != "waiting_approval":
            raise HTTPException(400, f"Pipeline is not waiting for approval (status={instance.status})")

        instance.status = "active"
        instance.updated_at = datetime.now(timezone.utc)
        await self._persist_instance(instance)
        logger.info("Pipeline %s approved by %s, now active at stage %d", instance.id, approver_id, instance.current_stage)
        return instance

    async def cancel_pipeline(self, instance_id: str, reason: str = "") -> PipelineInstance:
        """Cancel an active or waiting pipeline."""
        instance = await self._load_instance(instance_id)
        if not instance:
            raise HTTPException(404, f"Pipeline instance '{instance_id}' not found")

        if instance.status in ("completed", "failed", "cancelled"):
            raise HTTPException(400, f"Cannot cancel pipeline in status '{instance.status}'")

        instance.status = "cancelled"
        instance.cancellation_reason = reason
        now = datetime.now(timezone.utc)
        instance.updated_at = now
        instance.completed_at = now
        await self._persist_instance(instance)
        logger.info("Pipeline %s cancelled: %s", instance.id, reason)
        return instance

    # ─── Queries ───────────────────────────────────────────

    async def get_active_pipelines(self, owner_id: str) -> list[PipelineInstance]:
        """List active/waiting pipelines for a user."""
        if not self._db:
            return []
        try:
            result = (
                self._db.table("pipeline_instances")
                .select("*")
                .eq("owner_id", owner_id)
                .in_("status", ["active", "waiting_approval"])
                .order("created_at", desc=True)
                .execute()
            )
            return [self._row_to_instance(r) for r in (result.data or [])]
        except Exception:
            logger.exception("Failed to query active pipelines for user %s", owner_id)
            return []

    async def find_active_instance(
        self, owner_id: str, pipeline_id: str
    ) -> Optional[PipelineInstance]:
        """Find an active instance of a specific pipeline for a user."""
        if not self._db:
            return None
        try:
            result = (
                self._db.table("pipeline_instances")
                .select("*")
                .eq("owner_id", owner_id)
                .eq("pipeline_id", pipeline_id)
                .in_("status", ["active", "waiting_approval"])
                .limit(1)
                .execute()
            )
            rows = result.data or []
            return self._row_to_instance(rows[0]) if rows else None
        except Exception:
            logger.exception("Failed to find active pipeline %s for user %s", pipeline_id, owner_id)
            return None

    async def get_instance(self, instance_id: str) -> Optional[PipelineInstance]:
        """Get a pipeline instance by ID."""
        return await self._load_instance(instance_id)

    # ─── Context Formatting ────────────────────────────────

    def format_pipeline_context(self, instance: PipelineInstance) -> str:
        """Build the [PIPELINE CONTEXT] block for assembler injection."""
        stages = self.get_pipeline_stages(instance.pipeline_id)

        lines = [f"[PIPELINE CONTEXT — {instance.pipeline_id}]"]
        lines.append(
            f"Stage: {instance.current_stage} of {instance.total_stages} ({instance.current_pack_id})"
        )

        if instance.stages_completed:
            completed_names = []
            for sc in instance.stages_completed:
                completed_names.append(f"{sc['pack_id']} (stage {sc['stage']})")
            lines.append(f"Completed: {', '.join(completed_names)}")

        if instance.carried_context:
            lines.append("Carried information (do not re-collect):")
            for k, v in instance.carried_context.items():
                lines.append(f"  {k}: {v}")

        # Include prior deliverable summary if available
        if instance.stages_completed:
            last_completed = instance.stages_completed[-1]
            del_id = last_completed.get("deliverable_id", "")
            pack_id = last_completed.get("pack_id", "")
            if del_id:
                # Find deliverable name from stage config
                del_name = self._get_deliverable_name(pack_id, del_id)
                if del_name:
                    lines.append(
                        f"Prior deliverable (stage {last_completed['stage']}): {del_name}"
                    )

        lines.append(
            "INSTRUCTION: This session is part of a pipeline. Use carried context."
        )
        lines.append(
            "Do not re-collect information already captured in prior stages."
        )
        lines.append(f"[/PIPELINE CONTEXT]")

        return "\n".join(lines)

    # ─── Persistence Helpers ───────────────────────────────

    async def _persist_instance(self, instance: PipelineInstance):
        """Persist pipeline instance to Supabase (best-effort)."""
        if not self._db:
            return
        try:
            data = {
                "id": instance.id,
                "pipeline_id": instance.pipeline_id,
                "owner_id": instance.owner_id,
                "status": instance.status,
                "current_stage": instance.current_stage,
                "current_pack_id": instance.current_pack_id,
                "total_stages": instance.total_stages,
                "stages_completed": json.dumps(instance.stages_completed),
                "carried_context": json.dumps(instance.carried_context),
                "deliverable_ids": instance.deliverable_ids,
                "cancellation_reason": instance.cancellation_reason or "",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            if instance.completed_at:
                data["completed_at"] = instance.completed_at.isoformat()

            self._db.table("pipeline_instances").upsert(data).execute()
        except Exception:
            logger.exception("Failed to persist pipeline instance %s", instance.id)

    async def _load_instance(self, instance_id: str) -> Optional[PipelineInstance]:
        """Load a pipeline instance from Supabase."""
        if not self._db:
            return None
        try:
            result = (
                self._db.table("pipeline_instances")
                .select("*")
                .eq("id", instance_id)
                .limit(1)
                .execute()
            )
            rows = result.data or []
            return self._row_to_instance(rows[0]) if rows else None
        except Exception:
            logger.exception("Failed to load pipeline instance %s", instance_id)
            return None

    def _row_to_instance(self, row: dict) -> PipelineInstance:
        """Convert a Supabase row to PipelineInstance."""
        stages_completed = row.get("stages_completed", [])
        if isinstance(stages_completed, str):
            stages_completed = json.loads(stages_completed)

        carried_context = row.get("carried_context", {})
        if isinstance(carried_context, str):
            carried_context = json.loads(carried_context)

        return PipelineInstance(
            id=str(row["id"]),
            pipeline_id=row.get("pipeline_id", ""),
            owner_id=str(row.get("owner_id", "")),
            status=row.get("status", "active"),
            current_stage=row.get("current_stage", 1),
            current_pack_id=row.get("current_pack_id", ""),
            total_stages=row.get("total_stages", 1),
            stages_completed=stages_completed,
            carried_context=carried_context,
            deliverable_ids=row.get("deliverable_ids", []),
            cancellation_reason=row.get("cancellation_reason", ""),
            created_at=_parse_ts(row.get("created_at")),
            updated_at=_parse_ts(row.get("updated_at")),
            completed_at=_parse_ts(row.get("completed_at")),
        )

    async def _extract_carry_fields(
        self, deliverable_id: Optional[str], carry_fields: list[str]
    ) -> dict:
        """Extract carry-forward fields from a deliverable or session state."""
        carried = {}
        if not deliverable_id or not self._db:
            return carried
        try:
            result = (
                self._db.table("deliverables")
                .select("metadata, state_snapshot")
                .eq("id", deliverable_id)
                .limit(1)
                .execute()
            )
            rows = result.data or []
            if not rows:
                return carried

            row = rows[0]
            # Check metadata first, then state_snapshot
            for source_key in ("metadata", "state_snapshot"):
                source = row.get(source_key, {})
                if isinstance(source, str):
                    source = json.loads(source)
                if not source:
                    continue
                for cf in carry_fields:
                    if cf not in carried and cf in source:
                        carried[cf] = source[cf]

                # Also check nested state sections (forms, contact, case, etc.)
                for section in source.values():
                    if isinstance(section, dict):
                        for cf in carry_fields:
                            if cf not in carried and cf in section:
                                carried[cf] = section[cf]
        except Exception:
            logger.warning("Failed to extract carry fields from deliverable %s", deliverable_id)

        return carried

    def _get_deliverable_name(self, pack_id: str, deliverable_id: str) -> str:
        """Try to get a human-readable deliverable name for context."""
        try:
            from config import get_pack
            pack = get_pack(pack_id)
            manifest = pack.manifest
            for dt in manifest.get("deliverables", {}).get("types", []):
                return dt.get("name", "")
        except Exception:
            pass
        return ""


# ─── Timestamp Parsing ───────────────────────────────────────

def _parse_ts(val) -> Optional[datetime]:
    """Parse an ISO timestamp string to datetime, or return None."""
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


# ─── Singleton ────────────────────────────────────────────────

_pipeline_service: Optional[PipelineService] = None


def init_pipeline_service(db=None, orchestrator=None) -> PipelineService:
    """Initialize the global pipeline service. Called during app lifespan."""
    global _pipeline_service
    _pipeline_service = PipelineService(db=db, orchestrator=orchestrator)
    return _pipeline_service


def get_pipeline_service() -> Optional[PipelineService]:
    """Get the global pipeline service instance."""
    return _pipeline_service
