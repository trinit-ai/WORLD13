"""
Engine Dashboard API.

Operational transparency for the TMOS13 dashboard. These endpoints aggregate
data from existing services (session_store, monitoring, llm_provider, etc.)
into dashboard-friendly response shapes.

No new tables. No new services. Pure read-only aggregation.

Endpoints:
  GET /api/engine/overview   — System-wide metrics snapshot
  GET /api/engine/sessions   — Active/recent session list
  GET /api/engine/costs      — Cost breakdown by model/pack/time
  GET /api/engine/agents     — Derived agent roster

Registration: register_engine_endpoints(app)
"""
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import Depends

from auth import require_auth, UserProfile

logger = logging.getLogger("tmos13.engine_api")


# ─── Model Pricing ──────────────────────────────────────

# Cost per million tokens (input, output)
MODEL_PRICING = {
    "claude-3-haiku":    {"input": 0.25,  "output": 1.25},
    "claude-3-sonnet":   {"input": 3.0,   "output": 15.0},
    "claude-3-opus":     {"input": 15.0,  "output": 75.0},
    "claude-3.5-haiku":  {"input": 0.80,  "output": 4.0},
    "claude-3.5-sonnet": {"input": 3.0,   "output": 15.0},
    "claude-4-sonnet":   {"input": 3.0,   "output": 15.0},
    "claude-4.5-sonnet": {"input": 3.0,   "output": 15.0},
    "claude-sonnet-4-6": {"input": 3.0,   "output": 15.0},
}

