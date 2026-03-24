"""
TMOS13 MCP Connectors — External Service Integrations

Stub implementations for external MCP connectors (Calendar, Email,
Web Search, Messages, Contacts, Music, Maps, Weather, Stocks, News, Time).
Each connector implements a uniform interface that the MCP server can dispatch to.

Connectors return structured data that can be rendered as cards in the
client grid. Real implementations are swapped in via configuration when
API keys / OAuth tokens are provided.

Free-tier connectors with live API support:
    - Weather: OpenWeatherMap (OPENWEATHER_API_KEY)
    - Stocks: Yahoo Finance via yfinance (no key needed)
    - News: NewsAPI (NEWS_API_KEY) or RSS fallback via feedparser
    - Time: Built-in (always live)

Usage:
    connector = CalendarConnector(api_key="...")
    events = await connector.list_events(date="2026-02-08")
    event = await connector.create_event(title="Standup", start="2026-02-08T09:00")
"""
import asyncio
import logging
import time
import random
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import base64

import httpx

# Optional dependencies for live connectors
try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

logger = logging.getLogger("tmos13.mcp.connectors")


# ─── Base Connector ──────────────────────────────────────

class BaseConnector:
    """Base class for MCP connectors with common interface."""
    name: str = "base"
    enabled: bool = False

    def get_status(self) -> dict:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "provider": "stub",
        }

    def _ensure_health_init(self):
        """Lazy-init health tracking attributes.

        Called before any health method. Subclasses don't call
        super().__init__(), so we can't rely on BaseConnector.__init__.
        """
        if hasattr(self, "_health_events"):
            return
        self._health_events: list[dict] = []
        self._health_window_size: int = 100
        self._events_today: int = 0
        self._errors_today: int = 0
        self._total_events: int = 0
        self._total_errors: int = 0
        self._last_event_at: datetime | None = None
        self._latency_samples: list[float] = []
        self._today_date: str = ""

    def record_event(self, latency_ms: float, query: str | None = None, error: str | None = None):
        """Record a connector invocation for health tracking.

        Called automatically by ``call()``. External callers (MCP server,
        feed router) may also call this directly for non-call() invocations.
        """
        self._ensure_health_init()
        now = datetime.utcnow()
        today = now.strftime("%Y-%m-%d")

        # Day rollover — reset daily counters
        if today != self._today_date:
            self._today_date = today
            self._events_today = 0
            self._errors_today = 0

        self._total_events += 1
        self._events_today += 1
        self._last_event_at = now

        if error:
            self._total_errors += 1
            self._errors_today += 1

        # Sliding window for latency
        self._latency_samples.append(latency_ms)
        if len(self._latency_samples) > self._health_window_size:
            self._latency_samples = self._latency_samples[-self._health_window_size:]

        # Event log (keep last 20 for detail view)
        event = {
            "timestamp": now.isoformat(),
            "type": "error" if error else "query",
            "latency_ms": round(latency_ms, 2),
            "query": query,
            "error": error,
        }
        self._health_events.append(event)
        if len(self._health_events) > 20:
            self._health_events = self._health_events[-20:]

    def health_status(self) -> dict:
        """Return health status for Pulse dashboard."""
        self._ensure_health_init()
        avg_latency = (
            sum(self._latency_samples) / len(self._latency_samples)
            if self._latency_samples else 0.0
        )
        error_rate = (
            self._total_errors / max(1, self._total_events)
        )

        # Derive status
        if not getattr(self, "enabled", True):
            status = "pending"
        elif self._total_events == 0:
            status = "connected"  # no data yet, assume healthy
        elif error_rate > 0.5:
            status = "disconnected"
        elif error_rate > 0.1 or avg_latency > 5000:
            status = "degraded"
        else:
            status = "connected"

        return {
            "name": getattr(self, "name", self.__class__.__name__),
            "display_name": getattr(self, "display_name", getattr(self, "name", self.__class__.__name__)),
            "status": status,
            "enabled": getattr(self, "enabled", True),
            "last_event_at": self._last_event_at.isoformat() if self._last_event_at else None,
            "events_today": self._events_today,
            "total_events": self._total_events,
            "avg_latency_ms": round(avg_latency, 1),
            "error_rate": round(error_rate, 4),
            "errors_today": self._errors_today,
            "scopes": getattr(self, "scopes", []),
            "config": {
                "icon": getattr(self, "icon", None),
                "color": getattr(self, "color", None),
            },
        }

    def health_detail(self) -> dict:
        """Extended health info including recent event log."""
        self._ensure_health_init()
        base = self.health_status()
        base["recent_events"] = list(self._health_events)

        # Calculate 24h uptime (percentage of successful events in last 24h)
        now = datetime.utcnow()
        recent = [
            e for e in self._health_events
            if (now - datetime.fromisoformat(e["timestamp"])).total_seconds() < 86400
        ]
        if recent:
            successes = sum(1 for e in recent if e["type"] != "error")
            base["uptime_24h"] = round(successes / len(recent) * 100, 1)
        else:
            base["uptime_24h"] = 100.0 if getattr(self, "enabled", True) else 0.0

        return base

    async def call(self, operation: str, params: dict) -> dict:
        """Generic dispatch: route (operation, params) to the correct method.

        Subclasses can override ``_operation_map`` to alias feed-router
        operation names to actual method names. Automatically records
        health events for the Pulse dashboard.
        """
        self._ensure_health_init()
        start = time.time()
        op_map = getattr(self, "_operation_map", {})
        method_name = op_map.get(operation, operation)
        method = getattr(self, method_name, None)
        if method is None:
            error_msg = f"Unknown operation '{operation}' on connector '{self.name}'"
            latency = (time.time() - start) * 1000
            self.record_event(latency_ms=latency, query=f"{operation}", error=error_msg)
            return {"error": error_msg}
        try:
            result = await method(**params)
            latency = (time.time() - start) * 1000
            # Check if the result itself reports an error
            error = None
            if isinstance(result, dict) and "error" in result:
                error = result["error"]
            self.record_event(latency_ms=latency, query=f"{operation}", error=error)
            return result
        except TypeError as e:
            latency = (time.time() - start) * 1000
            error_msg = f"Bad params for {self.name}.{method_name}: {e}"
            self.record_event(latency_ms=latency, query=f"{operation}", error=error_msg)
            return {"error": error_msg}


# ─── Calendar Connector ─────────────────────────────────

@dataclass
class CalendarEvent:
    event_id: str = ""
    title: str = ""
    start: str = ""  # ISO datetime
    end: str = ""
    location: str = ""
    description: str = ""
    attendees: list[str] = field(default_factory=list)
    all_day: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


class CalendarConnector(BaseConnector):
    """Calendar integration (Google Calendar, Apple Calendar, etc.)."""
    name = "calendar"
    _operation_map = {"today": "list_events", "availability": "check_availability"}

    def __init__(self, api_key: str = "", provider: str = "stub"):
        self.api_key = api_key
        self.provider = provider
        self.enabled = bool(api_key)
        if self.enabled:
            logger.info(f"Calendar connector initialized ({provider})")

    async def list_events(
        self,
        date: str = "",
        days_ahead: int = 7,
        max_results: int = 20,
    ) -> list[dict]:
        """List upcoming calendar events."""
        if not self.enabled:
            return [{"info": "Calendar not configured. Add CALENDAR_API_KEY to enable."}]
        # Stub: real implementation would call Google Calendar API
        return []

    async def create_event(
        self,
        title: str,
        start: str,
        end: str = "",
        location: str = "",
        description: str = "",
        attendees: list[str] | None = None,
    ) -> dict:
        """Create a calendar event."""
        if not self.enabled:
            return {"error": "Calendar not configured"}
        return {"status": "stub", "message": f"Would create event: {title}"}

    async def check_availability(self, date: str, duration_minutes: int = 30) -> dict:
        """Check availability for a given date."""
        if not self.enabled:
            return {"error": "Calendar not configured"}
        return {"status": "stub", "available_slots": []}


