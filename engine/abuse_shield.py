"""
TMOS13 Abuse Shield — Anti-Abuse & Bot Detection

Comprehensive anti-abuse system for public chat widgets. Protects against
recursive bot spam, session flooding, and token exhaustion attacks.

Ships dark by default: all protections are permissive/off so the demo
experience is unchanged. Full machinery is toggleable per-account and
per-pack via feature flags and a dashboard API.

Architecture:
    1. ProtectionProfile — bundle of anti-abuse settings, resolved per-request
    2. Profile Resolution Chain — system defaults → pack overrides → account overrides → feature flags
    3. IPState / SessionBehavior — in-memory tracking with optional Redis backing
    4. ShieldVerdict — action result from evaluate() (allow/throttle/challenge/block/tarpit)
    5. AbuseEventLogger — structured logging + optional Supabase persistence
    6. Background cleanup coroutine for stale state pruning
"""
import asyncio
import hashlib
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger("tmos13.abuse_shield")


# ─── Protection Profile ───────────────────────────────────

@dataclass
class ProtectionProfile:
    """Bundle of anti-abuse settings. Resolved per-request by merging layers."""

    # Identity / gating
    require_turnstile: bool = False
    allow_automated_clients: bool = True   # True = demo/open mode
    require_email_after_n_turns: int = 0   # 0 = never require

    # Rate limits
    max_messages_per_minute: int = 10
    max_messages_per_session: int = 200
    max_sessions_per_ip_per_hour: int = 50
    max_daily_tokens_per_ip: int = 500_000

    # Behavioral analysis
    enable_timing_analysis: bool = False
    enable_coherence_scoring: bool = False
    min_inter_message_ms: int = 0          # 0 = no floor

    # Response mode on detection
    bot_response_mode: str = "allow"       # allow | throttle | challenge | block | tarpit

    # Cost controls
    session_token_budget: int = 0          # 0 = unlimited
    daily_account_spend_cap_cents: int = 0 # 0 = unlimited


# System defaults — permissive baseline (everything open for demo)
SYSTEM_DEFAULTS = ProtectionProfile()


def _merge_profile(base: ProtectionProfile, overrides: dict) -> ProtectionProfile:
    """Merge a dict of overrides onto a base profile. Only set keys override."""
    merged = ProtectionProfile(**{k: getattr(base, k) for k in base.__dataclass_fields__})
    valid_fields = set(ProtectionProfile.__dataclass_fields__.keys())
    for key, value in overrides.items():
        if key in valid_fields and value is not None:
            setattr(merged, key, value)
    return merged


def get_protection_profile(
    pack_id: str,
    account_id: Optional[str] = None,
) -> ProtectionProfile:
    """
    Resolve the effective protection profile by merging layers:
      1. System defaults (permissive baseline)
      2. Pack-level overrides (from manifest.json 'security' key)
      3. Account-level overrides (from protection_profiles store)
      4. Feature flag overrides (master switches can force-disable)
    """
    profile = ProtectionProfile(**asdict(SYSTEM_DEFAULTS))

    # Layer 2: Pack-level overrides
    try:
        from config import get_pack
        pack = get_pack(pack_id)
        if pack:
            manifest = pack.manifest if hasattr(pack, "manifest") else {}
            security_overrides = manifest.get("security", {})
            if security_overrides:
                profile = _merge_profile(profile, security_overrides)
    except Exception:
        logger.debug(f"Could not load pack overrides for {pack_id}")

    # Layer 3: Account-level overrides
    if account_id and account_id in _account_profiles:
        profile = _merge_profile(profile, _account_profiles[account_id])

    # Layer 4: Feature flag overrides
    profile = _apply_flag_overrides(profile)

    return profile


def _apply_flag_overrides(profile: ProtectionProfile) -> ProtectionProfile:
    """Apply feature flag master switches to force-disable features."""
    try:
        from feature_flags import FeatureFlagService
        # Use local flag defaults — we don't have user context here
        flag_svc = _flag_service
        if flag_svc is None:
            return profile

        if not flag_svc.get_flag("turnstile_enabled", default=False):
            profile.require_turnstile = False

        if not flag_svc.get_flag("behavioral_analysis", default=False):
            profile.enable_timing_analysis = False
            profile.enable_coherence_scoring = False

        if not flag_svc.get_flag("cost_circuit_breakers", default=False):
            profile.session_token_budget = 0
            profile.daily_account_spend_cap_cents = 0

    except Exception:
        pass  # Feature flag service not available — no overrides
    return profile


