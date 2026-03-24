"""
TMOS13 Response Parser

Reads LLM responses and extracts state signals. The model
embeds structured markers that the parser detects, keeping
server-side state in sync without requiring the model to
manage state directly.

The model is instructed to include these markers naturally
in its responses when relevant.
"""
import json
import logging
import re
from state import SessionState

logger = logging.getLogger("tmos13.parser")


# ─── State Signal Patterns ────────────────────────────────
# Claude embeds these in responses. Parser strips them before
# sending to the player (invisible scaffolding).

SIGNAL_PATTERNS = {
    r"\[MOOD:([\w]+)\]":             "mood",
    r"\[DEPTH=(\d)\]":              "depth_override",
    r"\[SAVE_STATE\]":              "save_state",
    r"\[RAIL_REQUEST(?::([\w]+))?\]": "rail_request",
    r"\[STATE:([\w.]+=[^\]]+)\]":     "state_flag",
    r"\[MOVE:([\w]+)\]":             "battle_move",
}

# ─── Robust STATE Signal Pattern ─────────────────────────
# Matches [STATE:key=value] where value can contain spaces,
# punctuation, and special characters — anything except ]
STATE_SIGNAL_PATTERN = re.compile(r'\[STATE:[^\]]+\]')

# ─── Profile Write Pattern ────────────────────────────────
# [PROFILE_WRITE:field=value] — Welcome pack writes profile data
_PROFILE_WRITE_RE = re.compile(r"\[PROFILE_WRITE:(\w+)=(.+?)\]")
_ALLOWED_PROFILE_FIELDS = frozenset({"display_name", "org_name", "title", "bio"})
# Map protocol field names to DB column names where they differ
_PROFILE_FIELD_MAP = {"org_name": "organization"}

# ─── Navigation Pattern ──────────────────────────────────
# [NAVIGATE:/url-path] — Triggers client-side navigation
_NAVIGATE_RE = re.compile(r"\[NAVIGATE:(\/[\w-]*)\]")

# ─── Tool Request Pattern ────────────────────────────────
# [TOOL_REQUEST: tool_id | operation | {json_params}]
_TOOL_REQUEST_RE = re.compile(
    r"\[TOOL_REQUEST:\s*(\w+)\s*\|\s*(\w+)\s*\|\s*(\{.*?\})\]",
    re.DOTALL,
)

# [REQUIRES_CONFIRMATION] — signals the model is asking user to confirm
_REQUIRES_CONFIRMATION_RE = re.compile(r"\[REQUIRES_CONFIRMATION\]")


def extract_state_signals(text: str) -> dict:
    """Extract all [STATE:key=value] signals from text. Returns dict of key->value."""
    signals = {}
    for match in STATE_SIGNAL_PATTERN.finditer(text):
        inner = match.group(0)[7:-1]  # strip [STATE: and ]
        if '=' in inner:
            key, _, value = inner.partition('=')
            signals[key.strip()] = value.strip()
    return signals


def strip_state_signals(text: str) -> str:
    """Remove all [STATE:key=value] signals from text before display."""
    stripped = STATE_SIGNAL_PATTERN.sub('', text)
    # Multiple spaces -> single space
    stripped = re.sub(r'  +', ' ', stripped)
    # Trailing whitespace on each line
    stripped = '\n'.join(line.rstrip() for line in stripped.split('\n'))
    # Multiple consecutive blank lines -> single blank line
    stripped = re.sub(r'\n{3,}', '\n\n', stripped)
    return stripped.strip()


def parse_response(response: str, state: SessionState) -> str:
    """
    Parse Claude's response for state signals, update state,
    and return the clean response (signals stripped).
    """
    clean = response

    # ─── Extract STATE signals first (robust pattern) ────────
    # Must happen before stripping so state is captured
    state_signals = extract_state_signals(response)
    if state_signals:
        if not hasattr(state, "_state_flags"):
            state._state_flags = {}
        for key, value in state_signals.items():
            state._state_flags[key] = value
            # Snapshot transcript when contact fields arrive via state signal
            _CONTACT_STATE_KEYS = {"contact_email", "contact_name", "contact_phone", "contact_company"}
            if key in _CONTACT_STATE_KEYS:
                dedup_flag = f"_transcript_logged_for_{key}"
                if not getattr(state, dedup_flag, False):
                    setattr(state, dedup_flag, True)
                    try:
                        import asyncio
                        from transcripts import log_transcript_for_contact
                        asyncio.get_event_loop().create_task(
                            asyncio.to_thread(log_transcript_for_contact, state.session_id, "state_signal")
                        )
                    except Exception:
                        pass

    for pattern, signal_type in SIGNAL_PATTERNS.items():
        matches = re.finditer(pattern, response)
        for match in matches:
            # Skip state_flag — already handled above with robust pattern
            if signal_type != "state_flag":
                _apply_signal(signal_type, match, state)
            # Strip the signal from the visible response
            clean = clean.replace(match.group(0), "")

    # ─── Strip any remaining STATE signals (robust pattern) ──
    # Catches signals the old SIGNAL_PATTERNS regex may have missed
    clean = strip_state_signals(clean)

    # ─── Profile Write Extraction ─────────────────────────────
    profile_updates = extract_profile_writes(clean)
    if profile_updates:
        state._pending_profile_updates = profile_updates
        clean = _PROFILE_WRITE_RE.sub("", clean)

    # ─── Navigation Extraction ────────────────────────────────
    nav_target = extract_navigation(clean)
    if nav_target is not None:
        state._pending_navigate_to = nav_target
        clean = _NAVIGATE_RE.sub("", clean)

    # ─── Tool Request Extraction ────────────────────────────
    tool_requests = extract_tool_requests(clean)
    if tool_requests:
        state._pending_tool_requests = tool_requests
        # Strip tool request signals from visible response
        clean = _TOOL_REQUEST_RE.sub("", clean)
        clean = _REQUIRES_CONFIRMATION_RE.sub("", clean)

    # Remove empty code blocks left after signal stripping
    clean = re.sub(r"```[a-z]*\s*```", "", clean)

    # Clean up any extra whitespace from stripped signals
    clean = re.sub(r"\n{3,}", "\n\n", clean).strip()

    return clean