# ─── Email Connector ─────────────────────────────────────

@dataclass
class EmailMessage:
    message_id: str = ""
    subject: str = ""
    sender: str = ""
    recipients: list[str] = field(default_factory=list)
    body_preview: str = ""
    date: str = ""
    read: bool = False
    has_attachments: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


class EmailConnector(BaseConnector):
    """Email integration (Gmail, Outlook, etc.)."""
    name = "email"
    _operation_map = {"inbox": "search_inbox", "search": "search_inbox"}

    def __init__(self, api_key: str = "", provider: str = "stub"):
        self.api_key = api_key
        self.provider = provider
        self.enabled = bool(api_key)
        if self.enabled:
            logger.info(f"Email connector initialized ({provider})")

    async def search_inbox(
        self,
        query: str,
        max_results: int = 10,
        unread_only: bool = False,
    ) -> list[dict]:
        """Search email inbox."""
        if not self.enabled:
            return [{"info": "Email not configured. Add EMAIL_API_KEY to enable."}]
        return []

    async def read_message(self, message_id: str) -> dict:
        """Read a specific email message."""
        if not self.enabled:
            return {"error": "Email not configured"}
        return {"status": "stub"}

    async def draft_reply(
        self,
        message_id: str,
        body: str,
    ) -> dict:
        """Draft a reply to an email (does NOT send without confirmation)."""
        if not self.enabled:
            return {"error": "Email not configured"}
        return {"status": "draft_created", "message": "Draft saved (not sent)"}

    async def get_unread_count(self) -> dict:
        """Get count of unread messages."""
        if not self.enabled:
            return {"error": "Email not configured"}
        return {"unread": 0}


# ─── Web Search Connector ────────────────────────────────