# ─── Tracking State ──────────────────────────────────────

def _hash_ip(ip: str) -> str:
    """SHA-256 hash an IP address. Raw IPs are never stored."""
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()[:32]


@dataclass
class IPState:
    """Per-IP tracking for cross-session abuse detection."""
    sessions_created: list = field(default_factory=list)  # timestamps
    messages_sent: list = field(default_factory=list)      # timestamps
    tokens_consumed_today: int = 0
    daily_reset: float = 0.0   # timestamp of last daily reset


@dataclass
class SessionBehavior:
    """Per-session behavioral signals for bot detection."""
    message_timestamps: list = field(default_factory=list)
    message_lengths: list = field(default_factory=list)
    inter_message_deltas: list = field(default_factory=list)  # ms between messages
    bot_probability: float = 0.0   # rolling estimate 0.0-1.0
    total_tokens: int = 0


# In-memory state stores (thread-safe via GIL for single-process)
_ip_states: dict[str, IPState] = {}
_session_behaviors: dict[str, SessionBehavior] = {}
_account_profiles: dict[str, dict] = {}  # account_id → override dict


def _get_ip_state(ip_hash: str) -> IPState:
    """Get or create IP state for a hashed IP."""
    if ip_hash not in _ip_states:
        _ip_states[ip_hash] = IPState()
    state = _ip_states[ip_hash]
    # Daily reset check
    now = time.time()
    day_start = now - (now % 86400)
    if state.daily_reset < day_start:
        state.tokens_consumed_today = 0
        state.daily_reset = now
    return state


def _get_session_behavior(session_id: str) -> SessionBehavior:
    """Get or create session behavior tracker."""
    if session_id not in _session_behaviors:
        _session_behaviors[session_id] = SessionBehavior()
    return _session_behaviors[session_id]


# ─── Verdict System ──────────────────────────────────────

@dataclass
class ShieldVerdict:
    """Result of abuse shield evaluation."""
    action: str             # "allow" | "throttle" | "challenge" | "block" | "tarpit"
    reason: str = ""
    delay_seconds: float = 0.0       # for throttle
    challenge_type: str = ""         # for challenge (e.g., "turnstile", "email")
    log_event: bool = True


VERDICT_ALLOW = ShieldVerdict(action="allow", log_event=False)


# ─── Main Evaluation Function ────────────────────────────

