"""
TMOS13 Feed Portal — API Endpoints

POST /api/feed/query    — Route a raw query to a connector and return a typed card
GET  /api/feed/history  — Retrieve past feed cards for a feed session
GET  /api/feed/connectors — List available connectors and their status

This is NOT the chat endpoint. Key differences:
- No session_id required (optional for persistence)
- No assembler invocation (no system prompt, no protocol files)
- No rolling message history
- Returns a typed card object, not a prose response string
- LLM invocation is conditional, not guaranteed
"""
import logging
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Depends, FastAPI
from pydantic import BaseModel

from auth import require_auth, UserProfile
from errors import APIError, ErrorCode

logger = logging.getLogger("tmos13.feed")


# ─── Pydantic Models ─────────────────────────────────────

class FeedQueryOptions(BaseModel):
    include_metadata: bool = True
    llm_fallback: bool = True
    max_chain_depth: int = 3


class FeedQueryRequest(BaseModel):
    query: str
    feed_id: Optional[str] = None
    user_id: Optional[str] = None
    connector_hint: Optional[str] = None
    options: Optional[FeedQueryOptions] = None


class FeedQueryResponse(BaseModel):
    card: dict
    meta: dict


class FeedHistoryResponse(BaseModel):
    feed_id: str
    cards: list[dict]
    total: int
    has_more: bool


class FeedConnectorStatusResponse(BaseModel):
    name: str
    display_name: str
    icon: str
    source: str
    enabled: bool
    provider: str
    tier: str
    example_queries: list[str]
    rate_limit: Optional[str] = None


class FeedConnectorsResponse(BaseModel):
    connectors: list[FeedConnectorStatusResponse]


# ─── Connector Metadata (display info, icons, examples) ──

_CONNECTOR_META: dict[str, dict] = {
    "weather": {
        "display_name": "Weather",
        "icon": "cloud",
        "tier": "free",
        "example_queries": ["weather NYC", "forecast Chicago", "temp in London"],
        "rate_limit": "1,000 calls/day (OpenWeatherMap free tier)",
    },
    "stocks": {
        "display_name": "Stock Quotes",
        "icon": "trending-up",
        "tier": "free",
        "example_queries": ["AAPL", "stock price MSFT", "ticker for Tesla"],
        "rate_limit": "Unlimited (Yahoo Finance)",
    },
    "news": {
        "display_name": "News",
        "icon": "newspaper",
        "tier": "free",
        "example_queries": ["news", "news about AI", "latest headlines"],
        "rate_limit": "100 calls/day (NewsAPI) or unlimited (RSS)",
    },
    "time": {
        "display_name": "Time",
        "icon": "clock",
        "tier": "free",
        "example_queries": ["time in Tokyo", "what time is it", "time in PST"],
    },
    "web_search": {
        "display_name": "Web Search",
        "icon": "search",
        "tier": "premium",
        "example_queries": ["search for TMOS13", "look up FastAPI docs"],
    },
    "email": {
        "display_name": "Email",
        "icon": "mail",
        "tier": "premium",
        "example_queries": ["my email", "check inbox", "unread messages"],
    },
    "calendar": {
        "display_name": "Calendar",
        "icon": "calendar",
        "tier": "premium",
        "example_queries": ["my schedule", "calendar", "am I free at 3pm"],
    },
    "contacts": {
        "display_name": "Contacts",
        "icon": "user",
        "tier": "premium",
        "example_queries": ["who is Sarah Chen", "John's phone number"],
    },
    "reminders": {
        "display_name": "Tasks",
        "icon": "check-square",
        "tier": "free",
        "example_queries": ["my tasks", "remind me to call dentist", "show reminders"],
    },
    "messages": {
        "display_name": "Messages",
        "icon": "message-circle",
        "tier": "premium",
        "example_queries": ["recent messages", "send text to John"],
    },
    "music": {
        "display_name": "Music",
        "icon": "music",
        "tier": "premium",
        "example_queries": ["now playing", "play Beatles"],
    },
    "maps": {
        "display_name": "Maps",
        "icon": "map-pin",
        "tier": "premium",
        "example_queries": ["directions to airport", "coffee near me"],
    },
}


# ─── In-Memory Feed History ──────────────────────────────

class FeedHistoryStore:
    """In-memory feed history. Phase 1 only — no persistence."""

    def __init__(self, max_per_feed: int = 100):
        self._feeds: dict[str, list[dict]] = {}
        self._max_per_feed = max_per_feed

    def append(self, feed_id: str, entry: dict) -> None:
        if feed_id not in self._feeds:
            self._feeds[feed_id] = []
        self._feeds[feed_id].insert(0, entry)  # newest first
        # Trim
        if len(self._feeds[feed_id]) > self._max_per_feed:
            self._feeds[feed_id] = self._feeds[feed_id][:self._max_per_feed]

    def get(self, feed_id: str, limit: int = 20, before: str = "") -> tuple[list[dict], int, bool]:
        cards = self._feeds.get(feed_id, [])
        if before:
            # Find the index of the entry with this timestamp
            idx = next(
                (i for i, c in enumerate(cards) if c.get("meta", {}).get("timestamp", "") < before),
                len(cards),
            )
            cards = cards[idx:]
        total = len(self._feeds.get(feed_id, []))
        limited = cards[:limit]
        has_more = len(cards) > limit
        return limited, total, has_more


