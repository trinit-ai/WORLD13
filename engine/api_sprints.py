"""Sprint Items API routes."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from auth import get_current_user

router = APIRouter(prefix="/api/sprints", tags=["sprints"])


class SprintCreate(BaseModel):
    title: str
    description: Optional[str] = None
    pack_id: Optional[str] = None
    seed_context: Optional[dict] = None
    due_date: Optional[str] = None
    completion_type: str = "manual"
    priority: int = 0


class SprintUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    pack_id: Optional[str] = None
    seed_context: Optional[dict] = None
    due_date: Optional[str] = None
    priority: Optional[int] = None
    status: Optional[str] = None
    completion_type: Optional[str] = None


@router.get("")
async def list_sprints(
    status: Optional[str] = None,
    pack_id: Optional[str] = None,
    limit: int = 20,
    user=Depends(get_current_user),
):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    from app import sprint_store
    status_filter = status.split(",") if status else None
    return sprint_store.list_sprints(user.user_id, status_filter=status_filter, pack_id=pack_id, limit=limit)


@router.post("")
async def create_sprint(body: SprintCreate, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    from app import sprint_store
    item = sprint_store.create_sprint(
        owner_id=user.user_id,
        title=body.title,
        description=body.description,
        pack_id=body.pack_id,
        seed_context=body.seed_context,
        due_date=body.due_date,
        completion_type=body.completion_type,
        priority=body.priority,
    )
    if not item:
        raise HTTPException(status_code=500, detail="Failed to create sprint item")
    return item


@router.patch("/{sprint_id}")
async def update_sprint(sprint_id: str, body: SprintUpdate, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    from app import sprint_store
    updates = body.model_dump(exclude_none=True)
    item = sprint_store.update_sprint(sprint_id, user.user_id, updates)
    if not item:
        raise HTTPException(status_code=404, detail="Sprint not found")
    return item


@router.post("/{sprint_id}/start")
async def start_sprint(sprint_id: str, user=Depends(get_current_user)):
    """Launch a session for this sprint item."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    from app import sprint_store
    import uuid

    if not sprint_store._db:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Get the sprint item first
    result = sprint_store._db.table("sprint_items").select("*").eq("id", sprint_id).eq("owner_id", user.user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Sprint not found")

    sprint = result.data[0]
    if sprint["status"] not in ("pending", "active"):
        raise HTTPException(status_code=400, detail="Sprint is not startable")

    # Generate a session ID
    session_id = str(uuid.uuid4())[:8]

    # Link sprint to session
    sprint_store.start_sprint(sprint_id, user.user_id, session_id)

    return {
        "session_id": session_id,
        "pack_id": sprint["pack_id"],
        "seed_context": sprint.get("seed_context", {}),
    }


@router.post("/{sprint_id}/complete")
async def complete_sprint(sprint_id: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    from app import sprint_store
    item = sprint_store.update_sprint(sprint_id, user.user_id, {"status": "complete"})
    if not item:
        raise HTTPException(status_code=404, detail="Sprint not found")
    return item


@router.delete("/{sprint_id}")
async def archive_sprint(sprint_id: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    from app import sprint_store
    success = sprint_store.archive_sprint(sprint_id, user.user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Sprint not found")
    return {"status": "archived"}