async def evaluate(
    session_id: str,
    ip: str,
    pack_id: str,
    account_id: Optional[str] = None,
    fingerprint: Optional[str] = None,   # Turnstile token
    message_length: int = 0,
    timestamp: Optional[float] = None,
) -> ShieldVerdict:
    """
    Evaluate a request against abuse protections.

    Checks in order (short-circuits on first failure):
      1. Master switch (abuse_shield_enabled flag)
      2. Resolve protection profile
      3. Turnstile validation
      4. Per-session message rate (messages per minute)
      5. Per-session total messages
      6. Per-IP session creation rate
      7. Per-IP daily token budget
      8. Behavioral timing analysis
      9. Session token budget
     10. Account spend cap
    """
    ts = timestamp or time.time()

    # 1. Master switch — if off, always allow
    if not _shield_enabled:
        return VERDICT_ALLOW

    # 2. Resolve protection profile
    profile = get_protection_profile(pack_id, account_id)

    ip_hash = _hash_ip(ip)
    ip_state = _get_ip_state(ip_hash)
    behavior = _get_session_behavior(session_id)

    # 3. Turnstile validation
    if profile.require_turnstile and not fingerprint:
        verdict = ShieldVerdict(
            action="challenge",
            reason="Turnstile verification required",
            challenge_type="turnstile",
        )
        _log_event("challenge_required", session_id, ip_hash, pack_id, verdict.reason)
        return verdict

    if profile.require_turnstile and fingerprint:
        valid = await _verify_turnstile(fingerprint, ip)
        if not valid:
            verdict = ShieldVerdict(
                action="block",
                reason="Turnstile verification failed",
            )
            _log_event("turnstile_failed", session_id, ip_hash, pack_id, verdict.reason)
            return verdict

    # 4. Per-session message rate (messages per minute)
    window_start = ts - 60.0
    recent_msgs = [t for t in behavior.message_timestamps if t > window_start]
    if len(recent_msgs) >= profile.max_messages_per_minute:
        verdict = _resolve_bot_response(
            profile,
            f"Rate limit exceeded: {len(recent_msgs)}/{profile.max_messages_per_minute} messages/minute",
        )
        _log_event("rate_limit_session_rpm", session_id, ip_hash, pack_id, verdict.reason)
        return verdict

    # 5. Per-session total messages
    if profile.max_messages_per_session > 0 and len(behavior.message_timestamps) >= profile.max_messages_per_session:
        verdict = ShieldVerdict(
            action="block",
            reason=f"Session message limit reached: {profile.max_messages_per_session}",
        )
        _log_event("session_message_limit", session_id, ip_hash, pack_id, verdict.reason)
        return verdict

    # 6. Per-IP session creation rate
    ip_sessions_hour = [t for t in ip_state.sessions_created if t > ts - 3600]
    if len(ip_sessions_hour) > profile.max_sessions_per_ip_per_hour:
        verdict = _resolve_bot_response(
            profile,
            f"IP session rate exceeded: {len(ip_sessions_hour)}/{profile.max_sessions_per_ip_per_hour} sessions/hour",
        )
        _log_event("ip_session_flood", session_id, ip_hash, pack_id, verdict.reason)
        return verdict

    # 7. Per-IP daily token budget
    if profile.max_daily_tokens_per_ip > 0 and ip_state.tokens_consumed_today >= profile.max_daily_tokens_per_ip:
        verdict = ShieldVerdict(
            action="block",
            reason=f"Daily token budget exhausted: {ip_state.tokens_consumed_today}/{profile.max_daily_tokens_per_ip}",
        )
        _log_event("ip_token_budget", session_id, ip_hash, pack_id, verdict.reason)
        return verdict

    # 8. Behavioral timing analysis
    if profile.enable_timing_analysis and len(behavior.inter_message_deltas) >= 3:
        bot_prob = _compute_bot_probability(behavior, profile)
        behavior.bot_probability = bot_prob
        if bot_prob > 0.8:
            verdict = _resolve_bot_response(
                profile,
                f"Bot behavior detected (probability: {bot_prob:.2f})",
            )
            _log_event("bot_detected", session_id, ip_hash, pack_id, verdict.reason)
            return verdict

    # Minimum inter-message timing
    if profile.min_inter_message_ms > 0 and behavior.message_timestamps:
        delta_ms = (ts - behavior.message_timestamps[-1]) * 1000
        if delta_ms < profile.min_inter_message_ms:
            verdict = ShieldVerdict(
                action="throttle",
                reason=f"Message too fast: {delta_ms:.0f}ms < {profile.min_inter_message_ms}ms minimum",
                delay_seconds=(profile.min_inter_message_ms - delta_ms) / 1000.0,
            )
            _log_event("timing_floor", session_id, ip_hash, pack_id, verdict.reason)
            return verdict

    # 9. Session token budget
    if profile.session_token_budget > 0 and behavior.total_tokens >= profile.session_token_budget:
        verdict = ShieldVerdict(
            action="block",
            reason=f"Session token budget exhausted: {behavior.total_tokens}/{profile.session_token_budget}",
        )
        _log_event("session_token_budget", session_id, ip_hash, pack_id, verdict.reason)
        return verdict

    # 10. Account spend cap
    if profile.daily_account_spend_cap_cents > 0 and account_id:
        spend = _account_daily_spend.get(account_id, 0)
        if spend >= profile.daily_account_spend_cap_cents:
            verdict = ShieldVerdict(
                action="block",
                reason=f"Daily account spend cap reached: {spend}/{profile.daily_account_spend_cap_cents} cents",
            )
            _log_event("account_spend_cap", session_id, ip_hash, pack_id, verdict.reason)
            return verdict

    # All checks passed — record the message and allow
    behavior.message_timestamps.append(ts)
    behavior.message_lengths.append(message_length)
    if len(behavior.message_timestamps) > 1:
        delta = (ts - behavior.message_timestamps[-2]) * 1000
        behavior.inter_message_deltas.append(delta)

    ip_state.messages_sent.append(ts)

    return VERDICT_ALLOW


