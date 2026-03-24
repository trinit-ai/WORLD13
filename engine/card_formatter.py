"""
TMOS13 Card Formatter — Connector Results → Typed Feed Cards

Transforms raw connector response dicts into structured FeedCard objects
for the feed portal. Each connector+operation pair has a dedicated formatter.
Unknown pairs fall back to a generic text card.
"""
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

logger = logging.getLogger("tmos13.feed.formatter")


# ─── Card Data Models ─────────────────────────────────────

@dataclass
class CardAction:
    """An action button on a feed card."""
    label: str
    query: str
    icon: str = ""

    def to_dict(self) -> dict:
        d = {"label": self.label, "query": self.query}
        if self.icon:
            d["icon"] = self.icon
        return d


@dataclass
class SourceInfo:
    """Card source metadata."""
    connector: str
    provider: str
    source_type: str  # "live" | "simulated" | "internal"
    tier: str = "free"  # "free" | "premium" | "enterprise"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FeedCard:
    """A typed card returned by the feed portal."""
    card_type: str
    title: str
    subtitle: str = ""
    data: dict = field(default_factory=dict)
    actions: list[CardAction] = field(default_factory=list)
    source: SourceInfo = field(default_factory=lambda: SourceInfo("unknown", "unknown", "unknown"))
    badge: str = ""  # "LIVE" | "DEMO" | "PREMIUM" — derived from source

    def to_dict(self) -> dict:
        badge = self.badge
        if not badge:
            if self.source.source_type == "live":
                badge = "LIVE"
            elif self.source.source_type == "internal":
                badge = "LIVE"
            elif self.source.tier in ("premium", "enterprise"):
                badge = "PREMIUM"
            else:
                badge = "DEMO"
        return {
            "card_type": self.card_type,
            "title": self.title,
            "subtitle": self.subtitle,
            "data": self.data,
            "actions": [a.to_dict() for a in self.actions],
            "source": self.source.to_dict(),
            "badge": badge,
        }


# ─── Card Formatter ──────────────────────────────────────

