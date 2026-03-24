"""
TMOS13 Distillation Guard — Session Behavioral Fingerprinting

Detects industrial-scale protocol distillation attempts by analyzing session
behavioral patterns. Each exchange is fingerprinted against a set of heuristic
signals. When a session accumulates enough signals, it fires an alert and
optionally terminates the session.

Signals detected:
  - rapid_fire: Exchanges arriving faster than human typing speed
  - capability_probing: Requests that enumerate system capabilities
  - rubric_extraction: Attempts to extract scoring criteria or decision trees
  - system_prompt_fishing: Attempts to reveal system prompt content
  - format_mirroring: Responses echoed back as questions (prompt reflection)
  - off_protocol: Requests that steer conversation away from pack purpose
  - high_session_volume: User opens unusually many sessions in a window
  - high_exchange_volume: Session has unusually many exchanges
  - parallel_sessions: User has multiple concurrent sessions

Thresholds:
  - 3+ signals → distillation_warning alert
  - 5+ signals → auto-terminate session
"""
import logging
import re
import time
from dataclasses import dataclass, field

logger = logging.getLogger("tmos13.distillation")

# ─── Detection Patterns ────────────────────────────────

# Capability probing: requests that try to enumerate what the system can do
CAPABILITY_PROBE_PATTERNS = [
    re.compile(r"\b(?:list|enumerate|show|tell me)\b.*\b(?:all|every|each)\b.*\b(?:commands?|features?|capabilities?|functions?|options?|modes?)\b", re.I),
    re.compile(r"\bwhat (?:can|do) you (?:do|support|offer|handle)\b", re.I),
    re.compile(r"\b(?:full|complete|comprehensive) list of\b", re.I),
    re.compile(r"\bwhat (?:tools|actions|operations) (?:are|do you have)\b", re.I),
]

# Rubric extraction: attempts to surface decision logic or scoring criteria
RUBRIC_EXTRACTION_PATTERNS = [
    re.compile(r"\b(?:scoring|decision|evaluation|assessment) (?:criteria|rubric|matrix|framework|logic)\b", re.I),
    re.compile(r"\bhow do you (?:decide|score|evaluate|rate|rank|assess|determine)\b", re.I),
    re.compile(r"\bwhat (?:factors|criteria|rules|weights) do you (?:use|consider|apply)\b", re.I),
    re.compile(r"\bshow (?:me )?(?:the|your) (?:scoring|decision|rubric)\b", re.I),
    re.compile(r"\bexplain (?:the|your) (?:scoring|decision|evaluation) (?:process|methodology|approach)\b", re.I),
]

# System prompt fishing: attempts to reveal the system prompt
SYSTEM_PROMPT_PATTERNS = [
    re.compile(r"\b(?:system|initial|original|starting|hidden) (?:prompt|instruction|message|directive)\b", re.I),
    re.compile(r"\brepeat (?:the |your )?(?:system )?(?:instructions?|prompt|directives?)\b", re.I),
    re.compile(r"\bignore (?:previous|prior|above|all) (?:instructions?|directives?|rules?)\b", re.I),
    re.compile(r"\bprint (?:your|the) (?:system|initial|full) (?:prompt|instructions?)\b", re.I),
    re.compile(r"\bwhat (?:were|are) (?:your|the) (?:original|system|initial) (?:instructions?|rules?)\b", re.I),
    re.compile(r"\byou are now (?:a |an )?(?:different|new|unrestricted)\b", re.I),
    re.compile(r"\bpretend (?:you(?:'re| are) )?(?:a different|another|an unrestricted)\b", re.I),
    re.compile(r"\b(?:DAN|jailbreak|developer mode|god mode)\b", re.I),
]

# Format mirroring: response echoed back as a question (structural reflection)
FORMAT_MIRROR_PATTERNS = [
    re.compile(r"\bwhy did you (?:say|respond|answer|phrase it) (?:that|it) (?:that )?way\b", re.I),
    re.compile(r"\bwhat template (?:are you|did you) (?:using|use|follow(?:ing)?)\b", re.I),
    re.compile(r"\bwhat(?:'s| is) (?:your|the) (?:response |output )?(?:format|structure|template)\b", re.I),
    re.compile(r"\bgenerate (?:the same|a similar|an identical) (?:response|output|answer)\b", re.I),
]


# ─── Fingerprint ────────────────────────────────────────