def _resolve_bot_response(profile: ProtectionProfile, reason: str) -> ShieldVerdict:
    """Map bot_response_mode to a ShieldVerdict."""
    mode = profile.bot_response_mode
    if mode == "block":
        return ShieldVerdict(action="block", reason=reason)
    elif mode == "throttle":
        return ShieldVerdict(action="throttle", reason=reason, delay_seconds=2.0)
    elif mode == "challenge":
        return ShieldVerdict(action="challenge", reason=reason, challenge_type="turnstile")
    elif mode == "tarpit":
        return ShieldVerdict(action="tarpit", reason=reason, delay_seconds=10.0)
    else:  # "allow" or unknown — default allow
        return ShieldVerdict(action="allow", reason=reason, log_event=True)


def _compute_bot_probability(behavior: SessionBehavior, profile: ProtectionProfile) -> float:
    """
    Estimate bot probability from behavioral signals.

    Heuristics:
      - Very consistent inter-message timing (low coefficient of variation)
      - Very consistent message lengths
      - Extremely fast messages (< 500ms)
    """
    deltas = behavior.inter_message_deltas[-20:]  # last 20 deltas
    if not deltas:
        return 0.0

    signals = []

    # Signal 1: Timing consistency (bots have very regular timing)
    avg_delta = sum(deltas) / len(deltas)
    if avg_delta > 0:
        variance = sum((d - avg_delta) ** 2 for d in deltas) / len(deltas)
        cv = (variance ** 0.5) / avg_delta  # coefficient of variation
        # CV < 0.1 means extremely consistent timing
        if cv < 0.05:
            signals.append(1.0)
        elif cv < 0.1:
            signals.append(0.8)
        elif cv < 0.2:
            signals.append(0.4)
        else:
            signals.append(0.0)
    else:
        signals.append(0.0)

    # Signal 2: Speed (average delta < 500ms is suspicious)
    if avg_delta < 200:
        signals.append(1.0)
    elif avg_delta < 500:
        signals.append(0.7)
    elif avg_delta < 1000:
        signals.append(0.3)
    else:
        signals.append(0.0)

    # Signal 3: Message length consistency
    lengths = behavior.message_lengths[-20:]
    if len(lengths) >= 3:
        avg_len = sum(lengths) / len(lengths)
        if avg_len > 0:
            len_var = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
            len_cv = (len_var ** 0.5) / avg_len
            if len_cv < 0.05:
                signals.append(0.8)
            elif len_cv < 0.15:
                signals.append(0.4)
            else:
                signals.append(0.0)
        else:
            signals.append(0.0)

    if not signals:
        return 0.0

    return sum(signals) / len(signals)


# ─── Token Reporting ─────────────────────────────────────

def report_tokens(session_id: str, ip: str, tokens_used: int) -> None:
    """Report token usage for a completed request. Called after LLM response."""
    if not _shield_enabled:
        return

    ip_hash = _hash_ip(ip)
    ip_state = _get_ip_state(ip_hash)
    ip_state.tokens_consumed_today += tokens_used

    behavior = _get_session_behavior(session_id)
    behavior.total_tokens += tokens_used

    # Track account daily spend (rough estimate: 1 token ≈ $0.003/1000 tokens ≈ 0.3 cents / 1000)
    # This is a placeholder — real cost tracking would use actual API pricing


def record_session_creation(ip: str) -> None:
    """Record that a new session was created from this IP."""
    if not _shield_enabled:
        return
    ip_hash = _hash_ip(ip)
    ip_state = _get_ip_state(ip_hash)
    ip_state.sessions_created.append(time.time())


# ─── Turnstile Verification ─────────────────────────────

async def _verify_turnstile(token: str, ip: str) -> bool:
    """Verify a Cloudflare Turnstile token against their API."""
    try:
        from config import TURNSTILE_SECRET_KEY
        if not TURNSTILE_SECRET_KEY:
            logger.warning("Turnstile secret key not configured — accepting all tokens")
            return True

        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={
                    "secret": TURNSTILE_SECRET_KEY,
                    "response": token,
                    "remoteip": ip,
                },
            )
            result = resp.json()
            return result.get("success", False)

    except Exception as e:
        logger.warning(f"Turnstile verification error: {e}")
        return True  # Fail open — don't block users due to verification errors


# ─── Abuse Event Logger ─────────────────────────────────

