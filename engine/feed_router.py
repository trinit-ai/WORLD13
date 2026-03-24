"""
TMOS13 Feed Router — Pattern-Based Query Intent Detection

Maps raw user queries to connector operations using regex pattern matching.
No manifest files, no pack dependency — this is a platform-level utility.

Routing tiers:
    1. Connector hint (explicit override from client)
    2. Pattern match (regex against FEED_INTENTS table)
    3. LLM fallback (lightweight classification for ambiguous queries)
    4. Unknown (no match)
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger("tmos13.feed.router")


@dataclass
class RouteResult:
    """Result of routing a feed query to a connector."""
    tier: int                      # 1=hint, 2=reserved, 3=pattern, 4=unknown
    tier_label: str = ""           # "connector_hint" | "pattern_match" | "llm_routing" | "unknown"
    connector: str = ""            # Connector name
    operation: str = ""            # Operation within the connector
    params: dict = field(default_factory=dict)
    pattern_matched: str = ""      # Regex that matched (tier 3)
    error: str = ""                # Error message (tier 4)


# ─── Intent Table ────────────────────────────────────────

def _extract_group(m: re.Match, idx: int = 1) -> str:
    """Safely extract a group from a regex match."""
    try:
        if m.lastindex and m.lastindex >= idx:
            return m.group(idx).strip()
    except (IndexError, AttributeError):
        pass
    return ""


FEED_INTENTS: list[dict[str, Any]] = [
    # ── Weather ──────────────────────────────────────────
    {
        "connector": "weather",
        "operation": "current",
        "patterns": [
            r"weather\s+(?:in\s+)?(.+)",
            r"(?:what'?s?\s+(?:the\s+)?)?(?:temperature|temp)\s+(?:in\s+)?(.+)",
            r"(?:is\s+it\s+)?(?:raining|snowing|sunny|cloudy|cold|hot|warm)\s+(?:in\s+)?(.+)",
            r"(?:do\s+i\s+need\s+(?:an?\s+)?(?:umbrella|jacket|coat))\s+(?:in\s+)?(.+)",
        ],
        "param_extract": lambda m: {"city": _extract_group(m, m.lastindex or 1)},
    },
    {
        "connector": "weather",
        "operation": "forecast",
        "patterns": [
            r"forecast\s+(?:for\s+)?(.+)",
            r"weather\s+(?:this\s+week|tomorrow|next\s+\w+)\s+(?:in\s+)?(.+)",
        ],
        "param_extract": lambda m: {"city": _extract_group(m, m.lastindex or 1)},
    },

    # ── Stocks ───────────────────────────────────────────
    {
        "connector": "stocks",
        "operation": "quote",
        "case_sensitive": True,  # Bare tickers must be uppercase: "AAPL" not "news"
        "patterns": [
            r"^([A-Z]{1,5})$",
            r"(?:what'?s?\s+)?([A-Z]{1,5})\s+(?:at|trading|price|worth|quote)",
            r"(?:stock|quote|price)\s+(?:for\s+)?([A-Z]{1,5})",
            r"how(?:'?s|\s+is)\s+([A-Z]{1,5})\s+(?:doing|trading|looking)",
        ],
        "param_extract": lambda m: {"symbol": _extract_group(m, 1)},
    },
    {
        "connector": "stocks",
        "operation": "search",
        "patterns": [
            r"(?:stock|ticker)\s+(?:for|of)\s+(.+)",
            r"(?:what'?s?\s+the\s+ticker\s+for)\s+(.+)",
        ],
        "param_extract": lambda m: {"keywords": _extract_group(m, 1)},
    },

    # ── News ─────────────────────────────────────────────
    {
        "connector": "news",
        "operation": "top_headlines",
        "patterns": [
            r"^(?:news|headlines|what'?s\s+happening)$",
            r"(?:top|latest|today'?s?)\s+(?:news|headlines)",
            r"(?:what'?s\s+(?:in\s+)?the\s+news)",
        ],
        "param_extract": lambda m: {},
    },
    {
        "connector": "news",
        "operation": "search",
        "patterns": [
            r"news\s+(?:about|on|for)\s+(.+)",
            r"(?:any|latest)\s+news\s+(?:about|on)\s+(.+)",
        ],
        "param_extract": lambda m: {"query": _extract_group(m, 1)},
    },

    # ── Time ─────────────────────────────────────────────
    {
        "connector": "time",
        "operation": "current",
        "patterns": [
            r"^(?:what\s+time\s+is\s+it)$",
            r"(?:what\s+)?time\s+(?:is\s+it\s+)?in\s+(.+)",
            r"(?:current\s+time)\s+(?:in\s+)?(.+)",
        ],
        "param_extract": lambda m: {"timezone_name": _extract_group(m, 1) or "UTC"},
    },

    # ── Web Search ───────────────────────────────────────
    {
        "connector": "web_search",
        "operation": "search",
        "patterns": [
            r"(?:search|google|look\s+up|find)\s+(?:for\s+)?(.+)",
            r"(?:search\s+the\s+web\s+for)\s+(.+)",
        ],
        "param_extract": lambda m: {"query": _extract_group(m, 1)},
    },

    # ── Email ────────────────────────────────────────────
    {
        "connector": "email",
        "operation": "inbox",
        "patterns": [
            r"^(?:email|inbox|mail|messages|my\s+(?:email|mail|messages))$",
            r"(?:check|show|open|read)\s+(?:my\s+)?(?:email|inbox|mail|messages)",
            r"(?:any\s+)?(?:new|unread)\s+(?:email|mail|messages)",
        ],
        "param_extract": lambda m: {},
    },
    {
        "connector": "email",
        "operation": "search",
        "patterns": [
            r"(?:email|mail)\s+(?:from|about|regarding)\s+(.+)",
            r"(?:search|find)\s+(?:email|mail)\s+(.+)",
        ],
        "param_extract": lambda m: {"query": _extract_group(m, 1)},
    },

    # ── Calendar ─────────────────────────────────────────
    {
        "connector": "calendar",
        "operation": "today",
        "patterns": [
            r"^(?:calendar|schedule|agenda|my\s+(?:calendar|schedule|day))$",
            r"(?:what'?s?\s+on\s+(?:my\s+)?(?:calendar|schedule|agenda))",
            r"(?:my|today'?s?)\s+(?:meetings|events|appointments|schedule)",
            r"(?:what\s+do\s+i\s+have\s+today)",
        ],
        "param_extract": lambda m: {},
    },
    {
        "connector": "calendar",
        "operation": "availability",
        "patterns": [
            r"(?:am\s+i\s+free|available)\s+(?:at\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
            r"(?:free\s+(?:at|around))\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
        ],
        "param_extract": lambda m: {"date": "today", "time": _extract_group(m, 1)},
    },

    # ── Contacts ─────────────────────────────────────────
    {
        "connector": "contacts",
        "operation": "search",
        "patterns": [
            r"(?:who\s+is)\s+(.+?)(?:\s+in\s+my\s+contacts)?$",
            r"(.+?)(?:'?s?)\s+(?:phone|number|email|contact\s+info)",
        ],
        "param_extract": lambda m: {"query": _extract_group(m, 1)},
    },

    # ── Reminders ────────────────────────────────────────
    {
        "connector": "reminders",
        "operation": "list",
        "patterns": [
            r"^(?:reminders|tasks|todos?|to-?dos?|my\s+(?:tasks|reminders|todos?))$",
            r"(?:show|list|check)\s+(?:my\s+)?(?:reminders|tasks|todos?)",
        ],
        "param_extract": lambda m: {},
    },
    {
        "connector": "reminders",
        "operation": "create",
        "patterns": [
            r"(?:remind\s+me\s+(?:to\s+)?|add\s+(?:a\s+)?(?:reminder|task|todo)\s*:?\s*)(.+)",
            r"(?:don'?t\s+(?:let\s+me\s+)?forget)\s+(?:to\s+)?(.+)",
        ],
        "param_extract": lambda m: {"title": _extract_group(m, 1)},
    },
]


# ─── Feed Router ─────────────────────────────────────────

class FeedRouter:
    """
    Routes raw queries to connectors using tiered intent detection.

    Tier 1: Explicit connector_hint from client
    Tier 3: Regex pattern matching against FEED_INTENTS
    Tier 4: Unknown / fallback
    """

    def __init__(self, intents: list[dict] | None = None):
        self.intents = intents or FEED_INTENTS
        # Pre-compile patterns for performance.
        # Patterns that need case-sensitivity (e.g. bare ticker ^([A-Z]{1,5})$)
        # should NOT have re.IGNORECASE. All other patterns get it.
        # Convention: patterns containing only [A-Z] character classes are case-sensitive.
        self._compiled: list[tuple[dict, list[re.Pattern]]] = []
        for intent in self.intents:
            compiled_patterns = []
            for p in intent["patterns"]:
                # If the pattern is purely uppercase letter matching, keep it case-sensitive
                if intent.get("case_sensitive"):
                    compiled_patterns.append(re.compile(p))
                else:
                    compiled_patterns.append(re.compile(p, re.IGNORECASE))
            self._compiled.append((intent, compiled_patterns))

    def route(self, query: str, connector_hint: str | None = None) -> RouteResult:
        """Route a query to the appropriate connector and operation."""
        query_clean = query.strip()

        # Tier 1: Explicit connector hint
        if connector_hint:
            return RouteResult(
                tier=1,
                tier_label="connector_hint",
                connector=connector_hint,
                operation="",  # let the connector figure it out
                params={"query": query_clean},
            )

        # Tier 3: Pattern match against FEED_INTENTS
        for intent, patterns in self._compiled:
            for pattern in patterns:
                match = pattern.match(query_clean)
                if match:
                    try:
                        params = intent["param_extract"](match)
                    except Exception:
                        params = {}
                    return RouteResult(
                        tier=3,
                        tier_label="pattern_match",
                        connector=intent["connector"],
                        operation=intent["operation"],
                        params=params,
                        pattern_matched=pattern.pattern,
                    )

        # Tier 4: Unknown
        return RouteResult(
            tier=4,
            tier_label="unknown",
            error="unknown_query",
        )