# ─── Feed Event Store (ring buffer for dashboard) ────────

class FeedEventStore:
    """In-memory ring buffer of recent feed events for the dashboard.

    Each event represents a connector invocation result (successful or error).
    Used by GET /api/feed/events.
    """

    def __init__(self, maxlen: int = 200):
        self._events: deque = deque(maxlen=maxlen)

    def record(
        self,
        source: str,
        summary: str,
        detail: dict,
        connector: str,
        icon: str | None = None,
        color: str | None = None,
    ) -> dict:
        """Record a feed event. Returns the event dict."""
        event = {
            "id": str(uuid.uuid4())[:12],
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "detail": detail,
            "connector": connector,
            "department": None,
            "icon": icon,
            "color": color,
        }
        self._events.appendleft(event)
        return event

    def query(
        self,
        source: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 50,
    ) -> tuple[list[dict], int, list[dict]]:
        """Query events with filters. Returns (events, total, sources_agg)."""
        events = list(self._events)

        if source:
            events = [e for e in events if e["source"] == source]
        if since:
            events = [e for e in events if e["timestamp"] >= since]
        if until:
            events = [e for e in events if e["timestamp"] <= until]

        total = len(events)
        limited = events[:limit]

        # Aggregate source counts
        source_counts: dict[str, int] = {}
        for e in list(self._events):  # aggregate over all events, not filtered
            s = e["source"]
            source_counts[s] = source_counts.get(s, 0) + 1
        sources_agg = [
            {"name": k, "count": v}
            for k, v in sorted(source_counts.items(), key=lambda x: -x[1])
        ]

        return limited, total, sources_agg


class FeedEventsResponse(BaseModel):
    events: list[dict]
    total: int
    sources: list[dict]


# ─── Registration ─────────────────────────────────────────