_abuse_events: list[dict] = []  # In-memory ring buffer
_MAX_EVENTS = 10_000
_abuse_counters: dict[str, int] = defaultdict(int)


def _log_event(
    event_type: str,
    session_id: str,
    ip_hash: str,
    pack_id: str,
    reason: str,
) -> None:
    """Log an abuse event to the structured logger and event store."""
    event = {
        "type": event_type,
        "session_id": session_id,
        "ip_hash": ip_hash,
        "pack_id": pack_id,
        "reason": reason,
        "timestamp": time.time(),
    }

    # Python logger (always)
    logger.warning(
        "Abuse event: type=%s session=%s ip_hash=%s pack=%s reason=%s",
        event_type, session_id, ip_hash[:12], pack_id, reason,
    )

    # In-memory ring buffer
    _abuse_events.append(event)
    if len(_abuse_events) > _MAX_EVENTS:
        _abuse_events.pop(0)

    # Counters for stats
    _abuse_counters[event_type] += 1

    # Supabase persistence (fire-and-forget)
    if _db is not None:
        try:
            _persist_event(event)
        except Exception:
            logger.debug("Failed to persist abuse event to database", exc_info=True)


def _persist_event(event: dict) -> None:
    """Write an abuse event to Supabase (if available)."""
    if _db is None:
        return
    try:
        if hasattr(_db, "_client"):
            _db._client.table("abuse_events").insert(event).execute()
    except Exception:
        pass  # Non-critical — events are always in memory


def get_events(
    limit: int = 50,
    event_type: Optional[str] = None,
    pack_id: Optional[str] = None,
) -> list[dict]:
    """Get recent abuse events with optional filters."""
    events = _abuse_events
    if event_type:
        events = [e for e in events if e["type"] == event_type]
    if pack_id:
        events = [e for e in events if e["pack_id"] == pack_id]
    return list(reversed(events[-limit:]))


def get_stats() -> dict:
    """Get abuse shield statistics."""
    return {
        "enabled": _shield_enabled,
        "total_events": len(_abuse_events),
        "counters": dict(_abuse_counters),
        "tracked_ips": len(_ip_states),
        "tracked_sessions": len(_session_behaviors),
    }


# ─── Account Profile Management ─────────────────────────

def get_account_overrides(account_id: str) -> dict:
    """Get account-level protection overrides."""
    return _account_profiles.get(account_id, {})


def set_account_overrides(account_id: str, overrides: dict) -> None:
    """Set account-level protection overrides."""
    valid_fields = set(ProtectionProfile.__dataclass_fields__.keys())
    cleaned = {k: v for k, v in overrides.items() if k in valid_fields}
    _account_profiles[account_id] = cleaned


def get_account_pack_overrides(account_id: str, pack_id: str) -> dict:
    """Get pack-specific overrides for an account."""
    key = f"{account_id}:{pack_id}"
    return _account_profiles.get(key, {})


def set_account_pack_overrides(account_id: str, pack_id: str, overrides: dict) -> None:
    """Set pack-specific overrides for an account."""
    valid_fields = set(ProtectionProfile.__dataclass_fields__.keys())
    cleaned = {k: v for k, v in overrides.items() if k in valid_fields}
    key = f"{account_id}:{pack_id}"
    _account_profiles[key] = cleaned


# ─── Background Cleanup ─────────────────────────────────

IP_STATE_MAX_AGE = 7200      # 2 hours
SESSION_BEHAVIOR_MAX_AGE = 7200  # 2 hours
CLEANUP_INTERVAL = 120       # 2 minutes


async def _cleanup_loop():
    """Background task: prune expired tracking state."""
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        try:
            now = time.time()
            cutoff = now - IP_STATE_MAX_AGE

            # Prune IP states with no recent activity
            stale_ips = [
                ip_hash for ip_hash, state in _ip_states.items()
                if not state.messages_sent or max(state.messages_sent) < cutoff
            ]
            for ip_hash in stale_ips:
                del _ip_states[ip_hash]

            # Prune stale session behaviors
            stale_sessions = [
                sid for sid, behavior in _session_behaviors.items()
                if not behavior.message_timestamps
                or max(behavior.message_timestamps) < cutoff
            ]
            for sid in stale_sessions:
                del _session_behaviors[sid]

            # Reset daily counters
            day_start = now - (now % 86400)
            for state in _ip_states.values():
                if state.daily_reset < day_start:
                    state.tokens_consumed_today = 0
                    state.daily_reset = now

            # Prune old events from ring buffer (keep last 24h)
            event_cutoff = now - 86400
            while _abuse_events and _abuse_events[0].get("timestamp", 0) < event_cutoff:
                _abuse_events.pop(0)

            if stale_ips or stale_sessions:
                logger.debug(
                    f"Abuse shield cleanup: pruned {len(stale_ips)} IP states, "
                    f"{len(stale_sessions)} session behaviors"
                )

        except Exception:
            logger.exception("Error in abuse shield cleanup task")