@dataclass
class SessionFingerprint:
    """Accumulated behavioral signals for one session."""
    session_id: str = ""
    user_id: str = "anonymous"
    signals: list[str] = field(default_factory=list)
    exchange_timestamps: list[float] = field(default_factory=list)
    exchange_count: int = 0
    last_user_input: str = ""
    terminated: bool = False

    @property
    def signal_count(self) -> int:
        return len(set(self.signals))

    @property
    def should_alert(self) -> bool:
        return self.signal_count >= 3

    @property
    def should_terminate(self) -> bool:
        return self.signal_count >= 5


# ─── Global Fingerprint Store ──────────────────────────

# session_id → SessionFingerprint
_fingerprints: dict[str, SessionFingerprint] = {}

# user_id → list of (session_id, start_time)
_user_sessions: dict[str, list[tuple[str, float]]] = {}


def get_fingerprint(session_id: str) -> SessionFingerprint:
    """Get or create a fingerprint for a session."""
    if session_id not in _fingerprints:
        _fingerprints[session_id] = SessionFingerprint(session_id=session_id)
    return _fingerprints[session_id]


def register_session(session_id: str, user_id: str) -> None:
    """Register a new session for a user (for parallel session tracking)."""
    fp = get_fingerprint(session_id)
    fp.user_id = user_id
    if user_id not in _user_sessions:
        _user_sessions[user_id] = []
    _user_sessions[user_id].append((session_id, time.time()))


def close_session(session_id: str) -> None:
    """Clean up fingerprint when session closes."""
    fp = _fingerprints.pop(session_id, None)
    if fp and fp.user_id in _user_sessions:
        _user_sessions[fp.user_id] = [
            (sid, ts) for sid, ts in _user_sessions[fp.user_id]
            if sid != session_id
        ]


def reset_all() -> None:
    """Reset all fingerprints (for testing)."""
    _fingerprints.clear()
    _user_sessions.clear()


# ─── Signal Detection ──────────────────────────────────

def _detect_rapid_fire(fp: SessionFingerprint) -> bool:
    """Detect exchanges arriving faster than human typing speed (<2s intervals)."""
    if len(fp.exchange_timestamps) < 3:
        return False
    recent = fp.exchange_timestamps[-5:]
    intervals = [recent[i] - recent[i - 1] for i in range(1, len(recent))]
    fast_count = sum(1 for iv in intervals if iv < 2.0)
    return fast_count >= 2


def _detect_capability_probing(user_input: str) -> bool:
    """Detect capability enumeration attempts."""
    return any(p.search(user_input) for p in CAPABILITY_PROBE_PATTERNS)


def _detect_rubric_extraction(user_input: str) -> bool:
    """Detect attempts to extract decision logic or scoring criteria."""
    return any(p.search(user_input) for p in RUBRIC_EXTRACTION_PATTERNS)


def _detect_system_prompt_fishing(user_input: str) -> bool:
    """Detect attempts to reveal or override system prompt."""
    return any(p.search(user_input) for p in SYSTEM_PROMPT_PATTERNS)


def _detect_format_mirroring(user_input: str) -> bool:
    """Detect structural reflection / format extraction attempts."""
    return any(p.search(user_input) for p in FORMAT_MIRROR_PATTERNS)


def _compute_structural_similarity(a: str, b: str) -> float:
    """
    Compute structural similarity between two strings.
    Uses a simple line-structure comparison for speed.
    Returns a float 0.0-1.0.
    """
    if not a or not b:
        return 0.0
    lines_a = a.strip().split("\n")
    lines_b = b.strip().split("\n")
    if not lines_a or not lines_b:
        return 0.0
    # Compare line count ratio
    count_ratio = min(len(lines_a), len(lines_b)) / max(len(lines_a), len(lines_b))
    # Compare average line length ratio
    avg_a = sum(len(l) for l in lines_a) / len(lines_a) if lines_a else 0
    avg_b = sum(len(l) for l in lines_b) / len(lines_b) if lines_b else 0
    if max(avg_a, avg_b) == 0:
        return 0.0
    len_ratio = min(avg_a, avg_b) / max(avg_a, avg_b)
    return (count_ratio + len_ratio) / 2


def _detect_off_protocol(user_input: str, pack_id: str) -> bool:
    """
    Detect requests that steer conversation away from the pack's stated purpose.
    Uses simple keyword heuristics — not intended as a content classifier.
    """
    off_topic_indicators = [
        re.compile(r"\bforget (?:everything|all|about|the|your)\b", re.I),
        re.compile(r"\blet(?:'s| us) (?:talk|chat|discuss) about something (?:else|different)\b", re.I),
        re.compile(r"\bstop being\b.*\b(?:and|instead) be\b", re.I),
        re.compile(r"\b(?:act|behave|pretend) (?:as|like) (?:a |an )?(?:different|another)\b", re.I),
    ]
    return any(p.search(user_input) for p in off_topic_indicators)


