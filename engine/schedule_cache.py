"""
TMOS13 Schedule Cache — TimeKeeper (Fibonacci Plume Node 11)

Parses manifest-declared schedules and evaluates them against the live clock.
Supports three pattern types: every_Nh, daily_at, weekly_on.

No external dependencies (no croniter). Simple regex pattern matching.

Usage:
    cache = init_schedule_cache()
    cache.load_from_manifests(loaded_packs)
    due = cache.get_due_entries(datetime.now(timezone.utc))
"""
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger("tmos13.schedule_cache")

# ─── Pattern Types ──────────────────────────────────────────

PATTERN_EVERY = "every_Nh"
PATTERN_DAILY = "daily_at"
PATTERN_WEEKLY = "weekly_on"

_EVERY_RE = re.compile(r"^every_(\d+)h$")
_DAILY_RE = re.compile(r"^daily_at\s+(\d{2}:\d{2})$")
_WEEKLY_RE = re.compile(r"^weekly_on\s+(\w+)\s+(\d{2}:\d{2})$")

_DAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


# ─── Data Structures ───────────────────────────────────────

@dataclass
class SchedulePattern:
    """Parsed schedule pattern."""
    pattern_type: str          # PATTERN_EVERY | PATTERN_DAILY | PATTERN_WEEKLY
    raw: str                   # original pattern string
    interval_hours: int = 0    # for every_Nh
    time_str: str = ""         # HH:MM for daily_at / weekly_on
    day_of_week: int = -1      # 0=Monday for weekly_on


@dataclass
class ScheduleEntry:
    """A single schedule entry from a pack manifest."""
    pack_id: str
    entry_id: str              # unique within pack
    action: str                # "pause" | "play" | "stop" | "notify" | "initiate" | "send"
    pattern: SchedulePattern
    timezone: str = "UTC"      # IANA timezone from manifest or session
    reason: str = ""           # human-readable reason for the transition
    enabled: bool = True
    initiate_for: str = ""     # "installed_users" | "active_contacts" | comma-separated user_ids
    _last_fired: Optional[datetime] = field(default=None, repr=False)


# ─── Pattern Parsing ───────────────────────────────────────

def parse_pattern(raw: str) -> SchedulePattern:
    """Parse a schedule pattern string into a SchedulePattern."""
    raw = raw.strip()

    # every_Nh
    m = _EVERY_RE.match(raw)
    if m:
        hours = int(m.group(1))
        if hours < 1 or hours > 168:
            raise ValueError(f"Invalid interval hours: {hours} (must be 1-168)")
        return SchedulePattern(
            pattern_type=PATTERN_EVERY, raw=raw, interval_hours=hours,
        )

    # daily_at HH:MM
    m = _DAILY_RE.match(raw)
    if m:
        time_str = m.group(1)
        _parse_time(time_str)  # validate
        return SchedulePattern(
            pattern_type=PATTERN_DAILY, raw=raw, time_str=time_str,
        )

    # weekly_on dayname HH:MM
    m = _WEEKLY_RE.match(raw)
    if m:
        day_name = m.group(1).lower()
        time_str = m.group(2)
        if day_name not in _DAY_MAP:
            raise ValueError(f"Invalid day of week: {day_name}")
        _parse_time(time_str)  # validate
        return SchedulePattern(
            pattern_type=PATTERN_WEEKLY, raw=raw,
            time_str=time_str, day_of_week=_DAY_MAP[day_name],
        )

    raise ValueError(f"Unrecognized schedule pattern: {raw!r}")


def _parse_time(time_str: str) -> time:
    """Parse HH:MM into a time object."""
    parts = time_str.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time format: {time_str}")
    h, m = int(parts[0]), int(parts[1])
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"Invalid time: {time_str}")
    return time(h, m)


# ─── Next Occurrence Calculator ────────────────────────────

