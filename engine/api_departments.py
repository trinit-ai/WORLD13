"""
Department Registry API.

Endpoints:
  GET    /api/departments                          — List departments
  POST   /api/departments                          — Create department
  PUT    /api/departments/:id                      — Update department
  DELETE /api/departments/:id                      — Delete department
  GET    /api/departments/:id/members              — List members
  POST   /api/departments/:id/members              — Add member
  DELETE /api/departments/:id/members/:member_id   — Remove member
  GET    /api/departments/:id/assets               — Scoped assets

Registration: register_department_endpoints(app, db)
"""
import logging
from typing import Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from auth import require_auth, UserProfile
from config import TMOS13_OWNER_ID

logger = logging.getLogger("tmos13.departments.api")


# ── Pydantic Models ──────────────────────────────────────

class DepartmentCreate(BaseModel):
    id: str
    label: str
    description: str = ""
    icon: str = "LayoutGrid"
    color: str = "#64748b"
    sort_order: int = 0


class DepartmentUpdate(BaseModel):
    label: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None


class MemberAdd(BaseModel):
    user_email: str
    display_name: str = ""
    role: str = "member"


class RefileDepartment(BaseModel):
    department: str


# ── Registration ─────────────────────────────────────────

def register_department_endpoints(app, db) -> None:
    """Register department endpoints on the FastAPI application."""

    # ── GET /api/departments ─────────────────────────

    @app.get("/api/departments", tags=["departments"])
    async def departments_list(user: UserProfile = Depends(require_auth)):
        """List all departments for this owner."""
        result = db.table("departments") \
            .select("*") \
            .eq("owner_id", TMOS13_OWNER_ID) \
            .order("sort_order") \
            .execute()
        return {"departments": result.data or []}

    # ── POST /api/departments ────────────────────────

    @app.post("/api/departments", tags=["departments"], status_code=201)
    async def departments_create(
        req: DepartmentCreate,
        user: UserProfile = Depends(require_auth),
    ):
        """Create a new department."""
        result = db.table("departments").insert({
            "id": req.id,
            "owner_id": TMOS13_OWNER_ID,
            "label": req.label,
            "description": req.description,
            "icon": req.icon,
            "color": req.color,
            "sort_order": req.sort_order,
        }).execute()
        if not result.data:
            raise HTTPException(400, "Failed to create department")
        return result.data[0]

    # ── PUT /api/departments/:id ─────────────────────

    @app.put("/api/departments/{dept_id}", tags=["departments"])
    async def departments_update(
        dept_id: str,
        req: DepartmentUpdate,
        user: UserProfile = Depends(require_auth),
    ):
        """Update a department."""
        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(400, "No fields to update")
        updates["updated_at"] = "now()"
        result = db.table("departments") \
            .update(updates) \
            .eq("id", dept_id) \
            .eq("owner_id", TMOS13_OWNER_ID) \
            .execute()
        if not result.data:
            raise HTTPException(404, "Department not found")
        return result.data[0]

    # ── DELETE /api/departments/:id ──────────────────

    @app.delete("/api/departments/{dept_id}", tags=["departments"])
    async def departments_delete(
        dept_id: str,
        user: UserProfile = Depends(require_auth),
    ):
        """Delete a department."""
        result = db.table("departments") \
            .delete() \
            .eq("id", dept_id) \
            .eq("owner_id", TMOS13_OWNER_ID) \
            .execute()
        return {"deleted": True, "id": dept_id}

    # ── GET /api/departments/:id/members ─────────────

    @app.get("/api/departments/{dept_id}/members", tags=["departments"])
    async def departments_members_list(
        dept_id: str,
        user: UserProfile = Depends(require_auth),
    ):
        """List members of a department."""
        result = db.table("department_members") \
            .select("*") \
            .eq("department_id", dept_id) \
            .eq("owner_id", TMOS13_OWNER_ID) \
            .order("created_at") \
            .execute()
        return {"members": result.data or []}

    # ── POST /api/departments/:id/members ────────────

    @app.post("/api/departments/{dept_id}/members", tags=["departments"], status_code=201)
    async def departments_members_add(
        dept_id: str,
        req: MemberAdd,
        user: UserProfile = Depends(require_auth),
    ):
        """Add a member to a department."""
        result = db.table("department_members").insert({
            "department_id": dept_id,
            "owner_id": TMOS13_OWNER_ID,
            "user_email": req.user_email,
            "display_name": req.display_name,
            "role": req.role,
        }).execute()
        if not result.data:
            raise HTTPException(400, "Failed to add member")
        return result.data[0]

    # ── DELETE /api/departments/:id/members/:member_id

    @app.delete("/api/departments/{dept_id}/members/{member_id}", tags=["departments"])
    async def departments_members_remove(
        dept_id: str,
        member_id: str,
        user: UserProfile = Depends(require_auth),
    ):
        """Remove a member from a department."""
        db.table("department_members") \
            .delete() \
            .eq("id", member_id) \
            .eq("department_id", dept_id) \
            .eq("owner_id", TMOS13_OWNER_ID) \
            .execute()
        return {"deleted": True, "id": member_id}

    # ── GET /api/departments/:id/assets ──────────────

    @app.get("/api/departments/{dept_id}/assets", tags=["departments"])
    async def departments_assets(
        dept_id: str,
        user: UserProfile = Depends(require_auth),
    ):
        """Get vault items, contacts, notes, and manifest entries scoped to a department."""
        vault_result = db.table("vault_items") \
            .select("id,filename,mime_type,size_bytes,tier,created_at") \
            .eq("owner_id", TMOS13_OWNER_ID) \
            .eq("department", dept_id) \
            .order("created_at", desc=True) \
            .limit(20) \
            .execute()

        contacts_result = db.table("contacts") \
            .select("id,name,email,source,created_at") \
            .eq("owner_id", TMOS13_OWNER_ID) \
            .eq("department", dept_id) \
            .order("created_at", desc=True) \
            .limit(20) \
            .execute()

        notes_result = db.table("notes") \
            .select("id,title,content,created_at") \
            .eq("user_id", TMOS13_OWNER_ID) \
            .eq("department", dept_id) \
            .order("created_at", desc=True) \
            .limit(20) \
            .execute()

        manifest_result = db.table("manifest_entries") \
            .select("id,event_type,category,summary,created_at") \
            .eq("owner_id", TMOS13_OWNER_ID) \
            .eq("department", dept_id) \
            .order("created_at", desc=True) \
            .limit(20) \
            .execute()

        return {
            "vault_items": vault_result.data or [],
            "contacts": contacts_result.data or [],
            "notes": notes_result.data or [],
            "manifest_entries": manifest_result.data or [],
        }