def _detect_high_session_volume(user_id: str, window_seconds: int = 3600) -> bool:
    """Detect if a user has opened too many sessions in the last hour."""
    if user_id == "anonymous" or user_id not in _user_sessions:
        return False
    now = time.time()
    cutoff = now - window_seconds
    recent = [(sid, ts) for sid, ts in _user_sessions[user_id] if ts >= cutoff]
    _user_sessions[user_id] = recent  # prune old entries
    return len(recent) > 20


def _detect_high_exchange_volume(fp: SessionFingerprint) -> bool:
    """Detect sessions with unusually many exchanges."""
    return fp.exchange_count > 50


def _detect_parallel_sessions(user_id: str) -> bool:
    """Detect if user has 3+ concurrent sessions."""
    if user_id == "anonymous" or user_id not in _user_sessions:
        return False
    return len(_user_sessions[user_id]) >= 3


# ─── Main Analysis Entry Point ─────────────────────────

def analyze_session(
    session_id: str,
    user_input: str,
    pack_id: str = "",
    user_id: str = "anonymous",
    last_assistant_response: str = "",
) -> SessionFingerprint:
    """
    Analyze a single exchange for distillation signals.

    Called once per user exchange in the pipeline (after routing, before Claude call).
    Accumulates signals on the session fingerprint and returns it.

    Args:
        session_id: Current session ID
        user_input: The user's message text
        pack_id: Active pack ID (for off-protocol detection)
        user_id: User ID (for cross-session signals)
        last_assistant_response: Previous assistant response (for format mirroring)

    Returns:
        Updated SessionFingerprint with all detected signals
    """
    fp = get_fingerprint(session_id)
    fp.user_id = user_id
    fp.exchange_count += 1
    fp.exchange_timestamps.append(time.time())
    fp.last_user_input = user_input

    # ─── Per-exchange signals ─────────────────────────
    if _detect_rapid_fire(fp) and "rapid_fire" not in fp.signals:
        fp.signals.append("rapid_fire")
        logger.info("Signal: rapid_fire session=%s", session_id)

    if _detect_capability_probing(user_input) and "capability_probing" not in fp.signals:
        fp.signals.append("capability_probing")
        logger.info("Signal: capability_probing session=%s", session_id)

    if _detect_rubric_extraction(user_input) and "rubric_extraction" not in fp.signals:
        fp.signals.append("rubric_extraction")
        logger.info("Signal: rubric_extraction session=%s", session_id)

    if _detect_system_prompt_fishing(user_input) and "system_prompt_fishing" not in fp.signals:
        fp.signals.append("system_prompt_fishing")
        logger.info("Signal: system_prompt_fishing session=%s", session_id)

    if _detect_format_mirroring(user_input) and "format_mirroring" not in fp.signals:
        fp.signals.append("format_mirroring")
        logger.info("Signal: format_mirroring session=%s", session_id)

    if _detect_off_protocol(user_input, pack_id) and "off_protocol" not in fp.signals:
        fp.signals.append("off_protocol")
        logger.info("Signal: off_protocol session=%s", session_id)

    # ─── Volume / concurrency signals ─────────────────
    if _detect_high_session_volume(user_id) and "high_session_volume" not in fp.signals:
        fp.signals.append("high_session_volume")
        logger.info("Signal: high_session_volume user=%s", user_id)

    if _detect_high_exchange_volume(fp) and "high_exchange_volume" not in fp.signals:
        fp.signals.append("high_exchange_volume")
        logger.info("Signal: high_exchange_volume session=%s", session_id)

    if _detect_parallel_sessions(user_id) and "parallel_sessions" not in fp.signals:
        fp.signals.append("parallel_sessions")
        logger.info("Signal: parallel_sessions user=%s", user_id)

    # ─── Format mirroring via structural similarity ───
    if (
        last_assistant_response
        and "format_mirroring" not in fp.signals
        and _compute_structural_similarity(user_input, last_assistant_response) > 0.85
    ):
        fp.signals.append("format_mirroring")
        logger.info("Signal: format_mirroring (structural) session=%s", session_id)

    # Log threshold crossings
    if fp.should_terminate and not fp.terminated:
        fp.terminated = True
        logger.warning(
            "Distillation threshold TERMINATE: session=%s signals=%d (%s)",
            session_id, fp.signal_count, ", ".join(set(fp.signals)),
        )
    elif fp.should_alert:
        logger.warning(
            "Distillation threshold ALERT: session=%s signals=%d (%s)",
            session_id, fp.signal_count, ", ".join(set(fp.signals)),
        )

    return fp
