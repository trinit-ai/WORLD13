"""
TMOS13 Toolbar API — Contextual Toolbar Management

Endpoints:
  GET  /api/toolbar/config   — Get toolbar config for current context
  POST /api/toolbar/action   — Dispatch a toolbar button action
"""

import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from toolbar import get_toolbar_resolver, ToolbarAction

logger = logging.getLogger("tmos13.api.toolbar")


# ─── Request / Response Models ───────────────────────────

class ToolbarButtonResponse(BaseModel):
    id: str
    label: str
    action_type: str
    action_target: str
    icon: str | None = None
    variant: str = "secondary"
    confirm: str | None = None
    disabled_until: str | None = None


class ToolbarConfigResponse(BaseModel):
    buttons: list[ToolbarButtonResponse]
    position: str = "above_input"
    visible_when: str | None = None


class ToolbarActionRequest(BaseModel):
    button_id: str
    session_id: str


class ToolbarActionResponse(BaseModel):
    success: bool
    action_type: str | None = None
    action_target: str | None = None
    error: str | None = None


# ─── Registration ────────────────────────────────────────

def register_toolbar_endpoints(app: FastAPI) -> None:
    """Register Toolbar API endpoints."""

    @app.get(
        "/api/toolbar/config",
        response_model=ToolbarConfigResponse,
        tags=["toolbar"],
    )
    async def get_toolbar_config(
        pack_id: str | None = None,
        cartridge_id: str | None = None,
    ):
        """Get toolbar configuration for the current context."""
        from config import get_pack
        from pack_loader import PackLoader

        pack = None
        if pack_id:
            try:
                pack = PackLoader(pack_id)
            except Exception:
                pass
        if not pack:
            pack = get_pack()

        manifest = pack.manifest if pack else {}
        resolver = get_toolbar_resolver()
        config = resolver.resolve(manifest, cartridge_id)

        return ToolbarConfigResponse(
            buttons=[
                ToolbarButtonResponse(**b.to_dict())
                for b in config.buttons
            ],
            position=config.position,
            visible_when=config.visible_when,
        )

    @app.post(
        "/api/toolbar/action",
        response_model=ToolbarActionResponse,
        tags=["toolbar"],
    )
    async def dispatch_toolbar_action(req: ToolbarActionRequest):
        """Dispatch a toolbar button action."""
        from app import sessions

        state = sessions.get(req.session_id)
        if not state:
            raise HTTPException(status_code=404, detail="Session not found")

        # Get pack manifest for validation
        from config import get_pack
        pack = get_pack()
        manifest = pack.manifest if pack else {}

        resolver = get_toolbar_resolver()
        config = resolver.resolve(manifest, state.current_game)

        # Find the button
        button = None
        for b in config.buttons:
            if b.id == req.button_id:
                button = b
                break

        if not button:
            return ToolbarActionResponse(
                success=False,
                error=f"Button '{req.button_id}' not found in toolbar",
            )

        # Validate and record
        action = ToolbarAction(
            button_id=button.id,
            action_type=button.action_type,
            action_target=button.action_target,
            session_id=req.session_id,
        )
        resolver.validate_action(action, config)

        return ToolbarActionResponse(
            success=True,
            action_type=button.action_type,
            action_target=button.action_target,
        )
