"""
TMOS13 Agentic Task Queue

Sequential executor for multi-step desk operations (e.g. batch email).
One confirmation covers the whole job; each task executes with live
progress via WebSocket events.

Usage:
    queue = TaskQueue(
        id="q-abc123",
        title="Sending 3 emails",
        tasks=[Task(id="t-1", label="alice@x.com"), ...],
        session_id="sess-xyz",
    )
    executors = [lambda: send_one("alice@x.com"), ...]
    result = await run_task_queue(queue, executors, emit)
"""
import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Awaitable, Optional

logger = logging.getLogger("tmos13.task_queue")


# ─── Data Structures ────────────────────────────────────

class TaskStatus(str, Enum):
    queued = "queued"
    running = "running"
    complete = "complete"
    failed = "failed"


@dataclass
class Task:
    id: str
    label: str
    status: TaskStatus = TaskStatus.queued
    result: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class TaskQueue:
    id: str
    title: str
    tasks: list[Task] = field(default_factory=list)
    session_id: str = ""


# ─── Serialization ──────────────────────────────────────

def serialize_queue(queue: TaskQueue) -> dict:
    """JSON-safe representation for WebSocket events."""
    all_done = all(
        t.status in (TaskStatus.complete, TaskStatus.failed)
        for t in queue.tasks
    )
    complete_count = sum(
        1 for t in queue.tasks if t.status == TaskStatus.complete
    )
    return {
        "id": queue.id,
        "title": queue.title,
        "session_id": queue.session_id,
        "all_done": all_done,
        "complete": complete_count,
        "total": len(queue.tasks),
        "tasks": [
            {
                "id": t.id,
                "label": t.label,
                "status": t.status.value,
                "result": t.result,
                "error": t.error,
            }
            for t in queue.tasks
        ],
    }


# ─── Executor ───────────────────────────────────────────

Executor = Callable[[], Awaitable[Any]]
Emitter = Callable[[dict], Awaitable[None]]

TASK_DELAY_SECONDS = 0.3  # rate-limit safety between tasks


async def run_task_queue(
    queue: TaskQueue,
    executors: list[Executor],
    emit: Emitter,
) -> TaskQueue:
    """
    Execute tasks sequentially with live progress via emit().

    - Emits ``task_queue`` event on start
    - Sets each task to ``running``, emits update
    - Executes, sets ``complete``/``failed``, emits update
    - 0.3s delay between tasks (rate limit safety)
    - Emits final ``task_queue`` event when all done
    - Never raises — failures recorded per-task

    Args:
        queue: The TaskQueue with tasks to execute.
        executors: One async callable per task (same order).
        emit: Async function that sends a WS event dict.

    Returns:
        The mutated TaskQueue with results filled in.
    """
    assert len(executors) == len(queue.tasks), (
        f"Executor count ({len(executors)}) != task count ({len(queue.tasks)})"
    )

    # Emit initial queue state
    await _safe_emit(emit, {
        "type": "task_queue",
        "task_queue": serialize_queue(queue),
    })

    for i, (task, executor) in enumerate(zip(queue.tasks, executors)):
        # Mark running
        task.status = TaskStatus.running
        await _safe_emit(emit, {
            "type": "task_queue",
            "task_queue": serialize_queue(queue),
        })

        # Execute
        try:
            result = await executor()
            task.status = TaskStatus.complete
            task.result = result
        except Exception as exc:
            task.status = TaskStatus.failed
            task.error = str(exc)
            logger.warning(f"Task {task.id} failed: {exc}")

        # Emit updated state
        await _safe_emit(emit, {
            "type": "task_queue",
            "task_queue": serialize_queue(queue),
        })

        # Rate-limit delay between tasks (skip after last)
        if i < len(queue.tasks) - 1:
            await asyncio.sleep(TASK_DELAY_SECONDS)

    logger.info(
        f"Task queue {queue.id} complete: "
        f"{sum(1 for t in queue.tasks if t.status == TaskStatus.complete)}"
        f"/{len(queue.tasks)} succeeded"
    )

    return queue


async def _safe_emit(emit: Emitter, event: dict) -> None:
    """Emit with error guard — never let WS failures kill the queue."""
    try:
        await emit(event)
    except Exception as exc:
        logger.warning(f"Task queue emit failed: {exc}")


# ─── Helpers ────────────────────────────────────────────

def make_queue_id() -> str:
    return f"q-{uuid.uuid4().hex[:8]}"


def make_task_id() -> str:
    return f"t-{uuid.uuid4().hex[:8]}"