# ─── Module Initialization ───────────────────────────────

_shield_enabled: bool = False
_cache = None
_db = None
_flag_service = None
_cleanup_task = None
_account_daily_spend: dict[str, int] = defaultdict(int)  # account_id → cents spent today


def init(cache=None, db=None, flag_service=None) -> None:
    """
    Initialize the abuse shield.

    Args:
        cache: RedisCache instance for distributed state (optional)
        db: Database instance for event persistence (optional)
        flag_service: FeatureFlagService for flag overrides (optional)
    """
    global _shield_enabled, _cache, _db, _flag_service

    _cache = cache
    _db = db
    _flag_service = flag_service

    # Check master switch
    try:
        from config import ABUSE_SHIELD_ENABLED
        _shield_enabled = ABUSE_SHIELD_ENABLED
    except ImportError:
        _shield_enabled = False

    # Override from feature flags if available
    if _flag_service:
        try:
            flag_val = _flag_service.get_flag("abuse_shield_enabled", default=False)
            if flag_val:
                _shield_enabled = True
        except Exception:
            pass

    logger.info(f"Abuse Shield initialized: enabled={_shield_enabled}")


def start_cleanup_task() -> Optional[asyncio.Task]:
    """Start the background cleanup coroutine. Returns the task handle."""
    global _cleanup_task
    _cleanup_task = asyncio.create_task(_cleanup_loop())
    return _cleanup_task


def stop_cleanup_task() -> None:
    """Cancel the background cleanup task."""
    global _cleanup_task
    if _cleanup_task:
        _cleanup_task.cancel()
        _cleanup_task = None


def reset() -> None:
    """Reset all state (for testing)."""
    global _shield_enabled, _cache, _db, _flag_service, _cleanup_task
    _ip_states.clear()
    _session_behaviors.clear()
    _account_profiles.clear()
    _abuse_events.clear()
    _abuse_counters.clear()
    _account_daily_spend.clear()
    _shield_enabled = False
    _cache = None
    _db = None
    _flag_service = None
    _cleanup_task = None


def get_profile_with_sources(
    pack_id: str,
    account_id: Optional[str] = None,
) -> dict:
    """
    Get the fully-resolved profile plus source attribution for each field.

    Returns a dict like:
      {
        "profile": { ...ProtectionProfile fields... },
        "sources": { "require_turnstile": "system_default", "max_messages_per_minute": "pack", ... }
      }
    """
    sources = {}
    profile_dict = asdict(SYSTEM_DEFAULTS)

    # Mark all as system default initially
    for key in profile_dict:
        sources[key] = "system_default"

    # Layer 2: Pack overrides
    pack_overrides = {}
    try:
        from config import get_pack
        pack = get_pack(pack_id)
        if pack:
            manifest = pack.manifest if hasattr(pack, "manifest") else {}
            pack_overrides = manifest.get("security", {})
    except Exception:
        pass

    for key, value in pack_overrides.items():
        if key in profile_dict and value is not None:
            profile_dict[key] = value
            sources[key] = "pack"

    # Layer 3: Account overrides
    if account_id:
        account_overrides = _account_profiles.get(account_id, {})
        for key, value in account_overrides.items():
            if key in profile_dict and value is not None:
                profile_dict[key] = value
                sources[key] = "account"

    # Layer 4: Feature flag overrides (applied to the profile object)
    resolved = ProtectionProfile(**profile_dict)
    resolved = _apply_flag_overrides(resolved)
    final_dict = asdict(resolved)

    # Detect flag-forced changes
    for key in final_dict:
        if final_dict[key] != profile_dict[key]:
            sources[key] = "feature_flag"

    return {
        "profile": final_dict,
        "sources": sources,
    }
