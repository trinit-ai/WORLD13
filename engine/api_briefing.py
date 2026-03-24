"""
TMOS13 Daily Briefing — Aggregation Endpoint

GET /api/briefing/daily — returns an activity snapshot from existing tables.
No LLM calls, no new migrations. Pure read aggregation.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, Depends, Request
from pydantic import BaseModel

logger = logging.getLogger("tmos13.api_briefing")


# ─── Response Models ──────────────────────────────────────────

class BriefingItem(BaseModel):
    label: str
    value: str


class BriefingSection(BaseModel):
    heading: str
    icon: str
    items: list[BriefingItem]


class DailyBriefingResponse(BaseModel):
    date: str
    greeting: str
    sections: list[BriefingSection]
    generated_at: str
    text_summary: str


# ─── Safe Helpers ─────────────────────────────────────────────

def _safe_get_journals(db, user_id: str, since: datetime) -> list[dict]:
    """Query session_journals for recent entries. Returns [] on failure."""
    if not db:
        return []
    try:
        result = (
            db.table("session_journals")
            .select("pack_id, turn_count, created_at")
            .eq("user_id", user_id)
            .gte("created_at", since.isoformat())
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.debug(f"Briefing: journals query failed: {e}")
        return []


def _safe_get_deliverables(db, user_id: str, since: datetime) -> list[dict]:
    """Query deliverables for recent entries. Returns [] on failure."""
    if not db:
        return []
    try:
        result = (
            db.table("deliverables")
            .select("spec_name, status, pack_id, created_at")
            .eq("user_id", user_id)
            .gte("created_at", since.isoformat())
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.debug(f"Briefing: deliverables query failed: {e}")
        return []


def _safe_get_installs(user_id: str) -> list[dict]:
    """Get active pack installs via pack_install_service. Returns [] on failure."""
    try:
        from pack_install_service import get_pack_install_service
        svc = get_pack_install_service()
        if not svc:
            return []
        return svc.get_user_installs(user_id, status_filter="active")
    except Exception as e:
        logger.debug(f"Briefing: installs query failed: {e}")
        return []


def _safe_get_upcoming_schedule() -> list[dict]:
    """Get schedule entries firing in the next 24h. Returns [] on failure."""
    try:
        from schedule_cache import get_schedule_cache, next_occurrence
        cache = get_schedule_cache()
        if not cache:
            return []

        now = datetime.now(timezone.utc)
        window_end = now + timedelta(hours=24)
        upcoming = []

        for pack_id in cache._entries:
            for entry in cache.get_entries_for_pack(pack_id):
                if not entry.enabled:
                    continue
                try:
                    nxt = next_occurrence(entry, now)
                    if nxt <= window_end:
                        upcoming.append({
                            "pack_id": pack_id,
                            "action": entry.action,
                            "reason": entry.reason,
                            "next_at": nxt.isoformat(),
                        })
                except Exception:
                    continue

        upcoming.sort(key=lambda x: x["next_at"])
        return upcoming[:10]
    except Exception as e:
        logger.debug(f"Briefing: schedule query failed: {e}")
        return []


def _safe_get_weekly_journals(db, user_id: str) -> list[dict]:
    """Query session_journals for the past 7 days (weekly insights). Returns [] on failure."""
    if not db:
        return []
    try:
        since = datetime.now(timezone.utc) - timedelta(days=7)
        result = (
            db.table("session_journals")
            .select("pack_id, created_at")
            .eq("user_id", user_id)
            .gte("created_at", since.isoformat())
            .order("created_at", desc=True)
            .limit(200)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.debug(f"Briefing: weekly journals query failed: {e}")
        return []


def _build_text_summary(date_str: str, sections: list[BriefingSection]) -> str:
    """Format sections as plaintext markdown for download/copy."""
    lines = [f"TMOS13 Daily Briefing — {date_str}", ""]
    for section in sections:
        lines.append(f"## {section.icon} {section.heading}")
        for item in section.items:
            lines.append(f"- **{item.label}**: {item.value}")
        lines.append("")
    return "\n".join(lines)


# ─── Endpoint Registration ───────────────────────────────────

def register_briefing_endpoints(app: FastAPI, db=None):
    """Register the daily briefing endpoint."""

    @app.get("/api/briefing/daily", response_model=DailyBriefingResponse)
    async def daily_briefing(request: Request):
        """Aggregate recent activity into a daily briefing snapshot."""
        from auth import get_current_user
        try:
            user = await get_current_user(request)
        except Exception:
            user = None

        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        since_24h = now - timedelta(hours=24)

        sections: list[BriefingSection] = []

        if user:
            uid = user.user_id

            # ── Section 1: Activity (sessions last 24h) ──
            journals = _safe_get_journals(db, uid, since_24h)
            if journals:
                count = len(journals)
                # Pack breakdown
                pack_counts: dict[str, int] = {}
                total_turns = 0
                for j in journals:
                    pid = j.get("pack_id", "unknown")
                    pack_counts[pid] = pack_counts.get(pid, 0) + 1
                    total_turns += j.get("turn_count", 0)

                breakdown = ", ".join(
                    f"{pid.replace('_', ' ').title()}: {c}"
                    for pid, c in sorted(pack_counts.items(), key=lambda x: -x[1])
                )
                items = [BriefingItem(label="Sessions (24h)", value=str(count))]
                if breakdown:
                    items.append(BriefingItem(label="Pack Breakdown", value=breakdown))
                if count > 0:
                    avg = round(total_turns / count, 1)
                    items.append(BriefingItem(label="Avg Turns", value=str(avg)))

                sections.append(BriefingSection(heading="Activity", icon="\u26A1", items=items))

            # ── Section 2: Deliverables (last 24h) ──
            deliverables = _safe_get_deliverables(db, uid, since_24h)
            if deliverables:
                items = []
                for d in deliverables[:5]:
                    name = d.get("spec_name") or d.get("pack_id", "—")
                    status = d.get("status", "generated")
                    pack = d.get("pack_id", "")
                    label = name
                    value = f"{status}"
                    if pack:
                        value += f" ({pack.replace('_', ' ').title()})"
                    items.append(BriefingItem(label=label, value=value))

                sections.append(BriefingSection(heading="Deliverables", icon="\uD83D\uDCE6", items=items))

            # ── Section 3: Installed Packs ──
            installs = _safe_get_installs(uid)
            if installs:
                pack_names = [i.get("pack_id", "").replace("_", " ").title() for i in installs]
                items = [
                    BriefingItem(label="Active Packs", value=str(len(installs))),
                    BriefingItem(label="Installed", value=", ".join(pack_names[:8])),
                ]
                sections.append(BriefingSection(heading="Installed Packs", icon="\uD83D\uDCE6", items=items))

        # ── Section 4: Upcoming Schedule (no auth required) ──
        upcoming = _safe_get_upcoming_schedule()
        if upcoming:
            items = []
            for u in upcoming[:5]:
                next_at = u.get("next_at", "")
                try:
                    dt = datetime.fromisoformat(next_at)
                    time_str = dt.strftime("%H:%M UTC")
                except Exception:
                    time_str = next_at
                reason = u.get("reason", u.get("action", ""))
                pack = u.get("pack_id", "").replace("_", " ").title()
                items.append(BriefingItem(
                    label=f"{pack} — {u.get('action', '')}",
                    value=f"{time_str}" + (f" ({reason})" if reason else ""),
                ))
            sections.append(BriefingSection(heading="Upcoming Schedule", icon="\uD83D\uDD52", items=items))

        # ── Section 5: Weekly Insights ──
        if user:
            weekly = _safe_get_weekly_journals(db, user.user_id)
            if weekly:
                week_count = len(weekly)
                pack_counts_w: dict[str, int] = {}
                for j in weekly:
                    pid = j.get("pack_id", "unknown")
                    pack_counts_w[pid] = pack_counts_w.get(pid, 0) + 1

                items = [BriefingItem(label="Sessions This Week", value=str(week_count))]
                if pack_counts_w:
                    top_pack = max(pack_counts_w, key=pack_counts_w.get)  # type: ignore[arg-type]
                    items.append(BriefingItem(
                        label="Most-Used Pack",
                        value=f"{top_pack.replace('_', ' ').title()} ({pack_counts_w[top_pack]} sessions)",
                    ))

                sections.append(BriefingSection(heading="Insights", icon="\uD83D\uDCA1", items=items))

        # Build response
        text_summary = _build_text_summary(today, sections)

        return DailyBriefingResponse(
            date=today,
            greeting="Here\u2019s your daily briefing",
            sections=sections,
            generated_at=now.isoformat(),
            text_summary=text_summary,
        )