# Default pricing for unknown models
_DEFAULT_PRICING = {"input": 3.0, "output": 15.0}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a given model and token count."""
    pricing = MODEL_PRICING.get(model, _DEFAULT_PRICING)
    return (input_tokens * pricing["input"] / 1_000_000) + (output_tokens * pricing["output"] / 1_000_000)


# ─── Helpers ─────────────────────────────────────────────

def _safe_get_metrics():
    """Get MetricsCollector safely — returns None if not initialized."""
    try:
        from monitoring import MetricsCollector
        m = MetricsCollector()
        if hasattr(m, "_initialized") and m._initialized:
            return m
    except Exception:
        pass
    return None


def _safe_get_sessions():
    """Get SessionStore from app module safely."""
    try:
        import app
        return app.sessions
    except Exception:
        return None


def _safe_get_transcript_store():
    """Get TranscriptStore from app module safely."""
    try:
        import app
        return app.transcript_store
    except Exception:
        return None


def _safe_get_alert_store():
    """Get AlertStore from app module safely."""
    try:
        import app
        return app.alert_store
    except Exception:
        return None


def _safe_get_llm_provider():
    """Get the LLM provider safely."""
    try:
        from llm_provider import get_llm_provider
        return get_llm_provider()
    except Exception:
        return None


def _safe_get_pack(pack_id: str):
    """Load a pack safely."""
    try:
        from config import get_pack
        return get_pack(pack_id)
    except Exception:
        return None


def _safe_get_pack_ids() -> list[str]:
    """Get available pack IDs safely."""
    try:
        from config import get_pack_ids
        return get_pack_ids()
    except Exception:
        return []


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _start_of_today() -> datetime:
    return _now_utc().replace(hour=0, minute=0, second=0, microsecond=0)


def _start_of_week() -> datetime:
    now = _now_utc()
    return (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


def _start_of_month() -> datetime:
    return _now_utc().replace(day=1, hour=0, minute=0, second=0, microsecond=0)


# ─── Registration ────────────────────────────────────────

def register_engine_endpoints(app):
    """Register engine dashboard endpoints. Called in app.py lifespan."""

    # ─── GET /api/engine/overview ────────────────────────

    @app.get("/api/engine/overview", tags=["engine"])
    async def engine_overview(user: UserProfile = Depends(require_auth)):
        """System-wide metrics snapshot for the dashboard."""
        metrics = _safe_get_metrics()
        sessions = _safe_get_sessions()
        llm = _safe_get_llm_provider()

        # Active sessions
        active_count = 0
        active_packs: set[str] = set()
        total_sessions_today = 0
        today_start = _start_of_today().timestamp()

        if sessions:
            all_sessions = sessions.all
            active_count = len(all_sessions)
            for s in all_sessions.values():
                active_packs.add(s.pack_id)
                if s.session_start >= today_start:
                    total_sessions_today += 1

        # Model info
        models_in_use = []
        if llm:
            models_in_use.append({
                "model": llm.model,
                "active_count": active_count,
            })

        # Token and cost data from MetricsCollector
        # MetricsCollector tracks total_tokens_estimated but not input/output split.
        # We estimate a 30/70 input/output split for cost calculation.
        tokens_total = 0
        cost_today = 0.0
        avg_latency = 0.0

        if metrics:
            m = metrics.get_metrics()
            tokens_total = m.get("total_tokens_estimated", 0)
            avg_latency = m.get("claude_latency_ms", {}).get("avg", 0.0)

            # Estimate input/output split (30% input, 70% output)
            est_input = int(tokens_total * 0.3)
            est_output = int(tokens_total * 0.7)
            model_name = llm.model if llm else "claude-sonnet-4-6"
            cost_today = estimate_cost(model_name, est_input, est_output)

        # Uptime
        uptime = 0.0
        if metrics:
            uptime = time.time() - metrics.started_at

        return {
            "active_sessions": active_count,
            "total_sessions_today": total_sessions_today,
            "active_packs": sorted(active_packs),
            "models_in_use": models_in_use,
            "tokens_today": {
                "input": int(tokens_total * 0.3),
                "output": int(tokens_total * 0.7),
                "total": tokens_total,
            },
            "cost_today_usd": round(cost_today, 4),
            "avg_latency_ms": round(avg_latency, 2),
            "uptime_seconds": round(uptime, 1),
        }

    # ─── GET /api/engine/sessions ────────────────────────

    @app.get("/api/engine/sessions", tags=["engine"])
    async def engine_sessions(
        status: Optional[str] = None,
        pack_id: Optional[str] = None,
        limit: int = 50,
        user: UserProfile = Depends(require_auth),
    ):
        """Active/recent session list with per-session metrics."""
        sessions = _safe_get_sessions()
        llm = _safe_get_llm_provider()
        model_name = llm.model if llm else "claude-sonnet-4-6"

        limit = min(limit, 200)
        result = []

        if sessions:
            all_sessions = sessions.all
            for sid, s in all_sessions.items():
                # Derive status from session state
                elapsed = time.time() - s.session_start
                if s.turn_count == 0:
                    sess_status = "waiting"
                elif elapsed > 1800:  # 30 min idle = resolved
                    sess_status = "resolved"
                else:
                    sess_status = "active"

                # Apply filters
                if status and sess_status != status:
                    continue
                if pack_id and s.pack_id != pack_id:
                    continue

                # Estimate tokens and cost per session
                # No per-session token tracking; estimate from turn count
                est_tokens = s.turn_count * 800  # ~800 tokens per turn average
                est_input = int(est_tokens * 0.3)
                est_output = int(est_tokens * 0.7)
                cost = estimate_cost(model_name, est_input, est_output)

                # Extract contact from forms if available
                contact = None
                if s.forms:
                    for form_data in s.forms.values():
                        if form_data.get("name") or form_data.get("email"):
                            contact = form_data.get("name") or form_data.get("email")
                            break

                result.append({
                    "session_id": s.session_id,
                    "pack_id": s.pack_id,
                    "contact": contact,
                    "cartridge": s.current_game,
                    "phase": f"depth_{s.depth}" if s.depth > 0 else "surface",
                    "turns": s.turn_count,
                    "tokens": est_tokens,
                    "cost_usd": round(cost, 4),
                    "latency_ms": 0.0,  # TODO: per-session latency tracking
                    "model": model_name,
                    "status": sess_status,
                    "started_at": datetime.fromtimestamp(
                        s.session_start, tz=timezone.utc
                    ).isoformat(),
                })

        # Sort by started_at descending (newest first)
        result.sort(key=lambda x: x["started_at"], reverse=True)
        result = result[:limit]

        return {"sessions": result}

    # ─── GET /api/engine/costs ───────────────────────────

    @app.get("/api/engine/costs", tags=["engine"])
    async def engine_costs(user: UserProfile = Depends(require_auth)):
        """Cost breakdown by model, pack, and time period."""
        sessions = _safe_get_sessions()
        transcript_store = _safe_get_transcript_store()
        llm = _safe_get_llm_provider()
        model_name = llm.model if llm else "claude-sonnet-4-6"

        today_start = _start_of_today().timestamp()
        week_start = _start_of_week().timestamp()
        month_start = _start_of_month().timestamp()

        # Aggregate from active sessions
        cost_today = 0.0
        cost_week = 0.0
        cost_month = 0.0
        by_model: dict[str, dict] = defaultdict(lambda: {"cost": 0.0, "tokens": 0})
        by_pack: dict[str, dict] = defaultdict(lambda: {"cost": 0.0, "sessions": 0})

        def _process_session(start_time: float, turn_count: int, pack: str):
            est_tokens = turn_count * 800
            est_input = int(est_tokens * 0.3)
            est_output = int(est_tokens * 0.7)
            cost = estimate_cost(model_name, est_input, est_output)

            by_model[model_name]["cost"] += cost
            by_model[model_name]["tokens"] += est_tokens
            by_pack[pack]["cost"] += cost
            by_pack[pack]["sessions"] += 1

            return cost, start_time

        # Active sessions
        if sessions:
            for s in sessions.all.values():
                cost, st = _process_session(s.session_start, s.turn_count, s.pack_id)
                if st >= today_start:
                    cost_today += cost
                if st >= week_start:
                    cost_week += cost
                if st >= month_start:
                    cost_month += cost

        # Closed transcripts (if available in memory)
        if transcript_store:
            for t in transcript_store.list_transcripts(closed_only=True, limit=500):
                cost, st = _process_session(t.started_at, t.turn_count, t.pack_id)
                if st >= today_start:
                    cost_today += cost
                if st >= week_start:
                    cost_week += cost
                if st >= month_start:
                    cost_month += cost

        return {
            "today": round(cost_today, 4),
            "this_week": round(cost_week, 4),
            "this_month": round(cost_month, 4),
            "by_model": [
                {"model": m, "cost": round(d["cost"], 4), "tokens": d["tokens"]}
                for m, d in sorted(by_model.items(), key=lambda x: -x[1]["cost"])
            ],
            "by_pack": [
                {"pack_id": p, "cost": round(d["cost"], 4), "sessions": d["sessions"]}
                for p, d in sorted(by_pack.items(), key=lambda x: -x[1]["cost"])
            ],
        }

    # ─── GET /api/engine/agents ──────────────────────────

    @app.get("/api/engine/agents", tags=["engine"])
    async def engine_agents(user: UserProfile = Depends(require_auth)):
        """Derived agent roster from loaded packs + session data."""
        sessions = _safe_get_sessions()
        transcript_store = _safe_get_transcript_store()
        llm = _safe_get_llm_provider()
        model_name = llm.model if llm else "claude-sonnet-4-6"

        pack_ids = _safe_get_pack_ids()
        today_start = _start_of_today().timestamp()

        # Count active sessions and today's sessions per pack
        active_by_pack: dict[str, int] = defaultdict(int)
        today_by_pack: dict[str, int] = defaultdict(int)
        cost_by_pack: dict[str, float] = defaultdict(float)

        if sessions:
            for s in sessions.all.values():
                active_by_pack[s.pack_id] += 1
                if s.session_start >= today_start:
                    today_by_pack[s.pack_id] += 1
                    est_tokens = s.turn_count * 800
                    cost_by_pack[s.pack_id] += estimate_cost(
                        model_name, int(est_tokens * 0.3), int(est_tokens * 0.7)
                    )

        # Count resolved sessions from transcripts for fidelity score
        resolved_by_pack: dict[str, int] = defaultdict(int)
        total_by_pack: dict[str, int] = defaultdict(int)
        if transcript_store:
            for t in transcript_store.list_transcripts(limit=500):
                total_by_pack[t.pack_id] += 1
                if t.is_closed:
                    resolved_by_pack[t.pack_id] += 1

        agents = []
        for pid in pack_ids:
            # Skip templates
            if pid.startswith("base_"):
                continue

            pack = _safe_get_pack(pid)
            pack_name = pack.name if pack else pid

            # Derive department from library category (organizational), not pack category (system)
            lib_cat = pack.library_config.get("category", "") if pack else ""
            department = lib_cat or (pack.category if pack else "general") or "general"

            # Status: active if has active sessions, idle otherwise
            agent_status = "active" if active_by_pack.get(pid, 0) > 0 else "idle"

            # Fidelity: resolved / total, default 0.95 if no data
            total = total_by_pack.get(pid, 0)
            resolved = resolved_by_pack.get(pid, 0)
            fidelity = resolved / total if total > 0 else 0.95

            agents.append({
                "agent_id": f"{pid}_{department}",
                "name": pack_name,
                "department": department,
                "pack_id": pid,
                "model": model_name,
                "status": agent_status,
                "sessions_today": today_by_pack.get(pid, 0),
                "fidelity_score": round(fidelity, 2),
                "cost_today": round(cost_by_pack.get(pid, 0.0), 4),
            })

        # Sort: active first, then by sessions_today
        agents.sort(key=lambda a: (-int(a["status"] == "active"), -a["sessions_today"]))

        return {"agents": agents}
