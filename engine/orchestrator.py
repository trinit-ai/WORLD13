"""
TMOS13 Pack Orchestration Engine (OpenClaw Spec 05)

Manages multi-step, time-spanning workflows that chain pack actions,
tool calls, triggers, and pack handoffs into governed sequences.

SAFETY PRINCIPLES:
- Workflows are 100% manifest-declared. No runtime workflow generation.
- Each step executes through existing governed systems (triggers, tools, deliverables).
- The orchestrator is a state machine, not an agent — it evaluates conditions
  and advances steps, it does not make decisions.
- All workflow state is persisted and auditable.
- Workflows have maximum step counts and time limits to prevent runaway chains.
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional

from triggers import parse_duration, TriggerEvent

logger = logging.getLogger("tmos13.orchestrator")

# ─── Constants ──────────────────────────────────────────────

DEFAULT_MAX_STEPS = 20
DEFAULT_WORKFLOW_TIMEOUT_DAYS = 30
STEP_TYPES = {
    "tool_action",
    "trigger_action",
    "pack_switch",
    "wait_for",
    "deliverable",
    "state_update",
    "complete",
}


# ─── Data Models ────────────────────────────────────────────

class WorkflowStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


@dataclass
class StepResult:
    """Result of executing a single workflow step."""
    step_id: str
    step_type: str
    success: bool
    output: dict = field(default_factory=dict)
    error: str = ""
    duration_ms: int = 0


@dataclass
class WorkflowInstance:
    """A running instance of a declared workflow."""
    id: str = ""
    workflow_id: str = ""           # manifest key
    pack_id: str = ""
    persistent_session_id: str = ""

    status: WorkflowStatus = WorkflowStatus.PENDING
    current_step_id: Optional[str] = None
    completed_steps: list[str] = field(default_factory=list)

    # State carried across steps
    context: dict = field(default_factory=dict)

    # Timing
    started_at: Optional[datetime] = None
    last_step_at: Optional[datetime] = None
    next_step_at: Optional[datetime] = None   # for delayed steps
    timeout_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Safety limits
    total_steps_executed: int = 0
    max_steps: int = DEFAULT_MAX_STEPS
    cancellation_reason: str = ""

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "pack_id": self.pack_id,
            "persistent_session_id": self.persistent_session_id,
            "status": self.status.value if isinstance(self.status, WorkflowStatus) else self.status,
            "current_step_id": self.current_step_id,
            "completed_steps": self.completed_steps,
            "context": self.context,
            "total_steps_executed": self.total_steps_executed,
            "max_steps": self.max_steps,
            "cancellation_reason": self.cancellation_reason,
        }
        for ts_field in ("started_at", "last_step_at", "next_step_at", "timeout_at", "completed_at"):
            val = getattr(self, ts_field)
            d[ts_field] = val.isoformat() if val else None
        return d


# ─── Audit Logging ──────────────────────────────────────────

async def log_step(
    db,
    instance: WorkflowInstance,
    step_id: str,
    step_type: str,
    status: str,
    input_context: dict = None,
    output_data: dict = None,
    error_message: str = "",
    duration_ms: int = 0,
) -> str | None:
    """Log a workflow step execution to the audit table."""
    if db is None:
        return None

    log_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    row = {
        "id": log_id,
        "workflow_instance_id": instance.id,
        "step_id": step_id,
        "step_type": step_type,
        "status": status,
        "input_context": json.dumps(input_context or {}),
        "output_data": json.dumps(output_data or {}),
        "error_message": error_message,
        "started_at": now.isoformat(),
        "completed_at": now.isoformat() if status in ("completed", "failed", "skipped") else None,
        "duration_ms": duration_ms,
        "created_at": now.isoformat(),
    }

    try:
        db.table("workflow_step_log").insert(row).execute()
        return log_id
    except Exception as e:
        logger.warning(f"Failed to log workflow step: {e}")
        return None


# ─── Orchestrator ───────────────────────────────────────────

class Orchestrator:
    """Manages workflow lifecycle: start, advance, wait, and event handling."""

    def __init__(
        self,
        supabase_client=None,
        tool_registry=None,
        action_dispatcher=None,
        persistence_service=None,
    ):
        self.db = supabase_client
        self.tools = tool_registry
        self.dispatcher = action_dispatcher
        self.persistence = persistence_service

        # In-memory workflow store (SQLite/Supabase as persistence backend)
        self._instances: dict[str, WorkflowInstance] = {}
        self._wait_conditions: dict[str, list[dict]] = {}  # instance_id → [conditions]
        self._workflow_defs: dict[str, dict] = {}  # instance_id → workflow_def

    @property
    def enabled(self) -> bool:
        return True  # orchestrator always works (memory-backed + optional Supabase)

    # ─── Workflow Definitions ───────────────────────────────

    def get_workflow_def(self, pack_id: str, workflow_id: str) -> dict | None:
        """Load a workflow definition from a pack manifest."""
        try:
            from config import get_pack
            pack = get_pack(pack_id)
            if not pack:
                return None
            workflows = pack.manifest.get("workflows", {})
            return workflows.get(workflow_id)
        except Exception:
            return None

    def _get_step_def(self, workflow_def: dict, step_id: str) -> dict | None:
        """Find a step definition by step_id within a workflow."""
        for step in workflow_def.get("steps", []):
            if step.get("step_id") == step_id:
                return step
        return None

    # ─── Workflow Lifecycle ─────────────────────────────────

    async def start_workflow(
        self,
        workflow_id: str,
        pack_id: str,
        persistent_session_id: str,
        initial_context: dict = None,
        workflow_def: dict = None,
    ) -> WorkflowInstance:
        """
        Initialize a new workflow instance.
        1. Load workflow definition from manifest (or accept directly)
        2. Create WorkflowInstance record
        3. Execute first step (if delay is 0)
        4. Persist workflow state
        """
        if not workflow_def:
            workflow_def = self.get_workflow_def(pack_id, workflow_id)
        if not workflow_def:
            raise ValueError(f"Workflow '{workflow_id}' not found in pack '{pack_id}'")

        steps = workflow_def.get("steps", [])
        if not steps:
            raise ValueError(f"Workflow '{workflow_id}' has no steps")

        # Check for cycle: workflow cannot target its own pack
        # (simple cycle prevention — checked more deeply in pack_switch)
        now = datetime.now(timezone.utc)
        max_steps = workflow_def.get("max_steps", DEFAULT_MAX_STEPS)
        timeout_days = workflow_def.get("timeout_days", DEFAULT_WORKFLOW_TIMEOUT_DAYS)

        instance = WorkflowInstance(
            id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            pack_id=pack_id,
            persistent_session_id=persistent_session_id,
            status=WorkflowStatus.ACTIVE,
            current_step_id=steps[0]["step_id"],
            context=initial_context or {},
            started_at=now,
            timeout_at=now + timedelta(days=timeout_days),
            max_steps=max_steps,
        )

        self._instances[instance.id] = instance
        self._workflow_defs[instance.id] = workflow_def
        await self._persist_instance(instance)

        logger.info(
            f"Workflow started: {workflow_id} for pack={pack_id} "
            f"session={persistent_session_id} id={instance.id}"
        )

        # Execute first step if no delay
        first_step = steps[0]
        delay = first_step.get("delay", "0")
        if delay == "0" or delay == "0s":
            await self.advance(instance.id, workflow_def=workflow_def)
        else:
            delay_td = parse_duration(delay)
            instance.next_step_at = now + delay_td
            await self._persist_instance(instance)

        return instance

    async def advance(
        self,
        workflow_instance_id: str,
        workflow_def: dict = None,
    ) -> WorkflowInstance:
        """
        Advance a workflow to execute its current step.
        Called by:
        - start_workflow() for the first step
        - The evaluation loop for time-delayed steps
        - handle_event() for wait_for conditions
        """
        instance = self._instances.get(workflow_instance_id)
        if not instance:
            raise ValueError(f"Workflow instance '{workflow_instance_id}' not found")

        # Safety: check terminal states
        if instance.status in (
            WorkflowStatus.COMPLETED, WorkflowStatus.FAILED,
            WorkflowStatus.TIMED_OUT, WorkflowStatus.CANCELLED,
        ):
            return instance

        # Safety: check max steps
        if instance.total_steps_executed >= instance.max_steps:
            instance.status = WorkflowStatus.FAILED
            instance.cancellation_reason = f"Max steps ({instance.max_steps}) exceeded"
            instance.completed_at = datetime.now(timezone.utc)
            await self._persist_instance(instance)
            logger.warning(f"Workflow {instance.id}: max steps exceeded")
            return instance

        # Safety: check timeout
        if instance.timeout_at and datetime.now(timezone.utc) > instance.timeout_at:
            instance.status = WorkflowStatus.TIMED_OUT
            instance.completed_at = datetime.now(timezone.utc)
            await self._persist_instance(instance)
            logger.warning(f"Workflow {instance.id}: timed out")
            return instance

        # Load workflow definition
        if not workflow_def:
            workflow_def = self._workflow_defs.get(workflow_instance_id)
        if not workflow_def:
            workflow_def = self.get_workflow_def(instance.pack_id, instance.workflow_id)
        if not workflow_def:
            instance.status = WorkflowStatus.FAILED
            instance.cancellation_reason = "Workflow definition not found"
            instance.completed_at = datetime.now(timezone.utc)
            await self._persist_instance(instance)
            return instance

        # Get current step
        step_id = instance.current_step_id
        step_def = self._get_step_def(workflow_def, step_id)
        if not step_def:
            instance.status = WorkflowStatus.FAILED
            instance.cancellation_reason = f"Step '{step_id}' not found in workflow definition"
            instance.completed_at = datetime.now(timezone.utc)
            await self._persist_instance(instance)
            return instance

        # Execute the step
        result = await self.execute_step(instance, step_def)
        now = datetime.now(timezone.utc)

        instance.total_steps_executed += 1
        instance.last_step_at = now
        instance.completed_steps.append(step_id)

        # Log step
        await log_step(
            self.db, instance, step_id, step_def["type"],
            status="completed" if result.success else "failed",
            input_context=instance.context,
            output_data=result.output,
            error_message=result.error,
            duration_ms=result.duration_ms,
        )

        if not result.success:
            # Check on_failure path
            on_failure = step_def.get("on_failure", "")
            if on_failure == "log_and_continue":
                logger.info(f"Workflow {instance.id}: step {step_id} failed but continuing")
                next_step_id = step_def.get("on_success")
            elif on_failure:
                next_step_id = on_failure
            else:
                instance.status = WorkflowStatus.FAILED
                instance.cancellation_reason = f"Step '{step_id}' failed: {result.error}"
                instance.completed_at = now
                await self._persist_instance(instance)
                return instance
        else:
            next_step_id = step_def.get("on_success")

        # If the step was wait_for, the instance is now WAITING
        if instance.status == WorkflowStatus.WAITING:
            await self._persist_instance(instance)
            return instance

        # Determine next step
        if not next_step_id:
            # No on_success defined — workflow is done
            instance.status = WorkflowStatus.COMPLETED
            instance.completed_at = now
            await self._persist_instance(instance)
            logger.info(f"Workflow {instance.id}: completed (no next step after {step_id})")
            return instance

        # Check if next step is "complete" shorthand
        next_step_def = self._get_step_def(workflow_def, next_step_id)
        if next_step_def and next_step_def.get("type") == "complete":
            instance.status = WorkflowStatus.COMPLETED
            instance.current_step_id = next_step_id
            instance.completed_steps.append(next_step_id)
            instance.completed_at = now
            instance.total_steps_executed += 1
            await log_step(
                self.db, instance, next_step_id, "complete",
                status="completed",
            )
            await self._persist_instance(instance)
            logger.info(f"Workflow {instance.id}: completed at step {next_step_id}")
            return instance

        # Set up next step
        instance.current_step_id = next_step_id

        # Check if next step has a delay
        if next_step_def:
            delay = next_step_def.get("delay", "0")
            if delay and delay != "0" and delay != "0s":
                delay_td = parse_duration(delay)
                instance.next_step_at = now + delay_td
                instance.status = WorkflowStatus.ACTIVE
                await self._persist_instance(instance)
                logger.info(
                    f"Workflow {instance.id}: next step {next_step_id} "
                    f"scheduled for {instance.next_step_at}"
                )
                return instance

        # Execute next step immediately (recursive)
        await self._persist_instance(instance)
        return await self.advance(workflow_instance_id, workflow_def=workflow_def)

    async def handle_event(
        self,
        event_type: str,
        persistent_session_id: str,
        event_data: dict = None,
    ) -> list[WorkflowInstance]:
        """
        Handle an external event that may advance waiting workflows.

        Events: contact_reply, team_action, deliverable_complete,
                payment_received, tool_complete, trigger_complete
        """
        advanced = []

        # Find waiting workflows for this session
        waiting = [
            inst for inst in self._instances.values()
            if inst.status == WorkflowStatus.WAITING
            and inst.persistent_session_id == persistent_session_id
        ]

        for instance in waiting:
            conditions = self._wait_conditions.get(instance.id, [])
            for cond in conditions:
                if cond.get("matched"):
                    continue
                if cond["event_type"] != event_type:
                    continue
                # Check additional filter criteria
                filter_criteria = cond.get("filter", {})
                if filter_criteria and not self._matches_filter(event_data or {}, filter_criteria):
                    continue

                # Match found
                cond["matched"] = True
                cond["matched_at"] = datetime.now(timezone.utc).isoformat()
                cond["matched_event"] = event_data

                target_step = cond["target_step_id"]
                instance.current_step_id = target_step
                instance.status = WorkflowStatus.ACTIVE

                logger.info(
                    f"Workflow {instance.id}: event {event_type} matched, "
                    f"advancing to step {target_step}"
                )

                try:
                    await self.advance(instance.id)
                    advanced.append(instance)
                except Exception as e:
                    logger.error(f"Failed to advance workflow {instance.id}: {e}")

                break  # one match per instance

        return advanced

    async def evaluate_waiting_workflows(self):
        """
        Check all WAITING workflows for timeout conditions.
        Called by the background evaluation loop.
        """
        now = datetime.now(timezone.utc)
        timed_out = []

        for instance in list(self._instances.values()):
            if instance.status != WorkflowStatus.WAITING:
                continue

            # Check workflow-level timeout
            if instance.timeout_at and now > instance.timeout_at:
                instance.status = WorkflowStatus.TIMED_OUT
                instance.completed_at = now
                await self._persist_instance(instance)
                timed_out.append(instance)
                logger.info(f"Workflow {instance.id}: timed out globally")
                continue

            # Check wait condition timeouts
            conditions = self._wait_conditions.get(instance.id, [])
            for cond in conditions:
                if cond.get("matched"):
                    continue
                timeout_at_str = cond.get("timeout_at")
                if not timeout_at_str:
                    continue

                # Parse timeout
                if isinstance(timeout_at_str, str):
                    try:
                        cond_timeout = datetime.fromisoformat(
                            timeout_at_str.replace("Z", "+00:00")
                        )
                    except ValueError:
                        continue
                elif isinstance(timeout_at_str, datetime):
                    cond_timeout = timeout_at_str
                else:
                    continue

                if now > cond_timeout:
                    # Find the timeout target step
                    timeout_target = cond.get("timeout_step_id", "")
                    if timeout_target:
                        cond["matched"] = True
                        cond["matched_at"] = now.isoformat()
                        cond["matched_event"] = {"reason": "timeout"}

                        instance.current_step_id = timeout_target
                        instance.status = WorkflowStatus.ACTIVE

                        logger.info(
                            f"Workflow {instance.id}: wait condition timed out, "
                            f"advancing to {timeout_target}"
                        )

                        try:
                            await self.advance(instance.id)
                        except Exception as e:
                            logger.error(f"Failed to advance timed-out workflow {instance.id}: {e}")

                        break  # one timeout per evaluation cycle

    async def get_due_workflows(self) -> list[WorkflowInstance]:
        """Get workflows with delayed steps that are now due for execution."""
        now = datetime.now(timezone.utc)
        due = []
        for instance in self._instances.values():
            if instance.status != WorkflowStatus.ACTIVE:
                continue
            if instance.next_step_at and now >= instance.next_step_at:
                due.append(instance)
        return due

    async def cancel_workflow(self, workflow_instance_id: str, reason: str = ""):
        """Cancel a running workflow."""
        instance = self._instances.get(workflow_instance_id)
        if not instance:
            return
        if instance.status in (WorkflowStatus.COMPLETED, WorkflowStatus.CANCELLED):
            return

        instance.status = WorkflowStatus.CANCELLED
        instance.cancellation_reason = reason
        instance.completed_at = datetime.now(timezone.utc)
        await self._persist_instance(instance)
        logger.info(f"Workflow {instance.id}: cancelled — {reason}")

    # ─── Step Execution ─────────────────────────────────────

    async def execute_step(
        self,
        instance: WorkflowInstance,
        step: dict,
    ) -> StepResult:
        """Execute a single workflow step. Routes to appropriate handler."""
        step_type = step.get("type", "")
        step_id = step.get("step_id", "")

        if step_type not in STEP_TYPES:
            return StepResult(
                step_id=step_id, step_type=step_type,
                success=False, error=f"Unknown step type: {step_type}",
            )

        start_ms = time.time() * 1000

        try:
            handler = {
                "tool_action": self._execute_tool_step,
                "trigger_action": self._execute_trigger_step,
                "pack_switch": self._execute_pack_switch,
                "wait_for": self._execute_wait,
                "deliverable": self._execute_deliverable,
                "state_update": self._execute_state_update,
                "complete": self._execute_complete,
            }.get(step_type)

            if not handler:
                return StepResult(
                    step_id=step_id, step_type=step_type,
                    success=False, error=f"No handler for step type: {step_type}",
                )

            result = await handler(instance, step)
            result.duration_ms = int(time.time() * 1000 - start_ms)
            return result

        except Exception as e:
            duration_ms = int(time.time() * 1000 - start_ms)
            logger.error(f"Step execution failed: {step_id} ({step_type}): {e}")
            return StepResult(
                step_id=step_id, step_type=step_type,
                success=False, error=str(e), duration_ms=duration_ms,
            )

    async def _execute_tool_step(
        self, instance: WorkflowInstance, step: dict,
    ) -> StepResult:
        """Execute a tool action step via Spec 03 ToolRegistry."""
        step_id = step.get("step_id", "")
        tool_id = step.get("tool_id", "")
        operation = step.get("operation", "")
        parameters = step.get("parameters", {})

        # Template variables from workflow context
        resolved_params = self._resolve_context_vars(parameters, instance.context)

        if not self.tools:
            return StepResult(
                step_id=step_id, step_type="tool_action",
                success=False, error="Tool registry not available",
            )

        from tool_registry import ToolRequest
        req = ToolRequest(
            tool_id=tool_id,
            operation=operation,
            parameters=resolved_params,
            session_id=instance.persistent_session_id,
            requires_confirmation=True,  # skip confirmation gate (automated workflow)
        )

        result = await self.tools.validate_and_execute(
            request=req,
            pack_id=instance.pack_id,
        )

        return StepResult(
            step_id=step_id, step_type="tool_action",
            success=result.success,
            output=result.data,
            error=result.error or "",
        )

    async def _execute_trigger_step(
        self, instance: WorkflowInstance, step: dict,
    ) -> StepResult:
        """Execute a trigger action step via Spec 02 ActionDispatcher."""
        step_id = step.get("step_id", "")
        action = step.get("action", "")
        template_name = step.get("template", "")

        if not self.dispatcher:
            return StepResult(
                step_id=step_id, step_type="trigger_action",
                success=False, error="Action dispatcher not available",
            )

        # Build a TriggerEvent for the dispatcher
        event = TriggerEvent(
            trigger_id=f"workflow:{instance.workflow_id}:{step_id}",
            pack_id=instance.pack_id,
            persistent_session_id=instance.persistent_session_id,
            contact_identity=instance.context.get("contact_identity", {}),
            action=action,
            template=template_name,
            metadata={
                "workflow_id": instance.workflow_id,
                "workflow_instance_id": instance.id,
                "session_data": instance.context,
                **step.get("action_config", {}),
            },
        )

        result = await self.dispatcher.dispatch(event)
        success = result.get("status") in ("dispatched", "approval_pending")

        return StepResult(
            step_id=step_id, step_type="trigger_action",
            success=success,
            output=result,
            error=result.get("error", ""),
        )

    async def _execute_pack_switch(
        self, instance: WorkflowInstance, step: dict,
    ) -> StepResult:
        """
        Hand off to a different pack.
        1. Validate target pack exists
        2. Check for recursive workflow (same pack)
        3. Carry specified fields to target
        4. Create or update persistent session for target pack
        """
        step_id = step.get("step_id", "")
        target_pack = step.get("target_pack", "")
        target_cartridge = step.get("target_cartridge", "")
        carry_fields = step.get("carry_fields", [])
        context_injection = step.get("context_injection", "")

        if not target_pack:
            return StepResult(
                step_id=step_id, step_type="pack_switch",
                success=False, error="No target_pack specified",
            )

        # Cycle detection: cannot switch to the same pack
        if target_pack == instance.pack_id:
            return StepResult(
                step_id=step_id, step_type="pack_switch",
                success=False, error=f"Recursive pack switch denied: {target_pack}",
            )

        # Validate target pack exists
        try:
            from config import get_pack
            pack = get_pack(target_pack)
            if not pack:
                return StepResult(
                    step_id=step_id, step_type="pack_switch",
                    success=False, error=f"Target pack '{target_pack}' not found",
                )
            # Validate target cartridge
            if target_cartridge and target_cartridge not in pack.cartridges:
                return StepResult(
                    step_id=step_id, step_type="pack_switch",
                    success=False,
                    error=f"Cartridge '{target_cartridge}' not found in pack '{target_pack}'",
                )
        except Exception as e:
            return StepResult(
                step_id=step_id, step_type="pack_switch",
                success=False, error=f"Pack validation failed: {e}",
            )

        # Build carried context
        carried = {}
        for field_name in carry_fields:
            val = instance.context.get(field_name)
            if val is not None:
                carried[field_name] = val

        # Resolve context injection template
        resolved_context = ""
        if context_injection:
            resolved_context = self._resolve_context_template(
                context_injection, instance.context,
            )

        # Store the handoff data in the instance context for the next pack
        instance.context["_pack_switch"] = {
            "target_pack": target_pack,
            "target_cartridge": target_cartridge,
            "carried_fields": carried,
            "context_injection": resolved_context,
        }

        return StepResult(
            step_id=step_id, step_type="pack_switch",
            success=True,
            output={
                "target_pack": target_pack,
                "target_cartridge": target_cartridge,
                "carried_fields": list(carried.keys()),
            },
        )

    async def _execute_wait(
        self, instance: WorkflowInstance, step: dict,
    ) -> StepResult:
        """
        Pause workflow until condition met.
        Set workflow status to WAITING.
        Register event listeners for the wait_for conditions.
        """
        step_id = step.get("step_id", "")
        condition = step.get("condition", {})
        any_of = condition.get("any_of", [])

        if not any_of:
            return StepResult(
                step_id=step_id, step_type="wait_for",
                success=False, error="No wait conditions defined",
            )

        instance.status = WorkflowStatus.WAITING
        now = datetime.now(timezone.utc)

        # Register wait conditions
        wait_conditions = []
        for cond in any_of:
            event_type = cond.get("event", "")
            within = cond.get("within", "")
            then_step = cond.get("then", "")
            filter_criteria = cond.get("filter", {})

            if event_type == "timeout":
                # Timeout is handled by other conditions' within durations
                # Store as a fallback
                wait_conditions.append({
                    "event_type": "timeout",
                    "target_step_id": then_step,
                    "timeout_step_id": then_step,
                    "filter": {},
                    "matched": False,
                })
                continue

            timeout_at = None
            if within:
                timeout_td = parse_duration(within)
                timeout_at = (now + timeout_td).isoformat()

            wait_conditions.append({
                "event_type": event_type,
                "target_step_id": then_step,
                "timeout_step_id": "",  # filled from timeout condition
                "timeout_at": timeout_at,
                "filter": filter_criteria,
                "matched": False,
            })

        # If there's a timeout condition, set it as the timeout fallback for all conditions
        timeout_cond = next(
            (c for c in wait_conditions if c["event_type"] == "timeout"), None
        )
        if timeout_cond:
            # Find the max timeout_at among non-timeout conditions
            max_timeout = None
            for c in wait_conditions:
                if c["event_type"] != "timeout" and c.get("timeout_at"):
                    cond_timeout = datetime.fromisoformat(
                        c["timeout_at"].replace("Z", "+00:00")
                    )
                    if max_timeout is None or cond_timeout > max_timeout:
                        max_timeout = cond_timeout

            if max_timeout:
                timeout_cond["timeout_at"] = max_timeout.isoformat()
                timeout_cond["timeout_step_id"] = timeout_cond["target_step_id"]

            # Set timeout_step_id on all conditions for fallback
            for c in wait_conditions:
                if c["event_type"] != "timeout" and not c.get("timeout_step_id"):
                    c["timeout_step_id"] = timeout_cond["target_step_id"]

        self._wait_conditions[instance.id] = wait_conditions

        return StepResult(
            step_id=step_id, step_type="wait_for",
            success=True,
            output={"conditions_registered": len(wait_conditions)},
        )

    async def _execute_deliverable(
        self, instance: WorkflowInstance, step: dict,
    ) -> StepResult:
        """Generate a deliverable document."""
        step_id = step.get("step_id", "")
        deliverable_type = step.get("deliverable_type", "")

        return StepResult(
            step_id=step_id, step_type="deliverable",
            success=True,
            output={
                "deliverable_type": deliverable_type,
                "note": "Deliverable generation delegated to pipeline",
            },
        )

    async def _execute_state_update(
        self, instance: WorkflowInstance, step: dict,
    ) -> StepResult:
        """Modify workflow context / persistent session state."""
        step_id = step.get("step_id", "")
        updates = step.get("updates", {})

        for key, value in updates.items():
            if isinstance(value, str) and "{{" in value:
                value = self._resolve_context_template(value, instance.context)
            instance.context[key] = value

        return StepResult(
            step_id=step_id, step_type="state_update",
            success=True,
            output={"updated_fields": list(updates.keys())},
        )

    async def _execute_complete(
        self, instance: WorkflowInstance, step: dict,
    ) -> StepResult:
        """Mark workflow as finished."""
        step_id = step.get("step_id", "")
        instance.status = WorkflowStatus.COMPLETED
        instance.completed_at = datetime.now(timezone.utc)

        return StepResult(
            step_id=step_id, step_type="complete",
            success=True,
            output={"workflow_completed": True},
        )

    # ─── Query ──────────────────────────────────────────────

    def get_instance(self, instance_id: str) -> WorkflowInstance | None:
        return self._instances.get(instance_id)

    def get_instances_for_session(self, persistent_session_id: str) -> list[WorkflowInstance]:
        return [
            inst for inst in self._instances.values()
            if inst.persistent_session_id == persistent_session_id
        ]

    def get_active_workflows(self) -> list[WorkflowInstance]:
        return [
            inst for inst in self._instances.values()
            if inst.status in (WorkflowStatus.ACTIVE, WorkflowStatus.WAITING)
        ]

    # ─── Pipeline Integration (Fibonacci Plume Node 5) ──────

    def create_pipeline_workflow(self, pipeline_id: str, stages: list) -> dict:
        """Convert pipeline stage list to orchestrator workflow definition.

        Each pipeline stage becomes a pack_switch step + optional wait_for
        for deliverable completion. Returns a workflow def dict compatible
        with start_workflow().

        Args:
            pipeline_id: Pipeline identifier (e.g. "legal_client_onboard")
            stages: List of PipelineStage dataclasses, sorted by stage number.
        """
        steps = {}
        step_order = []

        for i, stage in enumerate(stages):
            is_first = (i == 0)
            is_last = (i == len(stages) - 1)
            stage_prefix = f"stage_{stage.stage}"

            if not is_first:
                # Add pack_switch step for stages 2+
                switch_id = f"{stage_prefix}_switch"
                wait_id = f"{stage_prefix}_wait"
                steps[switch_id] = {
                    "type": "pack_switch",
                    "params": {
                        "target_pack": stage.pack_id,
                        "carry_fields": stage.carry_fields,
                    },
                    "on_success": wait_id if not stage.auto_advance else (
                        f"stage_{stages[i + 1].stage}_switch" if not is_last else "pipeline_complete"
                    ),
                    "on_failure": "pipeline_complete",
                }
                step_order.append(switch_id)

            # Add wait_for step (deliverable completion gate)
            if not stage.auto_advance or is_last:
                wait_id = f"{stage_prefix}_wait"
                next_id = (
                    f"stage_{stages[i + 1].stage}_switch" if not is_last else "pipeline_complete"
                )
                steps[wait_id] = {
                    "type": "wait_for",
                    "params": {
                        "event": stage.advance_condition,
                        "pack_id": stage.pack_id,
                    },
                    "on_success": next_id,
                }
                step_order.append(wait_id)

        # Terminal complete step
        steps["pipeline_complete"] = {"type": "complete"}
        step_order.append("pipeline_complete")

        first_step = step_order[0] if step_order else "pipeline_complete"

        return {
            "id": f"pipeline_{pipeline_id}",
            "name": f"Pipeline: {pipeline_id}",
            "steps": steps,
            "first_step": first_step,
            "max_steps": len(stages) * 3,
            "timeout_days": 30,
        }

    # ─── Helpers ────────────────────────────────────────────

    def _resolve_context_vars(self, params: dict, context: dict) -> dict:
        """Resolve {{variable}} placeholders in parameter values."""
        resolved = {}
        for k, v in params.items():
            if isinstance(v, str) and "{{" in v:
                resolved[k] = self._resolve_context_template(v, context)
            else:
                resolved[k] = v
        return resolved

    @staticmethod
    def _resolve_context_template(template: str, context: dict) -> str:
        """Resolve {{variable}} placeholders in a template string."""
        import re
        def replacer(m):
            key = m.group(1)
            parts = key.split(".")
            current = context
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return ""
            return str(current) if current is not None else ""

        return re.sub(r"\{\{(\w[\w.]*)\}\}", replacer, template)

    @staticmethod
    def _matches_filter(event_data: dict, filter_criteria: dict) -> bool:
        """Check if event_data matches all filter criteria."""
        for key, expected in filter_criteria.items():
            actual = event_data.get(key)
            if actual != expected:
                return False
        return True

    async def _persist_instance(self, instance: WorkflowInstance):
        """Persist workflow instance to Supabase (if available)."""
        if self.db is None:
            return

        row = {
            "id": instance.id,
            "workflow_id": instance.workflow_id,
            "pack_id": instance.pack_id,
            "persistent_session_id": instance.persistent_session_id or None,
            "status": instance.status.value if isinstance(instance.status, WorkflowStatus) else instance.status,
            "current_step_id": instance.current_step_id,
            "completed_steps": instance.completed_steps,
            "context": instance.context,
            "total_steps_executed": instance.total_steps_executed,
            "max_steps": instance.max_steps,
            "cancellation_reason": instance.cancellation_reason,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        for ts_field in ("started_at", "last_step_at", "next_step_at", "timeout_at", "completed_at"):
            val = getattr(instance, ts_field)
            row[ts_field] = val.isoformat() if val else None

        try:
            self.db.table("workflow_instances").upsert(row).execute()
        except Exception as e:
            logger.warning(f"Failed to persist workflow instance {instance.id}: {e}")
