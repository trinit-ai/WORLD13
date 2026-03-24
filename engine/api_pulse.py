"""
Pulse: Connector health monitoring for TMOS13 dashboard.

Surfaces the health status of every MCP connector: latency, error rate,
event count, last activity. Derives system-wide status from individual
connector health.

Endpoints:
  GET /api/pulse              — All connector health statuses + system status
  GET /api/pulse/:name        — Detailed health for one connector

Registration: register_pulse_endpoints(app)
"""
import logging
from typing import Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from auth import require_auth, UserProfile
from mcp_connectors import ConnectorRegistry

logger = logging.getLogger("tmos13.pulse")


# ── Connector metadata (display info, icons, colors) ────

CONNECTOR_META = {
    # ── Live connectors ────────────────────────────────────
    "weather": {"display_name": "Weather", "icon": "cloud", "color": "#60a5fa"},
    "stocks": {"display_name": "Stocks", "icon": "trending-up", "color": "#34d399"},
    "news": {"display_name": "News", "icon": "newspaper", "color": "#f59e0b"},
    "github": {"display_name": "GitHub", "icon": "git-branch", "color": "#8b5cf6"},
    "claude_code": {"display_name": "Claude Code", "icon": "terminal", "color": "#d4a574"},
    # ── System connectors (stub) ───────────────────────────
    "email": {"display_name": "Email", "icon": "mail", "color": "#f472b6"},
    "calendar": {"display_name": "Calendar", "icon": "calendar", "color": "#fb923c"},
    # ── Third-party connectors (stub) ──────────────────────
    "slack": {"display_name": "Slack", "icon": "hash", "color": "#e01e5a"},
    "whatsapp": {"display_name": "WhatsApp", "icon": "message-circle", "color": "#25d366"},
    "stripe": {"display_name": "Stripe", "icon": "credit-card", "color": "#635bff"},
    "calendly": {"display_name": "Calendly", "icon": "calendar-check", "color": "#006bff"},
    "zoom": {"display_name": "Zoom", "icon": "video", "color": "#2d8cff"},
    "notion": {"display_name": "Notion", "icon": "file-text", "color": "#e6e6e4"},
    "salesforce": {"display_name": "Salesforce", "icon": "cloud", "color": "#00a1e0"},
    "hubspot": {"display_name": "HubSpot", "icon": "target", "color": "#ff7a59"},
    # ── Infrastructure connectors (stub) ───────────────────
    "vercel": {"display_name": "Vercel", "icon": "triangle", "color": "#ffffff"},
    "railway": {"display_name": "Railway", "icon": "train-front", "color": "#c049ef"},
    "resend": {"display_name": "Resend", "icon": "send", "color": "#00c4b4"},
    "supabase": {"display_name": "Supabase", "icon": "database", "color": "#3ecf8e"},
    "huggingface": {"display_name": "Hugging Face", "icon": "bot", "color": "#ffcc00"},
}


def _enrich_health(health: dict) -> dict:
    """Enrich a connector health dict with display metadata if available."""
    meta = CONNECTOR_META.get(health["name"], {})
    if meta:
        health["display_name"] = meta.get("display_name", health["display_name"])
        health["config"]["icon"] = health["config"].get("icon") or meta.get("icon")
        health["config"]["color"] = health["config"].get("color") or meta.get("color")
    return health


def _derive_system_status(health_list: list[dict]) -> str:
    """Derive system-wide status from individual connector statuses.

    - "nominal"  — all enabled connectors are connected
    - "degraded" — any enabled connector is degraded
    - "down"     — more than half of enabled connectors are disconnected
    """
    enabled = [h for h in health_list if h["enabled"]]
    if not enabled:
        return "nominal"

    disconnected_count = sum(1 for h in enabled if h["status"] == "disconnected")
    degraded_count = sum(1 for h in enabled if h["status"] == "degraded")

    if disconnected_count > len(enabled) / 2:
        return "down"
    if degraded_count > 0 or disconnected_count > 0:
        return "degraded"
    return "nominal"


# ── Registration ────────────────────────────────────────

def register_pulse_endpoints(app, connector_registry: ConnectorRegistry):
    """Register pulse health endpoints. Called in app.py lifespan."""

    # ── GET /api/pulse ───────────────────────────────────

    @app.get("/api/pulse", tags=["pulse"])
    async def pulse_overview(
        user: UserProfile = Depends(require_auth),
    ):
        """All connector health statuses + system status."""
        health_list = []
        registered_names = set()
        for name, connector in connector_registry.connectors.items():
            if name not in CONNECTOR_META:
                continue  # Skip connectors without display metadata
            health = connector.health_status()
            health_list.append(_enrich_health(health))
            registered_names.add(name)

        # Include stub entries for connectors in CONNECTOR_META but not registered
        for name, meta in CONNECTOR_META.items():
            if name not in registered_names:
                health_list.append({
                    "name": name,
                    "display_name": meta.get("display_name", name),
                    "enabled": False,
                    "status": "pending",
                    "events_today": 0,
                    "avg_latency_ms": 0,
                    "last_event_at": None,
                    "config": {
                        "icon": meta.get("icon"),
                        "color": meta.get("color"),
                    },
                })

        enabled = [h for h in health_list if h["enabled"]]
        return {
            "system_status": _derive_system_status(health_list),
            "total_integrations": len(health_list),
            "connected": sum(1 for h in enabled if h["status"] == "connected"),
            "degraded": sum(1 for h in enabled if h["status"] == "degraded"),
            "disconnected": sum(1 for h in enabled if h["status"] == "disconnected"),
            "integrations": health_list,
        }

    # ── GET /api/pulse/:name ─────────────────────────────
    # Registered after the overview to avoid path conflict

    @app.get("/api/pulse/{connector_name}", tags=["pulse"])
    async def pulse_connector_detail(
        connector_name: str,
        user: UserProfile = Depends(require_auth),
    ):
        """Detailed health for one connector with recent events."""
        connector = connector_registry.get(connector_name)
        if not connector:
            raise HTTPException(404, f"Connector not found: {connector_name}")

        detail = connector.health_detail()
        return _enrich_health(detail)