def next_occurrence(entry: ScheduleEntry, after: datetime) -> datetime:
    """
    Compute the next fire time for a schedule entry after the given datetime.
    All calculations respect the entry's timezone.
    """
    try:
        tz = ZoneInfo(entry.timezone)
    except Exception:
        tz = ZoneInfo("UTC")

    # Convert 'after' to entry's timezone
    after_local = after.astimezone(tz)
    pattern = entry.pattern

    if pattern.pattern_type == PATTERN_EVERY:
        # Interval-based: fire every N hours from midnight of the day
        # Anchor to midnight of today in the entry's timezone
        midnight = after_local.replace(hour=0, minute=0, second=0, microsecond=0)
        interval = timedelta(hours=pattern.interval_hours)
        # Find next slot after 'after_local'
        candidate = midnight
        while candidate <= after_local:
            candidate += interval
        return candidate.astimezone(timezone.utc)

    elif pattern.pattern_type == PATTERN_DAILY:
        target_time = _parse_time(pattern.time_str)
        candidate = after_local.replace(
            hour=target_time.hour, minute=target_time.minute,
            second=0, microsecond=0,
        )
        if candidate <= after_local:
            candidate += timedelta(days=1)
        return candidate.astimezone(timezone.utc)

    elif pattern.pattern_type == PATTERN_WEEKLY:
        target_time = _parse_time(pattern.time_str)
        target_dow = pattern.day_of_week
        current_dow = after_local.weekday()

        days_ahead = target_dow - current_dow
        if days_ahead < 0:
            days_ahead += 7

        candidate = after_local.replace(
            hour=target_time.hour, minute=target_time.minute,
            second=0, microsecond=0,
        ) + timedelta(days=days_ahead)

        if candidate <= after_local:
            candidate += timedelta(weeks=1)

        return candidate.astimezone(timezone.utc)

    raise ValueError(f"Unknown pattern type: {pattern.pattern_type}")


# ─── Schedule Cache Singleton ──────────────────────────────