class CardFormatter:
    """Transforms raw connector results into typed FeedCard objects."""

    def format(self, connector: str, operation: str, result: dict) -> FeedCard:
        """Dispatch to the appropriate formatter method."""
        method_name = f"_format_{connector}_{operation}"
        formatter = getattr(self, method_name, None)
        if formatter:
            try:
                return formatter(result)
            except Exception as e:
                logger.warning(f"Formatter {method_name} failed: {e}")
                return self._format_generic(result, connector)
        return self._format_generic(result, connector)

    # ─── Weather ─────────────────────────────────────────

    def _format_weather_current(self, data: dict) -> FeedCard:
        desc = data.get("description", "").lower()
        return FeedCard(
            card_type="weather",
            title=f"{data.get('city', '?')}, {data.get('country', '?')}",
            subtitle=data.get("description", "").title(),
            data={
                "city": data.get("city", ""),
                "country": data.get("country", ""),
                "temp": data.get("temp", 0),
                "feels_like": data.get("feels_like", 0),
                "humidity": data.get("humidity", 0),
                "wind_speed": data.get("wind_speed", 0),
                "description": data.get("description", ""),
                "clouds": data.get("clouds", 0),
                "temp_high": data.get("temp_high", 0),
                "temp_low": data.get("temp_low", 0),
                "units": data.get("units", "imperial"),
            },
            actions=[
                CardAction(label="3-day forecast", query=f"forecast {data.get('city', '')}"),
            ],
            source=SourceInfo(
                connector="weather",
                provider=data.get("_provider", "OpenWeatherMap"),
                source_type=data.get("_source", "simulated"),
            ),
        )

    def _format_weather_forecast(self, data: dict) -> FeedCard:
        city = data.get("city", "?")
        days = data.get("days", [])
        subtitle = f"{len(days)}-day forecast"
        return FeedCard(
            card_type="weather_forecast",
            title=f"{city}, {data.get('country', '?')}",
            subtitle=subtitle,
            data={
                "city": city,
                "country": data.get("country", ""),
                "days": days,
                "units": data.get("units", "imperial"),
            },
            actions=[
                CardAction(label=f"Current weather", query=f"weather {city}"),
            ],
            source=SourceInfo(
                connector="weather",
                provider=data.get("_provider", "OpenWeatherMap"),
                source_type=data.get("_source", "simulated"),
            ),
        )

    # ─── Stocks ──────────────────────────────────────────

    def _format_stocks_quote(self, data: dict) -> FeedCard:
        change = data.get("change", 0)
        direction = "up" if change > 0 else "down" if change < 0 else "flat"
        arrow = "\u25b2" if direction == "up" else "\u25bc" if direction == "down" else "\u2013"
        symbol = data.get("symbol", "?")
        price = data.get("price", 0)
        pct = data.get("change_pct", 0)

        card_data = {
            "symbol": symbol,
            "price": price,
            "change": change,
            "change_pct": pct,
            "volume": data.get("volume", 0),
            "open": data.get("open", 0),
            "high": data.get("high", 0),
            "low": data.get("low", 0),
            "prev_close": data.get("prev_close", 0),
            "latest_day": data.get("latest_day", ""),
            "direction": direction,
        }

        return FeedCard(
            card_type="stock_quote",
            title=symbol,
            subtitle=f"${price:.2f} {arrow} {change:+.2f} ({pct:+.2f}%)",
            data=card_data,
            actions=[
                CardAction(label=f"News about {symbol}", query=f"news about {symbol}"),
            ],
            source=SourceInfo(
                connector="stocks",
                provider=data.get("_provider", "Alpha Vantage"),
                source_type=data.get("_source", "simulated"),
            ),
        )

    def _format_stocks_search(self, data: dict) -> FeedCard:
        results = data.get("results", [])
        query = data.get("query", "")
        return FeedCard(
            card_type="stock_search",
            title=f"Stock search: {query}",
            subtitle=f"{len(results)} result(s)",
            data={"query": query, "results": results},
            actions=[
                CardAction(label=f"Quote {results[0]['symbol']}", query=results[0]["symbol"])
            ] if results and results[0].get("symbol") != "???" else [],
            source=SourceInfo(
                connector="stocks",
                provider=data.get("_provider", "Alpha Vantage"),
                source_type=data.get("_source", "simulated"),
            ),
        )

    # ─── News ────────────────────────────────────────────

    def _format_news_top_headlines(self, data: dict) -> FeedCard:
        articles = data.get("articles", [])
        return FeedCard(
            card_type="news_feed",
            title="Top Headlines",
            subtitle=f"{len(articles)} articles",
            data={
                "articles": articles,
                "total_results": data.get("total_results", len(articles)),
            },
            actions=[
                CardAction(label="More headlines", query="latest news"),
            ],
            source=SourceInfo(
                connector="news",
                provider=data.get("_provider", "NewsAPI"),
                source_type=data.get("_source", "simulated"),
            ),
        )

    def _format_news_search(self, data: dict) -> FeedCard:
        articles = data.get("articles", [])
        topic = data.get("topic", "")
        return FeedCard(
            card_type="news_feed",
            title=f"News: {topic}" if topic else "News",
            subtitle=f"{len(articles)} articles",
            data={
                "articles": articles,
                "topic": topic,
                "total_results": data.get("total_results", len(articles)),
            },
            actions=[
                CardAction(label="Top headlines", query="news"),
            ],
            source=SourceInfo(
                connector="news",
                provider=data.get("_provider", "NewsAPI"),
                source_type=data.get("_source", "simulated"),
            ),
        )

    # ─── Time ────────────────────────────────────────────

    def _format_time_current(self, data: dict) -> FeedCard:
        tz = data.get("timezone", "UTC")
        return FeedCard(
            card_type="time",
            title=data.get("time", ""),
            subtitle=f"{data.get('date', '')} \u00b7 {tz}",
            data={
                "timezone": tz,
                "time": data.get("time", ""),
                "date": data.get("date", ""),
                "utc_offset": data.get("utc_offset", "UTC+0"),
            },
            source=SourceInfo(
                connector="time",
                provider="system",
                source_type="internal",
            ),
        )

    # ─── Web Search ──────────────────────────────────────

    def _format_web_search_search(self, data: dict) -> FeedCard:
        # WebSearchConnector.search returns a list of dicts
        results = data if isinstance(data, list) else data.get("results", [])
        return FeedCard(
            card_type="web_results",
            title="Web Results",
            subtitle=f"{len(results)} results",
            data={
                "query": "",
                "results": results[:10],
                "total_results": len(results),
            },
            source=SourceInfo(
                connector="web_search",
                provider=data.get("_provider", "Brave") if isinstance(data, dict) else "Brave",
                source_type=data.get("_source", "simulated") if isinstance(data, dict) else "simulated",
            ),
        )

    # ─── Email ───────────────────────────────────────────

    def _format_email_inbox(self, data: dict) -> FeedCard:
        # EmailConnector.search_inbox returns a list
        messages = data if isinstance(data, list) else data.get("messages", [])
        unread = sum(1 for m in messages if not m.get("read", True)) if messages else 0
        total = len(messages)
        return FeedCard(
            card_type="email_inbox",
            title="Inbox",
            subtitle=f"{unread} unread \u00b7 {total} total",
            data={
                "messages": messages,
                "total": total,
                "unread": unread,
            },
            actions=[
                CardAction(label="Unread only", query="unread emails"),
                CardAction(label="Search", query="search email"),
            ],
            source=SourceInfo(
                connector="email",
                provider=data.get("_provider", "demo") if isinstance(data, dict) else "demo",
                source_type=data.get("_source", "simulated") if isinstance(data, dict) else "simulated",
            ),
        )

    def _format_email_search(self, data: dict) -> FeedCard:
        return self._format_email_inbox(data)

    # ─── Calendar ────────────────────────────────────────

    def _format_calendar_today(self, data: dict) -> FeedCard:
        events = data if isinstance(data, list) else data.get("events", [])
        count = len(events)
        return FeedCard(
            card_type="calendar_today",
            title="Today's Schedule",
            subtitle=f"{count} event(s)",
            data={
                "date": "today",
                "events": events,
                "count": count,
            },
            actions=[
                CardAction(label="Tomorrow", query="schedule tomorrow"),
            ],
            source=SourceInfo(
                connector="calendar",
                provider=data.get("_provider", "demo") if isinstance(data, dict) else "demo",
                source_type=data.get("_source", "simulated") if isinstance(data, dict) else "simulated",
            ),
        )

    def _format_calendar_availability(self, data: dict) -> FeedCard:
        available = data.get("available", True) if isinstance(data, dict) else True
        return FeedCard(
            card_type="calendar_availability",
            title="Availability",
            subtitle="Free" if available else "Busy",
            data=data if isinstance(data, dict) else {"available_slots": []},
            source=SourceInfo(
                connector="calendar",
                provider="demo",
                source_type="simulated",
            ),
        )

    # ─── Contacts ────────────────────────────────────────

    def _format_contacts_search(self, data: dict) -> FeedCard:
        results = data if isinstance(data, list) else data.get("results", [])
        count = len(results)
        if count == 1:
            c = results[0]
            return FeedCard(
                card_type="contact",
                title=c.get("name", "Unknown"),
                subtitle=c.get("organization", c.get("company", "")),
                data={
                    "name": c.get("name", ""),
                    "role": c.get("role", ""),
                    "company": c.get("organization", c.get("company", "")),
                    "email": c.get("email", ""),
                    "phone": c.get("phone", ""),
                    "location": c.get("location", ""),
                },
                source=SourceInfo(connector="contacts", provider="demo", source_type="simulated"),
            )
        return FeedCard(
            card_type="contact_list",
            title="Contacts",
            subtitle=f"{count} result(s)",
            data={"results": results, "count": count, "query": ""},
            source=SourceInfo(connector="contacts", provider="demo", source_type="simulated"),
        )

    # ─── Reminders ───────────────────────────────────────

    def _format_reminders_list(self, data: dict) -> FeedCard:
        tasks = data if isinstance(data, list) else data.get("tasks", [])
        total = len(tasks)
        completed = sum(1 for t in tasks if t.get("completed"))
        pending = total - completed
        return FeedCard(
            card_type="reminder_list",
            title="Tasks",
            subtitle=f"{pending} pending \u00b7 {completed} done",
            data={
                "tasks": tasks,
                "total": total,
                "completed": completed,
                "pending": pending,
            },
            actions=[
                CardAction(label="Add a task", query="remind me to "),
            ],
            source=SourceInfo(connector="reminders", provider="in-memory", source_type="internal"),
        )

    def _format_reminders_create(self, data: dict) -> FeedCard:
        return FeedCard(
            card_type="reminder_created",
            title="Reminder Created",
            subtitle=data.get("title", ""),
            data={
                "id": data.get("reminder_id", ""),
                "title": data.get("title", ""),
                "due": data.get("due", ""),
            },
            actions=[
                CardAction(label="View all tasks", query="reminders"),
                CardAction(label="Add another", query="remind me to "),
            ],
            source=SourceInfo(connector="reminders", provider="in-memory", source_type="internal"),
        )

    # ─── Error Card ──────────────────────────────────────

    def format_error(
        self,
        message: str,
        error_type: str = "unknown_query",
        connector: str = "",
        suggestion: str = "",
    ) -> FeedCard:
        """Create an error card."""
        if not suggestion:
            suggestion = "Try asking for weather, stocks, news, or time."
        return FeedCard(
            card_type="error",
            title="Couldn't process that",
            subtitle=message,
            data={
                "message": message,
                "connector": connector,
                "error_type": error_type,
                "suggestion": suggestion,
            },
            source=SourceInfo(connector=connector or "none", provider="", source_type="internal"),
        )

    # ─── Generic Fallback ────────────────────────────────

    def _format_generic(self, data: Any, connector: str = "unknown") -> FeedCard:
        """Fallback for unrecognized connector results."""
        if isinstance(data, list):
            text = json.dumps(data, indent=2, default=str)
        elif isinstance(data, dict):
            # Strip internal keys
            clean = {k: v for k, v in data.items() if not k.startswith("_")}
            text = json.dumps(clean, indent=2, default=str)
        else:
            text = str(data)

        return FeedCard(
            card_type="text",
            title="Result",
            data={"text": text, "format": "plain"},
            source=SourceInfo(
                connector=connector,
                provider=data.get("_provider", "unknown") if isinstance(data, dict) else "unknown",
                source_type=data.get("_source", "unknown") if isinstance(data, dict) else "unknown",
            ),
        )