class WebSearchConnector(BaseConnector):
    """Web search integration (Brave Search, etc.)."""
    name = "web_search"

    def __init__(self, api_key: str = "", provider: str = "stub"):
        self.api_key = api_key
        self.provider = provider
        self.enabled = bool(api_key)
        if self.enabled:
            logger.info(f"Web search connector initialized ({provider})")

    async def search(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[dict]:
        """Perform a web search."""
        if not self.enabled:
            return [{"info": "Web search not configured. Add BRAVE_API_KEY to enable."}]
        return []

    async def news(self, query: str, max_results: int = 5) -> list[dict]:
        """Search recent news."""
        if not self.enabled:
            return [{"info": "Web search not configured"}]
        return []


# ─── Messages / SMS Connector ────────────────────────────

class MessagesConnector(BaseConnector):
    """SMS / messaging integration."""
    name = "messages"

    def __init__(self, api_key: str = "", provider: str = "stub"):
        self.api_key = api_key
        self.provider = provider
        self.enabled = bool(api_key)

    async def list_recent(self, contact: str = "", limit: int = 10) -> list[dict]:
        """List recent messages."""
        if not self.enabled:
            return [{"info": "Messages not configured"}]
        return []

    async def send(self, to: str, body: str, confirm: bool = True) -> dict:
        """
        Send a message. ALWAYS requires explicit confirmation by default.
        Will NOT send without confirm=True being set after user approval.
        """
        if not self.enabled:
            return {"error": "Messages not configured"}
        if not confirm:
            return {
                "status": "pending_confirmation",
                "message": f"Ready to send to {to}: '{body[:50]}...' — confirm to send.",
            }
        return {"status": "stub", "message": f"Would send to {to}"}


# ─── Contacts Connector ──────────────────────────────────

@dataclass
class Contact:
    contact_id: str = ""
    name: str = ""
    email: str = ""
    phone: str = ""
    organization: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class ContactsConnector(BaseConnector):
    """Contacts integration."""
    name = "contacts"

    def __init__(self, api_key: str = "", provider: str = "stub"):
        self.api_key = api_key
        self.provider = provider
        self.enabled = bool(api_key)

    async def search(self, query: str, max_results: int = 10) -> list[dict]:
        """Search contacts by name, email, or phone."""
        if not self.enabled:
            return [{"info": "Contacts not configured"}]
        return []

    async def get(self, contact_id: str) -> dict:
        """Get a specific contact."""
        if not self.enabled:
            return {"error": "Contacts not configured"}
        return {}


# ─── Music Connector ─────────────────────────────────────

class MusicConnector(BaseConnector):
    """Music / media integration (Spotify, Apple Music, etc.)."""
    name = "music"

    def __init__(self, api_key: str = "", provider: str = "stub"):
        self.api_key = api_key
        self.provider = provider
        self.enabled = bool(api_key)

    async def search(self, query: str, max_results: int = 5) -> list[dict]:
        """Search for songs/artists/albums."""
        if not self.enabled:
            return [{"info": "Music not configured. Add SPOTIFY_API_KEY to enable."}]
        return []

    async def now_playing(self) -> dict:
        """Get currently playing track."""
        if not self.enabled:
            return {"error": "Music not configured"}
        return {"status": "nothing_playing"}

    async def play(self, uri: str = "", query: str = "") -> dict:
        """Play a track, album, or playlist."""
        if not self.enabled:
            return {"error": "Music not configured"}
        return {"status": "stub"}


# ─── Maps / Navigation Connector ─────────────────────────

class MapsConnector(BaseConnector):
    """Maps and navigation integration."""
    name = "maps"

    def __init__(self, api_key: str = "", provider: str = "stub"):
        self.api_key = api_key
        self.provider = provider
        self.enabled = bool(api_key)

    async def directions(
        self,
        origin: str,
        destination: str,
        mode: str = "driving",
    ) -> dict:
        """Get directions and travel time."""
        if not self.enabled:
            return {"error": "Maps not configured. Add MAPS_API_KEY to enable."}
        return {"status": "stub"}

    async def nearby(
        self,
        query: str,
        location: str = "",
        radius_km: float = 5.0,
    ) -> list[dict]:
        """Find nearby places."""
        if not self.enabled:
            return [{"info": "Maps not configured"}]
        return []

    async def geocode(self, address: str) -> dict:
        """Geocode an address to coordinates."""
        if not self.enabled:
            return {"error": "Maps not configured"}
        return {}


# ─── Reminders / Tasks Connector ─────────────────────────

@dataclass
class Reminder:
    reminder_id: str = ""
    title: str = ""
    due: str = ""  # ISO datetime
    completed: bool = False
    priority: str = "normal"  # low, normal, high
    list_name: str = "default"

    def to_dict(self) -> dict:
        return asdict(self)


class RemindersConnector(BaseConnector):
    """Reminders / task list integration."""
    name = "reminders"
    _operation_map = {"list": "list_tasks"}

    def __init__(self, api_key: str = "", provider: str = "stub"):
        self.api_key = api_key
        self.provider = provider
        self.enabled = bool(api_key)
        self._reminders: list[Reminder] = []  # in-memory for stub

    async def list_tasks(
        self,
        list_name: str = "",
        include_completed: bool = False,
    ) -> list[dict]:
        """List reminders/tasks."""
        if not self.enabled and not self._reminders:
            return [{"info": "Reminders not configured"}]
        tasks = self._reminders
        if list_name:
            tasks = [r for r in tasks if r.list_name == list_name]
        if not include_completed:
            tasks = [r for r in tasks if not r.completed]
        return [r.to_dict() for r in tasks]

    async def create(
        self,
        title: str,
        due: str = "",
        priority: str = "normal",
        list_name: str = "default",
    ) -> dict:
        """Create a reminder/task."""
        import uuid
        reminder = Reminder(
            reminder_id=str(uuid.uuid4())[:8],
            title=title,
            due=due,
            priority=priority,
            list_name=list_name,
        )
        self._reminders.append(reminder)
        return reminder.to_dict()

    async def complete(self, reminder_id: str) -> dict:
        """Mark a reminder as completed."""
        for r in self._reminders:
            if r.reminder_id == reminder_id:
                r.completed = True
                return {"status": "completed", "reminder_id": reminder_id}
        return {"error": f"Reminder not found: {reminder_id}"}


# ─── Weather Connector ──────────────────────────────────

class WeatherConnector(BaseConnector):
    """Weather data integration via OpenWeatherMap (free tier: 1,000 calls/day).

    Live mode: OPENWEATHER_API_KEY set → real API calls.
    Simulated mode: no key → demo data for known cities, random for unknown.
    """
    name = "weather"

    # Simulated city weather for demo / fallback
    _DEMO_CITIES: dict[str, dict] = {
        "chicago": {"city": "Chicago", "country": "US", "temp": 34, "feels_like": 28, "humidity": 65, "wind_speed": 12, "description": "partly cloudy", "clouds": 45, "temp_high": 38, "temp_low": 26},
        "new york": {"city": "New York", "country": "US", "temp": 42, "feels_like": 37, "humidity": 55, "wind_speed": 8, "description": "clear sky", "clouds": 10, "temp_high": 46, "temp_low": 34},
        "nyc": {"city": "New York", "country": "US", "temp": 42, "feels_like": 37, "humidity": 55, "wind_speed": 8, "description": "clear sky", "clouds": 10, "temp_high": 46, "temp_low": 34},
        "san francisco": {"city": "San Francisco", "country": "US", "temp": 58, "feels_like": 55, "humidity": 72, "wind_speed": 14, "description": "foggy", "clouds": 80, "temp_high": 62, "temp_low": 52},
        "los angeles": {"city": "Los Angeles", "country": "US", "temp": 72, "feels_like": 70, "humidity": 40, "wind_speed": 6, "description": "sunny", "clouds": 5, "temp_high": 78, "temp_low": 58},
        "london": {"city": "London", "country": "GB", "temp": 48, "feels_like": 44, "humidity": 80, "wind_speed": 10, "description": "light rain", "clouds": 90, "temp_high": 50, "temp_low": 42},
        "tokyo": {"city": "Tokyo", "country": "JP", "temp": 52, "feels_like": 49, "humidity": 60, "wind_speed": 7, "description": "overcast", "clouds": 70, "temp_high": 56, "temp_low": 46},
        "paris": {"city": "Paris", "country": "FR", "temp": 46, "feels_like": 42, "humidity": 75, "wind_speed": 9, "description": "cloudy", "clouds": 65, "temp_high": 50, "temp_low": 40},
        "miami": {"city": "Miami", "country": "US", "temp": 78, "feels_like": 82, "humidity": 85, "wind_speed": 11, "description": "partly cloudy", "clouds": 30, "temp_high": 82, "temp_low": 70},
        "seattle": {"city": "Seattle", "country": "US", "temp": 45, "feels_like": 40, "humidity": 78, "wind_speed": 8, "description": "light rain", "clouds": 85, "temp_high": 48, "temp_low": 38},
        "austin": {"city": "Austin", "country": "US", "temp": 65, "feels_like": 63, "humidity": 50, "wind_speed": 10, "description": "sunny", "clouds": 15, "temp_high": 72, "temp_low": 52},
        "denver": {"city": "Denver", "country": "US", "temp": 38, "feels_like": 30, "humidity": 35, "wind_speed": 15, "description": "clear sky", "clouds": 5, "temp_high": 45, "temp_low": 28},
        "cupertino": {"city": "Cupertino", "country": "US", "temp": 62, "feels_like": 60, "humidity": 55, "wind_speed": 5, "description": "sunny", "clouds": 10, "temp_high": 68, "temp_low": 50},
    }

    _OWM_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

    def __init__(self, api_key: str = "", provider: str = ""):
        self.api_key = api_key
        # Always enabled: live with API key, simulated without
        self.enabled = True
        if api_key:
            self.provider = provider or "openweathermap"
            self._source = "live"
            logger.info(f"Weather connector: LIVE (openweathermap)")
        else:
            self.provider = provider or "demo"
            self._source = "simulated"
            logger.info("Weather connector: SIMULATED (no API key)")

    def get_status(self) -> dict:
        return {"name": self.name, "enabled": True, "provider": self.provider, "source": self._source}

    async def _fetch_live(self, city: str) -> dict | None:
        """Fetch live weather from OpenWeatherMap. Returns None on failure."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    self._OWM_BASE_URL,
                    params={"q": city, "appid": self.api_key, "units": "imperial"},
                )
                if resp.status_code == 401:
                    logger.warning("Weather API: invalid API key")
                    return None
                if resp.status_code == 404:
                    return {"error": f"City not found: {city}"}
                if resp.status_code == 429:
                    logger.warning("Weather API: rate limit exceeded")
                    return None
                resp.raise_for_status()
                j = resp.json()
                main = j.get("main", {})
                wind = j.get("wind", {})
                weather = j.get("weather", [{}])[0]
                sys_data = j.get("sys", {})
                return {
                    "city": j.get("name", city),
                    "country": sys_data.get("country", "??"),
                    "temp": round(main.get("temp", 0)),
                    "feels_like": round(main.get("feels_like", 0)),
                    "humidity": main.get("humidity", 0),
                    "wind_speed": round(wind.get("speed", 0)),
                    "description": weather.get("description", ""),
                    "icon": weather.get("icon", ""),
                    "clouds": j.get("clouds", {}).get("all", 0),
                    "temp_high": round(main.get("temp_max", 0)),
                    "temp_low": round(main.get("temp_min", 0)),
                    "_provider": "openweathermap",
                    "_source": "live",
                    "units": "imperial",
                }
        except httpx.HTTPStatusError as e:
            logger.error(f"Weather API HTTP error: {e.response.status_code}")
            return None
        except (httpx.RequestError, Exception) as e:
            logger.error(f"Weather API request error: {e}")
            return None

    def _simulated_current(self, city: str) -> dict:
        """Return simulated weather data (always tagged as simulated)."""
        key = city.strip().lower()
        if key in self._DEMO_CITIES:
            data = dict(self._DEMO_CITIES[key])
        else:
            data = {
                "city": city.title(), "country": "??",
                "temp": random.randint(30, 85), "feels_like": random.randint(25, 80),
                "humidity": random.randint(30, 90), "wind_speed": random.randint(3, 20),
                "description": random.choice(["clear sky", "partly cloudy", "overcast", "light rain"]),
                "clouds": random.randint(0, 100),
                "temp_high": 0, "temp_low": 0,
            }
            data["temp_high"] = data["temp"] + random.randint(2, 8)
            data["temp_low"] = data["temp"] - random.randint(4, 12)
        data["_provider"] = "demo"
        data["_source"] = "simulated"
        data["units"] = "imperial"
        return data

    async def current(self, city: str = "New York") -> dict:
        """Get current weather for a city."""
        if self.api_key:
            result = await self._fetch_live(city)
            if result is not None:
                return result
            # Fall back to simulated on API failure
            logger.warning(f"Weather API failed for '{city}', falling back to simulated")
        return self._simulated_current(city)

    async def forecast(self, city: str = "New York") -> dict:
        """Get multi-day forecast. Free tier returns simulated forecast with premium upsell."""
        current = await self.current(city)
        if "error" in current:
            return current
        conditions = ["clear sky", "partly cloudy", "cloudy", "light rain", "sunny", "overcast"]
        days = []
        for i in range(5):
            d = datetime.now(timezone.utc) + timedelta(days=i + 1)
            base = current["temp"] + random.randint(-8, 8)
            days.append({
                "date": d.strftime("%Y-%m-%d"),
                "temp_high": base + random.randint(2, 6),
                "temp_low": base - random.randint(4, 10),
                "conditions": random.choice(conditions),
            })
        return {
            "city": current["city"], "country": current["country"],
            "days": days, "units": "imperial",
            "_provider": self.provider, "_source": self._source,
        }


# ─── Stocks Connector ──────────────────────────────────

class StocksConnector(BaseConnector):
    """Stock market data via Yahoo Finance (yfinance, no API key needed).

    Live mode: yfinance installed → real market data.
    Simulated mode: yfinance not installed → demo data.
    """
    name = "stocks"

    _DEMO_QUOTES: dict[str, dict] = {
        "AAPL": {"symbol": "AAPL", "price": 187.42, "change": 2.31, "change_pct": 1.25, "volume": 52_300_000, "open": 185.11, "high": 188.90, "low": 184.50, "prev_close": 185.11, "latest_day": "2026-02-12", "name": "Apple Inc."},
        "GOOGL": {"symbol": "GOOGL", "price": 176.85, "change": -1.42, "change_pct": -0.80, "volume": 28_100_000, "open": 178.27, "high": 179.50, "low": 175.90, "prev_close": 178.27, "latest_day": "2026-02-12", "name": "Alphabet Inc."},
        "MSFT": {"symbol": "MSFT", "price": 432.18, "change": 5.67, "change_pct": 1.33, "volume": 22_500_000, "open": 426.51, "high": 433.80, "low": 425.20, "prev_close": 426.51, "latest_day": "2026-02-12", "name": "Microsoft Corp."},
        "TSLA": {"symbol": "TSLA", "price": 248.90, "change": -8.75, "change_pct": -3.40, "volume": 95_200_000, "open": 257.65, "high": 258.40, "low": 246.10, "prev_close": 257.65, "latest_day": "2026-02-12", "name": "Tesla Inc."},
        "AMZN": {"symbol": "AMZN", "price": 198.34, "change": 3.12, "change_pct": 1.60, "volume": 45_800_000, "open": 195.22, "high": 199.10, "low": 194.80, "prev_close": 195.22, "latest_day": "2026-02-12", "name": "Amazon.com Inc."},
        "NVDA": {"symbol": "NVDA", "price": 875.50, "change": 22.30, "change_pct": 2.61, "volume": 38_700_000, "open": 853.20, "high": 878.90, "low": 850.10, "prev_close": 853.20, "latest_day": "2026-02-12", "name": "NVIDIA Corp."},
        "META": {"symbol": "META", "price": 582.70, "change": 8.45, "change_pct": 1.47, "volume": 18_900_000, "open": 574.25, "high": 585.20, "low": 572.80, "prev_close": 574.25, "latest_day": "2026-02-12", "name": "Meta Platforms Inc."},
    }

    _DEMO_COMPANIES: dict[str, dict] = {
        "apple": {"symbol": "AAPL", "name": "Apple Inc.", "headquarters": "Cupertino, CA"},
        "google": {"symbol": "GOOGL", "name": "Alphabet Inc.", "headquarters": "Mountain View, CA"},
        "alphabet": {"symbol": "GOOGL", "name": "Alphabet Inc.", "headquarters": "Mountain View, CA"},
        "microsoft": {"symbol": "MSFT", "name": "Microsoft Corp.", "headquarters": "Redmond, WA"},
        "tesla": {"symbol": "TSLA", "name": "Tesla Inc.", "headquarters": "Austin, TX"},
        "amazon": {"symbol": "AMZN", "name": "Amazon.com Inc.", "headquarters": "Seattle, WA"},
        "nvidia": {"symbol": "NVDA", "name": "NVIDIA Corp.", "headquarters": "Santa Clara, CA"},
        "meta": {"symbol": "META", "name": "Meta Platforms Inc.", "headquarters": "Menlo Park, CA"},
        "facebook": {"symbol": "META", "name": "Meta Platforms Inc.", "headquarters": "Menlo Park, CA"},
    }

    def __init__(self, api_key: str = "", provider: str = ""):
        self.api_key = api_key
        self.enabled = True
        if HAS_YFINANCE:
            self.provider = provider or "yahoo_finance"
            self._source = "live"
            logger.info("Stocks connector: LIVE (yahoo_finance)")
        else:
            self.provider = provider or "demo"
            self._source = "simulated"
            logger.info("Stocks connector: SIMULATED (yfinance not installed)")

    def get_status(self) -> dict:
        return {"name": self.name, "enabled": True, "provider": self.provider, "source": self._source}

    async def _fetch_yfinance_quote(self, symbol: str) -> dict | None:
        """Fetch a live quote via yfinance. Returns None on failure."""
        def _sync_fetch():
            ticker = yf.Ticker(symbol)
            info = ticker.info
            if not info or info.get("trailingPegRatio") is None and info.get("regularMarketPrice") is None:
                # yfinance returns empty info for invalid symbols in some versions
                fast = ticker.fast_info
                if hasattr(fast, "last_price") and fast.last_price:
                    price = round(fast.last_price, 2)
                    prev = round(fast.previous_close, 2) if hasattr(fast, "previous_close") and fast.previous_close else price
                    change = round(price - prev, 2)
                    return {
                        "symbol": symbol,
                        "name": symbol,
                        "price": price,
                        "change": change,
                        "change_pct": round((change / prev) * 100, 2) if prev else 0,
                        "volume": int(fast.last_volume) if hasattr(fast, "last_volume") and fast.last_volume else 0,
                        "market_cap": int(fast.market_cap) if hasattr(fast, "market_cap") and fast.market_cap else 0,
                        "day_high": round(fast.day_high, 2) if hasattr(fast, "day_high") and fast.day_high else price,
                        "day_low": round(fast.day_low, 2) if hasattr(fast, "day_low") and fast.day_low else price,
                        "open": round(fast.open, 2) if hasattr(fast, "open") and fast.open else prev,
                        "prev_close": prev,
                        "latest_day": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    }
                return None
            price = info.get("regularMarketPrice") or info.get("currentPrice", 0)
            prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose", price)
            change = round(price - prev_close, 2) if price and prev_close else 0
            return {
                "symbol": symbol,
                "name": info.get("shortName") or info.get("longName", symbol),
                "price": round(price, 2) if price else 0,
                "change": change,
                "change_pct": round((change / prev_close) * 100, 2) if prev_close else 0,
                "volume": info.get("regularMarketVolume") or info.get("volume", 0) or 0,
                "market_cap": info.get("marketCap", 0) or 0,
                "day_high": round(info.get("regularMarketDayHigh") or info.get("dayHigh", 0) or 0, 2),
                "day_low": round(info.get("regularMarketDayLow") or info.get("dayLow", 0) or 0, 2),
                "open": round(info.get("regularMarketOpen") or info.get("open", 0) or 0, 2),
                "high": round(info.get("regularMarketDayHigh") or info.get("dayHigh", 0) or 0, 2),
                "low": round(info.get("regularMarketDayLow") or info.get("dayLow", 0) or 0, 2),
                "prev_close": round(prev_close, 2) if prev_close else 0,
                "latest_day": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            }
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _sync_fetch)
        except Exception as e:
            logger.error(f"yfinance error for {symbol}: {e}")
            return None

    def _simulated_quote(self, symbol: str) -> dict:
        """Return simulated quote data (always tagged as simulated)."""
        sym = symbol.upper().strip()
        if sym in self._DEMO_QUOTES:
            data = dict(self._DEMO_QUOTES[sym])
        else:
            price = round(random.uniform(10, 500), 2)
            change = round(random.uniform(-10, 10), 2)
            data = {
                "symbol": sym, "price": price, "change": change,
                "change_pct": round((change / price) * 100, 2),
                "volume": random.randint(1_000_000, 100_000_000),
                "open": round(price - change, 2), "high": round(price + abs(change) * 0.5, 2),
                "low": round(price - abs(change) * 1.5, 2),
                "prev_close": round(price - change, 2),
                "latest_day": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            }
        data["_provider"] = "demo"
        data["_source"] = "simulated"
        return data

    async def quote(self, symbol: str = "AAPL") -> dict:
        """Get a stock quote by ticker symbol."""
        sym = symbol.upper().strip()
        if HAS_YFINANCE:
            result = await self._fetch_yfinance_quote(sym)
            if result is not None:
                result["_provider"] = "yahoo_finance"
                result["_source"] = "live"
                result["actions"] = [
                    {"label": "\u26a1 Real-time streaming", "query": "cmd:upgrade stocks", "icon": "\u26a1"},
                    {"label": "\ud83d\udcca Technical indicators", "query": "cmd:upgrade stocks", "icon": "\ud83d\udcca"},
                ]
                return result
            logger.warning(f"yfinance failed for '{sym}', falling back to simulated")
        return self._simulated_quote(sym)

    async def search(self, keywords: str = "") -> dict:
        """Search for a company by name."""
        key = keywords.strip().lower()
        results = [
            v for k, v in self._DEMO_COMPANIES.items()
            if key in k
        ]
        if not results:
            results = [{"symbol": "???", "name": keywords, "headquarters": "Unknown"}]
        return {
            "query": keywords, "results": results,
            "_provider": self.provider, "_source": self._source,
        }


# ─── News Connector ────────────────────────────────────

class NewsConnector(BaseConnector):
    """News headlines via NewsAPI (NEWS_API_KEY) or RSS fallback (feedparser).

    Live mode (tier 1): NEWS_API_KEY set → NewsAPI.org (100 calls/day free).
    Live mode (tier 2): No key but feedparser installed → RSS feeds.
    Simulated mode: Neither available → demo headlines.
    """
    name = "news"

    _DEMO_HEADLINES = [
        {"title": "AI Infrastructure Spending Surges as Companies Race to Build Capacity", "source": "Reuters", "published_at": "2026-02-12T14:30:00Z", "description": "Major tech companies announced combined spending of $180B on AI infrastructure in 2026.", "url": "#"},
        {"title": "Federal Reserve Signals Cautious Approach to Rate Cuts", "source": "Bloomberg", "published_at": "2026-02-12T12:15:00Z", "description": "Fed minutes reveal ongoing debate about the pace of monetary policy easing.", "url": "#"},
        {"title": "SpaceX Starship Completes First Commercial Payload Delivery", "source": "Space.com", "published_at": "2026-02-12T10:00:00Z", "description": "The Starship vehicle successfully delivered a batch of satellites to orbit.", "url": "#"},
        {"title": "Climate Summit Produces Landmark Agreement on Carbon Markets", "source": "AP News", "published_at": "2026-02-12T08:45:00Z", "description": "194 nations agreed on a unified framework for international carbon credit trading.", "url": "#"},
        {"title": "Breakthrough in Solid-State Battery Technology Promises 1000-Mile EV Range", "source": "TechCrunch", "published_at": "2026-02-11T16:20:00Z", "description": "A startup demonstrated a battery cell with 3x the energy density of current lithium-ion.", "url": "#"},
    ]

    _NEWSAPI_BASE = "https://newsapi.org/v2"
    _RSS_FEEDS = [
        ("Reuters", "https://feeds.reuters.com/reuters/topNews"),
        ("AP News", "https://rsshub.app/apnews/topics/apf-topnews"),
        ("BBC", "https://feeds.bbci.co.uk/news/rss.xml"),
    ]

    def __init__(self, api_key: str = "", provider: str = ""):
        self.api_key = api_key
        self.enabled = True
        if api_key:
            self.provider = provider or "newsapi"
            self._source = "live"
            logger.info("News connector: LIVE (newsapi)")
        elif HAS_FEEDPARSER:
            self.provider = provider or "rss"
            self._source = "live"
            logger.info("News connector: LIVE (rss/feedparser)")
        else:
            self.provider = provider or "demo"
            self._source = "simulated"
            logger.info("News connector: SIMULATED (no API key, feedparser not installed)")

    def get_status(self) -> dict:
        return {"name": self.name, "enabled": True, "provider": self.provider, "source": self._source}

    async def _fetch_newsapi_headlines(self, category: str = "general") -> list[dict] | None:
        """Fetch from NewsAPI top-headlines endpoint."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self._NEWSAPI_BASE}/top-headlines",
                    params={"country": "us", "category": category, "apiKey": self.api_key, "pageSize": 10},
                )
                if resp.status_code == 401:
                    logger.warning("NewsAPI: invalid API key")
                    return None
                if resp.status_code == 429:
                    logger.warning("NewsAPI: rate limit exceeded")
                    return None
                resp.raise_for_status()
                data = resp.json()
                return [
                    {
                        "title": a.get("title", ""),
                        "source": a.get("source", {}).get("name", ""),
                        "description": a.get("description", ""),
                        "url": a.get("url", "#"),
                        "published_at": a.get("publishedAt", ""),
                        "image_url": a.get("urlToImage", ""),
                    }
                    for a in data.get("articles", [])
                ]
        except (httpx.RequestError, Exception) as e:
            logger.error(f"NewsAPI request error: {e}")
            return None

    async def _fetch_newsapi_search(self, query: str) -> list[dict] | None:
        """Search NewsAPI everything endpoint."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self._NEWSAPI_BASE}/everything",
                    params={"q": query, "apiKey": self.api_key, "pageSize": 10, "sortBy": "publishedAt"},
                )
                if resp.status_code in (401, 429):
                    return None
                resp.raise_for_status()
                data = resp.json()
                return [
                    {
                        "title": a.get("title", ""),
                        "source": a.get("source", {}).get("name", ""),
                        "description": a.get("description", ""),
                        "url": a.get("url", "#"),
                        "published_at": a.get("publishedAt", ""),
                        "image_url": a.get("urlToImage", ""),
                    }
                    for a in data.get("articles", [])
                ]
        except (httpx.RequestError, Exception) as e:
            logger.error(f"NewsAPI search error: {e}")
            return None

    async def _fetch_rss_headlines(self) -> list[dict] | None:
        """Fetch headlines from RSS feeds via feedparser."""
        def _sync_parse():
            articles = []
            for source_name, url in self._RSS_FEEDS:
                try:
                    feed = feedparser.parse(url)
                    for entry in feed.entries[:5]:
                        articles.append({
                            "title": entry.get("title", ""),
                            "source": source_name,
                            "description": entry.get("summary", ""),
                            "url": entry.get("link", "#"),
                            "published_at": entry.get("published", ""),
                            "image_url": "",
                        })
                except Exception:
                    continue
            return articles if articles else None
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _sync_parse)
        except Exception as e:
            logger.error(f"RSS fetch error: {e}")
            return None

    def _simulated_headlines(self) -> dict:
        """Return simulated demo headlines (always tagged as simulated)."""
        return {
            "articles": list(self._DEMO_HEADLINES),
            "total_results": len(self._DEMO_HEADLINES),
            "_provider": "demo", "_source": "simulated",
        }

    async def top_headlines(self, category: str = "general") -> dict:
        """Get top headlines."""
        # Tier 1: NewsAPI
        if self.api_key:
            articles = await self._fetch_newsapi_headlines(category)
            if articles is not None:
                return {
                    "articles": articles,
                    "total_results": len(articles),
                    "_provider": "newsapi", "_source": "live",
                }
        # Tier 2: RSS
        if HAS_FEEDPARSER:
            articles = await self._fetch_rss_headlines()
            if articles is not None:
                return {
                    "articles": articles,
                    "total_results": len(articles),
                    "_provider": "rss", "_source": "live",
                }
        # Tier 3: Simulated
        return self._simulated_headlines()

    async def search(self, query: str = "") -> dict:
        """Search news by topic."""
        # Tier 1: NewsAPI search
        if self.api_key:
            articles = await self._fetch_newsapi_search(query)
            if articles is not None:
                return {
                    "articles": articles, "topic": query,
                    "total_results": len(articles),
                    "_provider": "newsapi", "_source": "live",
                }
        # Tier 2/3: Simulated search (RSS doesn't support search)
        q = query.lower()
        matched = [a for a in self._DEMO_HEADLINES if q in a["title"].lower() or q in a["description"].lower()]
        if not matched:
            matched = [
                {"title": f"Latest developments in {query}", "source": "Demo News", "published_at": datetime.now(timezone.utc).isoformat(), "description": f"Simulated news results for '{query}'.", "url": "#"},
            ]
        return {
            "articles": matched, "topic": query,
            "total_results": len(matched),
            "_provider": "demo", "_source": "simulated",
        }


# ─── Time Connector ────────────────────────────────────

class TimeConnector(BaseConnector):
    """Time and timezone utility connector."""
    name = "time"

    _TZ_OFFSETS: dict[str, tuple[str, int]] = {
        "utc": ("UTC", 0), "gmt": ("GMT", 0),
        "est": ("US/Eastern", -5), "eastern": ("US/Eastern", -5),
        "cst": ("US/Central", -6), "central": ("US/Central", -6),
        "mst": ("US/Mountain", -7), "mountain": ("US/Mountain", -7),
        "pst": ("US/Pacific", -8), "pacific": ("US/Pacific", -8),
        "new york": ("US/Eastern", -5), "chicago": ("US/Central", -6),
        "denver": ("US/Mountain", -7), "los angeles": ("US/Pacific", -8),
        "san francisco": ("US/Pacific", -8), "seattle": ("US/Pacific", -8),
        "london": ("Europe/London", 0), "paris": ("Europe/Paris", 1),
        "berlin": ("Europe/Berlin", 1), "tokyo": ("Asia/Tokyo", 9),
        "sydney": ("Australia/Sydney", 11), "mumbai": ("Asia/Kolkata", 5),
        "dubai": ("Asia/Dubai", 4), "singapore": ("Asia/Singapore", 8),
        "hong kong": ("Asia/Hong_Kong", 8),
        "jst": ("Asia/Tokyo", 9), "ist": ("Asia/Kolkata", 5),
        "cet": ("Europe/Paris", 1), "aest": ("Australia/Sydney", 11),
    }

    def __init__(self, **kwargs):
        self.enabled = True
        self._source = "internal"
        self.provider = "system"

    def get_status(self) -> dict:
        return {"name": self.name, "enabled": True, "provider": "system", "source": "internal"}

    async def current(self, timezone_name: str = "UTC") -> dict:
        """Get current time in a timezone."""
        key = timezone_name.strip().lower()
        if key in self._TZ_OFFSETS:
            tz_label, offset = self._TZ_OFFSETS[key]
        else:
            tz_label = timezone_name
            offset = 0

        now = datetime.now(timezone.utc) + timedelta(hours=offset)
        return {
            "timezone": tz_label,
            "time": now.strftime("%I:%M:%S %p"),
            "date": now.strftime("%A, %B %d, %Y"),
            "utc_offset": f"UTC{'+' if offset >= 0 else ''}{offset}",
            "_provider": "system", "_source": "internal",
        }


# ─── GitHub Connector ────────────────────────────────────

class GitHubConnector(BaseConnector):
    """GitHub repository connector via REST API v3."""
    name = "github"
    MAX_FILE_CONTENT_SIZE = 50000
    WRITE_METHODS = {"create_issue", "create_branch", "create_or_update_file"}

    def __init__(self, token: str = "", default_repo: str = ""):
        self.token = token
        self.default_repo = default_repo
        self.enabled = bool(self.token and self.default_repo)
        self.base_url = "https://api.github.com"
        self._client = None

    @property
    def client(self):
        if not self._client:
            self._client = httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/vnd.github.v3+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=15.0,
            )
        return self._client

    def _repo_url(self, repo: str = "") -> str:
        r = repo or self.default_repo
        return f"{self.base_url}/repos/{r}"

    def get_status(self) -> dict:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "provider": "github",
            "default_repo": self.default_repo,
        }

    # ─── Commits ─────────────────────────────────────────

    async def list_commits(
        self,
        repo: str = "",
        branch: str = "main",
        limit: int = 20,
        path: str = "",
        since: str = "",
    ) -> dict:
        """List recent commits. Optional path filter for file-specific history."""
        params = {"sha": branch, "per_page": min(limit, 100)}
        if path:
            params["path"] = path
        if since:
            params["since"] = since

        start = time.time()
        try:
            resp = await self.client.get(
                f"{self._repo_url(repo)}/commits", params=params
            )
            resp.raise_for_status()
            commits = resp.json()

            result = {
                "commits": [
                    {
                        "sha": c["sha"][:7],
                        "sha_full": c["sha"],
                        "message": c["commit"]["message"].split("\n")[0],
                        "author": c["commit"]["author"]["name"],
                        "date": c["commit"]["author"]["date"],
                        "url": c["html_url"],
                    }
                    for c in commits
                ],
                "count": len(commits),
                "branch": branch,
                "repo": repo or self.default_repo,
                "_provider": "github",
                "_source": "live",
            }
            self.record_event(
                latency_ms=(time.time() - start) * 1000,
                query=f"commits:{branch}:{path or 'all'}",
            )
            return result
        except httpx.HTTPError as e:
            logger.warning(f"GitHub connector error in list_commits: {e}")
            self.record_event(
                latency_ms=(time.time() - start) * 1000,
                query=f"commits:{branch}:{path or 'all'}",
                error=str(e),
            )
            return {"error": str(e), "commits": []}

    # ─── Pull Requests ───────────────────────────────────

    async def list_pulls(
        self,
        repo: str = "",
        state: str = "open",
        limit: int = 20,
    ) -> dict:
        """List pull requests."""
        params = {"state": state, "per_page": min(limit, 100), "sort": "updated", "direction": "desc"}

        start = time.time()
        try:
            resp = await self.client.get(
                f"{self._repo_url(repo)}/pulls", params=params
            )
            resp.raise_for_status()
            pulls = resp.json()

            result = {
                "pulls": [
                    {
                        "number": p["number"],
                        "title": p["title"],
                        "state": p["state"],
                        "author": p["user"]["login"],
                        "branch": p["head"]["ref"],
                        "base": p["base"]["ref"],
                        "created": p["created_at"],
                        "updated": p["updated_at"],
                        "url": p["html_url"],
                        "mergeable": p.get("mergeable"),
                        "additions": p.get("additions", 0),
                        "deletions": p.get("deletions", 0),
                    }
                    for p in pulls
                ],
                "count": len(pulls),
                "state_filter": state,
                "_provider": "github",
                "_source": "live",
            }
            self.record_event(
                latency_ms=(time.time() - start) * 1000,
                query=f"pulls:{state}",
            )
            return result
        except httpx.HTTPError as e:
            logger.warning(f"GitHub connector error in list_pulls: {e}")
            self.record_event(
                latency_ms=(time.time() - start) * 1000,
                query=f"pulls:{state}",
                error=str(e),
            )
            return {"error": str(e), "pulls": []}

    # ─── Issues ──────────────────────────────────────────

    async def list_issues(
        self,
        repo: str = "",
        state: str = "open",
        labels: str = "",
        limit: int = 20,
    ) -> dict:
        """List issues (excludes PRs)."""
        params = {"state": state, "per_page": min(limit, 100), "sort": "updated", "direction": "desc"}
        if labels:
            params["labels"] = labels

        start = time.time()
        try:
            resp = await self.client.get(
                f"{self._repo_url(repo)}/issues", params=params
            )
            resp.raise_for_status()
            # GitHub API returns PRs in issues endpoint — filter them out
            issues = [i for i in resp.json() if "pull_request" not in i]

            result = {
                "issues": [
                    {
                        "number": i["number"],
                        "title": i["title"],
                        "state": i["state"],
                        "author": i["user"]["login"],
                        "labels": [l["name"] for l in i.get("labels", [])],
                        "created": i["created_at"],
                        "updated": i["updated_at"],
                        "url": i["html_url"],
                        "comments": i.get("comments", 0),
                    }
                    for i in issues
                ],
                "count": len(issues),
                "state_filter": state,
                "_provider": "github",
                "_source": "live",
            }
            self.record_event(
                latency_ms=(time.time() - start) * 1000,
                query=f"issues:{state}",
            )
            return result
        except httpx.HTTPError as e:
            logger.warning(f"GitHub connector error in list_issues: {e}")
            self.record_event(
                latency_ms=(time.time() - start) * 1000,
                query=f"issues:{state}",
                error=str(e),
            )
            return {"error": str(e), "issues": []}

    # ─── File Tree ───────────────────────────────────────

    async def get_tree(
        self,
        repo: str = "",
        path: str = "",
        branch: str = "main",
    ) -> dict:
        """Get directory contents at a path."""
        url = f"{self._repo_url(repo)}/contents/{path}"
        params = {"ref": branch}

        start = time.time()
        try:
            resp = await self.client.get(url, params=params)
            resp.raise_for_status()
            items = resp.json()

            if isinstance(items, list):
                result = {
                    "path": path or "/",
                    "items": [
                        {
                            "name": i["name"],
                            "type": i["type"],
                            "size": i.get("size", 0),
                            "path": i["path"],
                        }
                        for i in items
                    ],
                    "count": len(items),
                    "_provider": "github",
                    "_source": "live",
                }
            else:
                # Single file — return metadata (not content, too large)
                result = {
                    "path": items["path"],
                    "type": "file",
                    "size": items.get("size", 0),
                    "encoding": items.get("encoding"),
                    "_provider": "github",
                    "_source": "live",
                }

            self.record_event(
                latency_ms=(time.time() - start) * 1000,
                query=f"tree:{path or '/'}",
            )
            return result
        except httpx.HTTPError as e:
            logger.warning(f"GitHub connector error in get_tree: {e}")
            self.record_event(
                latency_ms=(time.time() - start) * 1000,
                query=f"tree:{path or '/'}",
                error=str(e),
            )
            return {"error": str(e), "items": []}

    # ─── File Content ────────────────────────────────────

    async def get_file(
        self,
        path: str,
        repo: str = "",
        branch: str = "main",
    ) -> dict:
        """Read a single file's content. Returns raw text for files under 1MB."""
        url = f"{self._repo_url(repo)}/contents/{path}"
        params = {"ref": branch}

        start = time.time()
        try:
            resp = await self.client.get(
                url,
                params=params,
                headers={
                    **dict(self.client.headers),
                    "Accept": "application/vnd.github.v3.raw",
                },
            )
            resp.raise_for_status()

            content = resp.text
            full_size = len(content)
            # Truncate large files
            truncated = full_size > self.MAX_FILE_CONTENT_SIZE
            if truncated:
                content = content[:self.MAX_FILE_CONTENT_SIZE] + f"\n\n... [truncated at {self.MAX_FILE_CONTENT_SIZE} chars, full file is {full_size} chars]"

            result = {
                "path": path,
                "content": content,
                "size": full_size,
                "truncated": truncated,
                "_provider": "github",
                "_source": "live",
            }
            self.record_event(
                latency_ms=(time.time() - start) * 1000,
                query=f"file:{path}",
            )
            return result
        except httpx.HTTPError as e:
            logger.warning(f"GitHub connector error in get_file: {e}")
            self.record_event(
                latency_ms=(time.time() - start) * 1000,
                query=f"file:{path}",
                error=str(e),
            )
            return {"error": str(e), "content": ""}

    # ─── Repo Stats ──────────────────────────────────────

    async def repo_info(self, repo: str = "") -> dict:
        """Get repository metadata."""
        start = time.time()
        try:
            resp = await self.client.get(self._repo_url(repo))
            resp.raise_for_status()
            r = resp.json()

            result = {
                "name": r["full_name"],
                "description": r.get("description", ""),
                "default_branch": r["default_branch"],
                "visibility": r["visibility"],
                "language": r.get("language"),
                "size_kb": r.get("size", 0),
                "open_issues": r.get("open_issues_count", 0),
                "stars": r.get("stargazers_count", 0),
                "updated": r.get("updated_at"),
                "pushed": r.get("pushed_at"),
                "_provider": "github",
                "_source": "live",
            }
            self.record_event(
                latency_ms=(time.time() - start) * 1000,
                query="repo_info",
            )
            return result
        except httpx.HTTPError as e:
            logger.warning(f"GitHub connector error in repo_info: {e}")
            self.record_event(
                latency_ms=(time.time() - start) * 1000,
                query="repo_info",
                error=str(e),
            )
            return {"error": str(e)}

    # ─── Search Code ─────────────────────────────────────

    async def search_code(self, query: str, limit: int = 20) -> dict:
        """Search code in the repository via GitHub Search API."""
        if not self.enabled:
            return {"error": "GitHub not configured", "matches": []}

        # Extract owner from default_repo (owner/repo format)
        owner = self.default_repo.split("/")[0] if "/" in self.default_repo else ""
        repo_qualifier = f"repo:{owner}/{self.default_repo.split('/')[-1]}" if owner else f"repo:{self.default_repo}"
        full_query = f"{query} {repo_qualifier}"

        start = time.time()
        try:
            resp = await self.client.get(
                f"{self.base_url}/search/code",
                params={"q": full_query, "per_page": min(limit, 100)},
            )
            resp.raise_for_status()
            data = resp.json()

            result = {
                "matches": [
                    {
                        "path": item["path"],
                        "name": item["name"],
                        "sha": item["sha"][:7],
                        "url": item["html_url"],
                        "score": item.get("score", 0),
                    }
                    for item in data.get("items", [])
                ],
                "total_count": data.get("total_count", 0),
                "query": query,
                "_provider": "github",
                "_source": "live",
            }
            self.record_event(
                latency_ms=(time.time() - start) * 1000,
                query=f"search:{query}",
            )
            return result
        except httpx.HTTPError as e:
            logger.warning(f"GitHub connector error in search_code: {e}")
            self.record_event(
                latency_ms=(time.time() - start) * 1000,
                query=f"search:{query}",
                error=str(e),
            )
            return {"error": str(e), "matches": []}

    # ─── Get Commit Detail ───────────────────────────────

    async def get_commit(self, sha: str, repo: str = "") -> dict:
        """Get detailed information about a specific commit."""
        if not self.enabled:
            return {"error": "GitHub not configured"}

        start = time.time()
        try:
            resp = await self.client.get(
                f"{self._repo_url(repo)}/commits/{sha}"
            )
            resp.raise_for_status()
            c = resp.json()

            files = c.get("files", [])[:50]  # Cap at 50 to prevent huge responses
            result = {
                "sha": c["sha"],
                "message": c["commit"]["message"],
                "author": c["commit"]["author"]["name"],
                "date": c["commit"]["author"]["date"],
                "stats": c.get("stats", {}),
                "files": [
                    {
                        "filename": f["filename"],
                        "status": f["status"],
                        "additions": f.get("additions", 0),
                        "deletions": f.get("deletions", 0),
                        "changes": f.get("changes", 0),
                    }
                    for f in files
                ],
                "file_count": len(c.get("files", [])),
                "_provider": "github",
                "_source": "live",
            }
            self.record_event(
                latency_ms=(time.time() - start) * 1000,
                query=f"commit:{sha}",
            )
            return result
        except httpx.HTTPError as e:
            logger.warning(f"GitHub connector error in get_commit: {e}")
            self.record_event(
                latency_ms=(time.time() - start) * 1000,
                query=f"commit:{sha}",
                error=str(e),
            )
            return {"error": str(e)}

    # ─── Get Issue Detail ────────────────────────────────

    async def get_issue(self, number: int, repo: str = "") -> dict:
        """Get detailed information about a specific issue."""
        if not self.enabled:
            return {"error": "GitHub not configured"}

        start = time.time()
        try:
            resp = await self.client.get(
                f"{self._repo_url(repo)}/issues/{number}"
            )
            resp.raise_for_status()
            i = resp.json()

            body = i.get("body") or ""
            if len(body) > 5000:
                body = body[:5000] + "\n\n... [truncated]"

            result = {
                "number": i["number"],
                "title": i["title"],
                "body": body,
                "state": i["state"],
                "labels": [l["name"] for l in i.get("labels", [])],
                "assignees": [a["login"] for a in i.get("assignees", [])],
                "author": i["user"]["login"],
                "created": i["created_at"],
                "updated": i["updated_at"],
                "comments": i.get("comments", 0),
                "url": i["html_url"],
                "_provider": "github",
                "_source": "live",
            }
            self.record_event(
                latency_ms=(time.time() - start) * 1000,
                query=f"issue:{number}",
            )
            return result
        except httpx.HTTPError as e:
            logger.warning(f"GitHub connector error in get_issue: {e}")
            self.record_event(
                latency_ms=(time.time() - start) * 1000,
                query=f"issue:{number}",
                error=str(e),
            )
            return {"error": str(e)}

    # ─── Create Issue ────────────────────────────────────

    async def create_issue(
        self,
        title: str,
        body: str = "",
        labels: list[str] = None,
        assignees: list[str] = None,
        repo: str = "",
    ) -> dict:
        """Create a new GitHub issue."""
        if not self.enabled:
            return {"error": "GitHub not configured"}

        payload: dict = {"title": title}
        if body:
            payload["body"] = body
        if labels:
            payload["labels"] = labels
        if assignees:
            payload["assignees"] = assignees

        start = time.time()
        try:
            resp = await self.client.post(
                f"{self._repo_url(repo)}/issues",
                json=payload,
            )
            resp.raise_for_status()
            i = resp.json()

            result = {
                "number": i["number"],
                "title": i["title"],
                "url": i["html_url"],
                "created": i["created_at"],
                "_provider": "github",
                "_source": "live",
            }
            self.record_event(
                latency_ms=(time.time() - start) * 1000,
                query=f"create_issue:{title[:30]}",
            )
            return result
        except httpx.HTTPError as e:
            logger.warning(f"GitHub connector error in create_issue: {e}")
            self.record_event(
                latency_ms=(time.time() - start) * 1000,
                query=f"create_issue:{title[:30]}",
                error=str(e),
            )
            return {"error": str(e)}

    # ─── Create Branch ───────────────────────────────────

    async def create_branch(
        self,
        branch_name: str,
        from_sha: str,
        repo: str = "",
    ) -> dict:
        """Create a new branch from a commit SHA."""
        if not self.enabled:
            return {"error": "GitHub not configured"}

        payload = {
            "ref": f"refs/heads/{branch_name}",
            "sha": from_sha,
        }

        start = time.time()
        try:
            resp = await self.client.post(
                f"{self._repo_url(repo)}/git/refs",
                json=payload,
            )
            resp.raise_for_status()
            ref = resp.json()

            result = {
                "ref": ref["ref"],
                "sha": ref["object"]["sha"],
                "_provider": "github",
                "_source": "live",
            }
            self.record_event(
                latency_ms=(time.time() - start) * 1000,
                query=f"create_branch:{branch_name}",
            )
            return result
        except httpx.HTTPError as e:
            logger.warning(f"GitHub connector error in create_branch: {e}")
            self.record_event(
                latency_ms=(time.time() - start) * 1000,
                query=f"create_branch:{branch_name}",
                error=str(e),
            )
            return {"error": str(e)}

    # ─── Create or Update File ───────────────────────────

    async def create_or_update_file(
        self,
        path: str,
        content: str,
        message: str,
        branch: str = "main",
        sha: str = "",
        repo: str = "",
    ) -> dict:
        """Create or update a file in the repository. Pass sha to update existing file."""
        if not self.enabled:
            return {"error": "GitHub not configured"}

        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        payload: dict = {
            "message": message,
            "content": encoded,
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha

        start = time.time()
        try:
            resp = await self.client.put(
                f"{self._repo_url(repo)}/contents/{path}",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

            result = {
                "path": data["content"]["path"],
                "sha": data["content"]["sha"],
                "commit_sha": data["commit"]["sha"],
                "_provider": "github",
                "_source": "live",
            }
            self.record_event(
                latency_ms=(time.time() - start) * 1000,
                query=f"update_file:{path}",
            )
            return result
        except httpx.HTTPError as e:
            logger.warning(f"GitHub connector error in create_or_update_file: {e}")
            self.record_event(
                latency_ms=(time.time() - start) * 1000,
                query=f"update_file:{path}",
                error=str(e),
            )
            return {"error": str(e)}


# ─── Connector Registry ─────────────────────────────────

class ConnectorRegistry:
    """Registry of all available MCP connectors."""

    def __init__(self):
        self.connectors: dict[str, BaseConnector] = {}

    def register(self, connector: BaseConnector):
        self.connectors[connector.name] = connector

    def get(self, name: str) -> Optional[BaseConnector]:
        return self.connectors.get(name)

    def get_status(self) -> dict:
        return {
            name: c.get_status()
            for name, c in self.connectors.items()
        }

    @property
    def enabled_count(self) -> int:
        return sum(1 for c in self.connectors.values() if c.enabled)


def init_connectors(
    calendar_api_key: str = "",
    email_api_key: str = "",
    brave_api_key: str = "",
    messages_api_key: str = "",
    contacts_api_key: str = "",
    spotify_api_key: str = "",
    maps_api_key: str = "",
    reminders_api_key: str = "",
    weather_api_key: str = "",
    stocks_api_key: str = "",
    news_api_key: str = "",
    github_token: str = "",
    github_repo: str = "",
) -> ConnectorRegistry:
    """Initialize all MCP connectors from available API keys."""
    registry = ConnectorRegistry()

    registry.register(CalendarConnector(api_key=calendar_api_key))
    registry.register(EmailConnector(api_key=email_api_key))
    registry.register(WebSearchConnector(api_key=brave_api_key))
    registry.register(MessagesConnector(api_key=messages_api_key))
    registry.register(ContactsConnector(api_key=contacts_api_key))
    registry.register(MusicConnector(api_key=spotify_api_key))
    registry.register(MapsConnector(api_key=maps_api_key))
    registry.register(RemindersConnector(api_key=reminders_api_key))
    registry.register(WeatherConnector(api_key=weather_api_key))
    registry.register(StocksConnector(api_key=stocks_api_key))
    registry.register(NewsConnector(api_key=news_api_key))
    registry.register(TimeConnector())
    registry.register(GitHubConnector(
        token=github_token,
        default_repo=github_repo,
    ))

    enabled = registry.enabled_count
    total = len(registry.connectors)
    logger.info(f"MCP connectors initialized: {enabled}/{total} enabled")

    return registry