class ScheduleCache:
    """
    In-memory cache of schedule entries loaded from pack manifests.
    Provides query methods for due entries and upcoming events.
    """

    def __init__(self):
        self._entries: dict[str, list[ScheduleEntry]] = {}  # pack_id -> entries
        self._all_entries: list[ScheduleEntry] = []

    def load_from_manifests(self, packs: dict) -> int:
        """
        Load schedule entries from pack manifests.

        Args:
            packs: dict of {pack_id: PackLoader} instances

        Returns:
            Total number of schedule entries loaded.
        """
        from config import TIMEKEEPER_MAX_SCHEDULE_ENTRIES

        self._entries.clear()
        self._all_entries.clear()
        total = 0

        for pack_id, pack in packs.items():
            try:
                schedule_section = self._get_schedule_section(pack)
                if not schedule_section:
                    continue

                entries_data = schedule_section.get("entries", [])
                pack_tz = schedule_section.get("timezone", "UTC")
                pack_entries = []

                for entry_data in entries_data:
                    if total >= TIMEKEEPER_MAX_SCHEDULE_ENTRIES:
                        logger.warning(
                            "Schedule cache: max entries (%d) reached, skipping remaining",
                            TIMEKEEPER_MAX_SCHEDULE_ENTRIES,
                        )
                        break

                    try:
                        entry = self._parse_entry(pack_id, entry_data, pack_tz)
                        pack_entries.append(entry)
                        total += 1
                    except (ValueError, KeyError) as e:
                        logger.warning(
                            "Schedule cache: invalid entry in pack %s: %s", pack_id, e
                        )

                # Load outbound send templates as schedule entries
                outbound_entries = self._load_outbound_templates(
                    pack_id, pack, schedule_section.get("timezone", "UTC"),
                )
                for oe in outbound_entries:
                    if total >= TIMEKEEPER_MAX_SCHEDULE_ENTRIES:
                        break
                    pack_entries.append(oe)
                    total += 1

                if pack_entries:
                    self._entries[pack_id] = pack_entries
                    self._all_entries.extend(pack_entries)
                    logger.debug(
                        "Schedule cache: loaded %d entries for pack %s",
                        len(pack_entries), pack_id,
                    )

            except Exception as e:
                logger.warning("Schedule cache: failed to load pack %s: %s", pack_id, e)

        logger.info("Schedule cache: %d total entries from %d packs", total, len(self._entries))
        return total

    def _get_schedule_section(self, pack) -> dict:
        """Extract schedule section from a pack (PackLoader or dict)."""
        if hasattr(pack, "manifest"):
            return pack.manifest.get("schedule", {})
        if isinstance(pack, dict):
            return pack.get("schedule", {})
        return {}

    def _parse_entry(self, pack_id: str, data: dict, default_tz: str) -> ScheduleEntry:
        """Parse a single schedule entry from manifest data."""
        entry_id = data["id"]
        action = data.get("action", "notify")
        if action not in ("pause", "play", "stop", "notify", "initiate", "send"):
            raise ValueError(f"Invalid schedule action: {action}")

        pattern = parse_pattern(data["pattern"])
        tz = data.get("timezone", default_tz)
        reason = data.get("reason", "")
        enabled = data.get("enabled", True)

        initiate_for = data.get("initiate_for", "")

        return ScheduleEntry(
            pack_id=pack_id,
            entry_id=entry_id,
            action=action,
            pattern=pattern,
            timezone=tz,
            reason=reason,
            enabled=enabled,
            initiate_for=initiate_for,
        )

    def _load_outbound_templates(
        self, pack_id: str, pack, default_tz: str,
    ) -> list[ScheduleEntry]:
        """Parse outbound manifest section for schedule-triggered send templates."""
        entries = []
        try:
            if hasattr(pack, "manifest"):
                outbound = pack.manifest.get("outbound", {})
            elif isinstance(pack, dict):
                outbound = pack.get("outbound", {})
            else:
                return entries

            templates = outbound.get("templates", [])
            for tmpl in templates:
                if tmpl.get("trigger") != "schedule":
                    continue
                pattern_str = tmpl.get("pattern", "")
                if not pattern_str:
                    continue
                try:
                    pattern = parse_pattern(pattern_str)
                    entry = ScheduleEntry(
                        pack_id=pack_id,
                        entry_id=f"outbound_{tmpl.get('id', 'unknown')}",
                        action="send",
                        pattern=pattern,
                        timezone=tmpl.get("timezone", default_tz),
                        reason=tmpl.get("reason", "Scheduled outbound send"),
                        enabled=tmpl.get("enabled", True),
                        initiate_for=tmpl.get("target", ""),
                    )
                    entries.append(entry)
                except (ValueError, KeyError) as e:
                    logger.warning(
                        "Schedule cache: invalid outbound template in pack %s: %s",
                        pack_id, e,
                    )
        except Exception as e:
            logger.debug("Schedule cache: outbound parse error for %s: %s", pack_id, e)
        return entries

    def get_entries_for_pack(self, pack_id: str) -> list[ScheduleEntry]:
        """Get all schedule entries for a specific pack."""
        return list(self._entries.get(pack_id, []))

    def get_due_entries(self, now: datetime) -> list[tuple[ScheduleEntry, datetime]]:
        """
        Get all entries whose next occurrence is at or before `now`.

        Returns list of (entry, next_fire_time) tuples for entries that are due.
        Only returns enabled entries.
        """
        due = []
        for entry in self._all_entries:
            if not entry.enabled:
                continue
            try:
                # Use _last_fired or 1 hour ago as the reference point
                reference = entry._last_fired or (now - timedelta(hours=1))
                nxt = next_occurrence(entry, reference)
                if nxt <= now:
                    due.append((entry, nxt))
            except Exception as e:
                logger.debug("Schedule eval error for %s/%s: %s", entry.pack_id, entry.entry_id, e)
        return due

    def get_upcoming(self, pack_id: str, now: datetime, limit: int = 3) -> list[dict]:
        """
        Get the next N upcoming schedule events for a pack.
        Returns list of {entry_id, action, reason, next_at} dicts.
        """
        entries = self.get_entries_for_pack(pack_id)
        upcoming = []

        for entry in entries:
            if not entry.enabled:
                continue
            try:
                nxt = next_occurrence(entry, now)
                upcoming.append({
                    "entry_id": entry.entry_id,
                    "action": entry.action,
                    "reason": entry.reason,
                    "next_at": nxt.isoformat(),
                    "timezone": entry.timezone,
                })
            except Exception:
                continue

        # Sort by next_at
        upcoming.sort(key=lambda x: x["next_at"])
        return upcoming[:limit]

    def mark_fired(self, entry: ScheduleEntry, fired_at: datetime) -> None:
        """Record that an entry has fired (prevents re-firing within the same cycle)."""
        entry._last_fired = fired_at

    @property
    def total_entries(self) -> int:
        return len(self._all_entries)

    @property
    def pack_count(self) -> int:
        return len(self._entries)


# ─── Singleton ─────────────────────────────────────────────

_schedule_cache: Optional[ScheduleCache] = None


def init_schedule_cache() -> ScheduleCache:
    """Initialize the global schedule cache. Called during app lifespan."""
    global _schedule_cache
    _schedule_cache = ScheduleCache()
    logger.info("TimeKeeper schedule cache initialized")
    return _schedule_cache


def get_schedule_cache() -> Optional[ScheduleCache]:
    """Get the global schedule cache instance."""
    return _schedule_cache