def register_feed_endpoints(
    app: FastAPI,
    connector_registry,
    feed_router,
    card_formatter,
) -> None:
    """Register feed portal endpoints on the FastAPI application."""

    history_store = FeedHistoryStore()
    event_store = FeedEventStore()

    @app.post(
        "/api/feed/query",
        response_model=FeedQueryResponse,
        tags=["feed"],
        summary="Execute a feed query and return a typed card",
    )
    async def feed_query(req: FeedQueryRequest, user: UserProfile = Depends(require_auth)):
        """Route a raw query to a connector and return a typed card result."""
        if not req.query.strip():
            raise APIError(ErrorCode.VALIDATION_ERROR, "Query cannot be empty", 400)

        timers: dict[str, float] = {}
        query_id = str(uuid.uuid4())[:12]
        feed_id = req.feed_id or f"feed_{uuid.uuid4().hex[:8]}"
        opts = req.options or FeedQueryOptions()

        t_total = time.perf_counter()

        # ── Step 1: Route ────────────────────────────────
        t0 = time.perf_counter()
        route_result = feed_router.route(req.query, req.connector_hint)
        timers["route_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        # ── Handle routing failure ───────────────────────
        if route_result.error:
            card = card_formatter.format_error(
                message=f"I don't know how to handle: \"{req.query}\"",
                error_type=route_result.error,
                suggestion="Try asking for weather, stocks, news, or time.",
            )
            timers["total_ms"] = round((time.perf_counter() - t_total) * 1000, 2)
            meta = _build_meta(
                query_id=query_id, feed_id=feed_id,
                route=_route_to_dict(route_result),
                timing=timers, llm_used=False,
                connector_source="internal",
            )
            response = {"card": card.to_dict(), "meta": meta}
            history_store.append(feed_id, response)
            return response

        # ── Step 2: Dispatch to connector ────────────────
        connector = connector_registry.get(route_result.connector)
        if not connector:
            card = card_formatter.format_error(
                message=f"Connector '{route_result.connector}' not available",
                error_type="connector_disabled",
                connector=route_result.connector,
            )
            timers["total_ms"] = round((time.perf_counter() - t_total) * 1000, 2)
            meta = _build_meta(
                query_id=query_id, feed_id=feed_id,
                route=_route_to_dict(route_result),
                timing=timers, llm_used=False,
                connector_source="internal",
            )
            response = {"card": card.to_dict(), "meta": meta}
            history_store.append(feed_id, response)
            return response

        t1 = time.perf_counter()
        try:
            raw_result = await connector.call(route_result.operation, route_result.params)
        except Exception as e:
            logger.error(f"Connector {route_result.connector}.{route_result.operation} error: {e}")
            raw_result = {"error": str(e)}
        timers["api_ms"] = round((time.perf_counter() - t1) * 1000, 2)

        # ── Handle connector error ───────────────────────
        if isinstance(raw_result, dict) and "error" in raw_result:
            card = card_formatter.format_error(
                message=raw_result["error"],
                error_type="api_error",
                connector=route_result.connector,
            )
            timers["total_ms"] = round((time.perf_counter() - t_total) * 1000, 2)
            meta = _build_meta(
                query_id=query_id, feed_id=feed_id,
                route=_route_to_dict(route_result),
                timing=timers, llm_used=False,
                connector_source=connector.get_status().get("source", "unknown"),
            )
            response = {"card": card.to_dict(), "meta": meta}
            history_store.append(feed_id, response)
            return response

        # ── Step 3: Format card ──────────────────────────
        t2 = time.perf_counter()
        card = card_formatter.format(route_result.connector, route_result.operation, raw_result)
        timers["format_ms"] = round((time.perf_counter() - t2) * 1000, 2)

        # ── Step 4: Build response ───────────────────────
        timers["total_ms"] = round((time.perf_counter() - t_total) * 1000, 2)

        connector_source = "internal"
        status = connector.get_status()
        if "source" in status:
            connector_source = status["source"]
        elif status.get("enabled"):
            connector_source = "live"
        else:
            connector_source = "simulated"

        meta = _build_meta(
            query_id=query_id, feed_id=feed_id,
            route=_route_to_dict(route_result),
            timing=timers, llm_used=False,
            connector_source=connector_source,
        )

        response = {"card": card.to_dict(), "meta": meta}
        history_store.append(feed_id, response)

        # Record as a feed event for the dashboard event stream
        card_dict = card.to_dict()
        connector_meta = _CONNECTOR_META.get(route_result.connector, {})
        event_store.record(
            source=route_result.connector,
            summary=card_dict.get("title", route_result.connector),
            detail=card_dict.get("data", {}),
            connector=route_result.connector,
            icon=connector_meta.get("icon"),
        )

        return response

    @app.get(
        "/api/feed/history",
        response_model=FeedHistoryResponse,
        tags=["feed"],
        summary="Retrieve feed history for a session",
    )
    async def feed_history(feed_id: str, user: UserProfile = Depends(require_auth), limit: int = 20, before: str = ""):
        """Retrieve past feed cards for a feed session."""
        if not feed_id:
            raise APIError(ErrorCode.VALIDATION_ERROR, "feed_id is required", 400)
        cards, total, has_more = history_store.get(feed_id, limit=limit, before=before)
        return FeedHistoryResponse(
            feed_id=feed_id,
            cards=cards,
            total=total,
            has_more=has_more,
        )

    @app.get(
        "/api/feed/connectors",
        response_model=FeedConnectorsResponse,
        tags=["feed"],
        summary="List available feed connectors and their live/simulated/premium status",
    )
    async def feed_connectors(user: UserProfile = Depends(require_auth)):
        """List all connectors with status: live, simulated, or premium-only."""
        results = []
        for name, connector in connector_registry.connectors.items():
            meta = _CONNECTOR_META.get(name)
            if not meta:
                continue
            status = connector.get_status()
            source = status.get("source", "simulated" if not status.get("enabled") else "live")
            results.append(FeedConnectorStatusResponse(
                name=name,
                display_name=meta["display_name"],
                icon=meta["icon"],
                source=source,
                enabled=status.get("enabled", False),
                provider=status.get("provider", "demo"),
                tier=meta["tier"],
                example_queries=meta["example_queries"],
                rate_limit=meta.get("rate_limit"),
            ))
        return FeedConnectorsResponse(connectors=results)

    # ── GET /api/feed/events — Dashboard event stream ────

    @app.get(
        "/api/feed/events",
        response_model=FeedEventsResponse,
        tags=["feed"],
        summary="Filterable feed event list for dashboard",
    )
    async def feed_events(
        source: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 50,
        user: UserProfile = Depends(require_auth),
    ):
        """List recent feed events with optional filters."""
        limit = min(limit, 200)
        events, total, sources = event_store.query(
            source=source,
            since=since,
            until=until,
            limit=limit,
        )
        return FeedEventsResponse(
            events=events,
            total=total,
            sources=sources,
        )

    # TODO: WS /ws/feed — Real-time event push. WebSocket infrastructure
    # exists (/ws in app.py) but is chat-specific. The dashboard can poll
    # GET /api/feed/events until a dedicated feed WebSocket is implemented.


# ─── Helpers ─────────────────────────────────────────────

def _route_to_dict(route) -> dict:
    return {
        "tier": route.tier,
        "tier_label": route.tier_label,
        "connector": route.connector,
        "operation": route.operation,
        "pattern_matched": route.pattern_matched,
    }


def _build_meta(
    query_id: str,
    feed_id: str,
    route: dict,
    timing: dict,
    llm_used: bool,
    connector_source: str,
) -> dict:
    from datetime import datetime, timezone
    return {
        "query_id": query_id,
        "feed_id": feed_id,
        "route": route,
        "timing": timing,
        "cost": {"api_cost": 0.0, "llm_cost": 0.0, "total_cost": 0.0},
        "llm_used": llm_used,
        "connector_source": connector_source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