def extract_profile_writes(text: str) -> dict:
    """
    Extract PROFILE_WRITE signals from model output.

    Returns dict of db_field -> value for allowed profile fields.
    Only permits known safe fields to prevent injection.
    Protocol names are mapped to DB column names (e.g. org_name → organization).
    """
    writes = {}
    for match in _PROFILE_WRITE_RE.finditer(text):
        field = match.group(1)
        value = match.group(2).strip()
        if field in _ALLOWED_PROFILE_FIELDS and value:
            db_field = _PROFILE_FIELD_MAP.get(field, field)
            writes[db_field] = value
    return writes


def extract_navigation(text: str) -> str | None:
    """
    Extract NAVIGATE signal from model output.

    Returns the target URL path (e.g. '/legal-intake') or None.
    Only the first NAVIGATE signal is used.
    """
    match = _NAVIGATE_RE.search(text)
    if match:
        return match.group(1)
    return None


def extract_tool_requests(text: str) -> list[dict]:
    """
    Extract TOOL_REQUEST signals from model output.

    Returns list of dicts: [{tool_id, operation, parameters, requires_confirmation}]
    One tool request per response is the safety design, but we parse all
    matches and only the first will be executed.
    """
    requests = []
    has_confirmation = bool(_REQUIRES_CONFIRMATION_RE.search(text))

    for match in _TOOL_REQUEST_RE.finditer(text):
        tool_id = match.group(1)
        operation = match.group(2)
        params_str = match.group(3)

        try:
            parameters = json.loads(params_str)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in TOOL_REQUEST params: {params_str[:100]}")
            parameters = {}

        requests.append({
            "tool_id": tool_id,
            "operation": operation,
            "parameters": parameters,
            "requires_confirmation": has_confirmation,
        })

    return requests


def _apply_signal(signal_type: str, match: re.Match, state: SessionState):
    """Apply a parsed signal to the session state."""
    if signal_type == "mood":
        state.mood = match.group(1).lower()
    elif signal_type == "depth_override":
        state.depth = int(match.group(1))
    elif signal_type == "save_state":
        state._save_state_requested = True
    elif signal_type == "rail_request":
        state._pending_rail_id = match.group(1) or "default"
    elif signal_type == "state_flag":
        # Generic state flag: [STATE:key=value]
        try:
            key, value = match.group(1).split("=", 1)
            if not hasattr(state, "_state_flags"):
                state._state_flags = {}
            state._state_flags[key] = value

            # Snapshot transcript when contact fields arrive via state signal
            _CONTACT_STATE_KEYS = {"contact_email", "contact_name", "contact_phone", "contact_company"}
            if key in _CONTACT_STATE_KEYS:
                dedup_flag = f"_transcript_logged_for_{key}"
                if not getattr(state, dedup_flag, False):
                    setattr(state, dedup_flag, True)
                    try:
                        import asyncio
                        from transcripts import log_transcript_for_contact
                        asyncio.get_event_loop().create_task(
                            asyncio.to_thread(log_transcript_for_contact, state.session_id, "state_signal")
                        )
                    except Exception:
                        pass
        except ValueError:
            pass
    elif signal_type == "battle_move":
        # Battle move signal: [MOVE:type] — stored temporarily, consumed by battle_service
        state.pending_battle_move = match.group(1).lower()


def detect_mood(user_input: str) -> str:
    """
    Mood detection from user input using word-boundary matching.
    Returns: curious | serious | playful | sad | intense

    Uses regex word boundaries to avoid false positives
    (e.g. "must" inside "mustard" won't trigger "intense").
    """
    lower = user_input.lower()

    def _has_word(words: list[str]) -> bool:
        return any(re.search(rf"\b{re.escape(w)}\b", lower) for w in words)

    # Sad indicators
    if _has_word(["sad", "hurt", "lonely", "lost", "miss", "grief", "cry", "pain", "struggle"]):
        return "sad"

    # Playful indicators (checked before intense — "fun" and "cool" are common)
    if _has_word(["haha", "lol", "lmao", "fun", "cool", "awesome", "wild", "crazy", "weird"]):
        return "playful"

    # Serious indicators
    if _has_word(["meaning", "purpose", "existence", "consciousness",
                  "death", "truth", "why do", "what is"]):
        return "serious"

    # Intense indicators (checked last — these overlap with normal speech)
    if _has_word(["urgent", "critical", "desperate", "need to"]):
        return "intense"

    return "curious"
