"""
TMOS13 Monitoring & Analytics

Provides request metrics collection, performance tracking, and
Prometheus-compatible metrics export. Designed to run alongside
the main application with minimal overhead.

Usage in app.py:
    from monitoring import MetricsCollector, MonitoringMiddleware, register_monitoring_endpoints

    metrics = MetricsCollector()
    app.add_middleware(MonitoringMiddleware, metrics=metrics)
    register_monitoring_endpoints(app, metrics, sessions, db)
"""
import time
import uuid
import logging
from collections import defaultdict, deque
from typing import Any, Optional

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from config import ENV, MODEL, logger
from state import SessionState


# ─── Metrics Collector (Singleton-style) ─────────────────────


class MetricsCollector:
    """
    Central metrics collector for the TMOS13 backend.

    Tracks request counts, error rates, latencies, Claude API call
    performance, and session-level analytics. Uses a rolling deque
    of recent timing entries (last 1000) for statistical calculations.

    Designed as a singleton-style class: create one instance and
    pass it to middleware and endpoint registrars.
    """

    _instance: Optional["MetricsCollector"] = None

    def __new__(cls) -> "MetricsCollector":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        # ─── Counters ────────────────────────────────────
        self.total_requests: int = 0
        self.total_errors: int = 0
        self.total_claude_calls: int = 0
        self.total_tokens_estimated: int = 0
        self.total_cache_creation_tokens: int = 0
        self.total_cache_read_tokens: int = 0
        self.total_citation_responses: int = 0

        # ─── Per-endpoint request counts ─────────────────
        self.endpoint_counts: dict[str, int] = defaultdict(int)

        # ─── Active sessions gauge ───────────────────────
        self.active_sessions: int = 0

        # ─── Request latency tracking (rolling window) ───
        self._request_latencies: deque[float] = deque(maxlen=1000)

        # ─── Claude API call tracking (rolling window) ───
        self._claude_latencies: deque[float] = deque(maxlen=1000)
        self._claude_tokens: deque[int] = deque(maxlen=1000)

        # ─── Startup time ───────────────────────────────
        self.started_at: float = time.time()

    def record_request(
        self, endpoint: str, latency_ms: float, error: bool = False
    ) -> None:
        """
        Record an HTTP request.

        Args:
            endpoint: The request path (e.g. "/chat", "/ws").
            latency_ms: Response time in milliseconds.
            error: Whether the request resulted in an error (4xx/5xx).
        """
        self.total_requests += 1
        self.endpoint_counts[endpoint] += 1
        self._request_latencies.append(latency_ms)

        if error:
            self.total_errors += 1

    def record_claude_call(
        self, latency_ms: float, tokens_estimated: int = 0,
        cache_creation_tokens: int = 0, cache_read_tokens: int = 0,
        has_citations: bool = False,
    ) -> None:
        """
        Record a Claude API call.

        Args:
            latency_ms: API call duration in milliseconds.
            tokens_estimated: Estimated token count for the prompt.
            cache_creation_tokens: Tokens written to prompt cache this call.
            cache_read_tokens: Tokens read from prompt cache this call.
            has_citations: Whether the response contained citation references.
        """
        self.total_claude_calls += 1
        self._claude_latencies.append(latency_ms)

        if tokens_estimated > 0:
            self.total_tokens_estimated += tokens_estimated
            self._claude_tokens.append(tokens_estimated)

        self.total_cache_creation_tokens += cache_creation_tokens
        self.total_cache_read_tokens += cache_read_tokens

        if has_citations:
            self.total_citation_responses += 1

    def _compute_stats(self, data: deque[float]) -> dict[str, float]:
        """Compute min, max, avg, p95, p99 from a deque of values."""
        if not data:
            return {
                "min": 0.0,
                "max": 0.0,
                "avg": 0.0,
                "p95": 0.0,
                "p99": 0.0,
                "count": 0,
            }

        sorted_data = sorted(data)
        n = len(sorted_data)

        return {
            "min": round(sorted_data[0], 2),
            "max": round(sorted_data[-1], 2),
            "avg": round(sum(sorted_data) / n, 2),
            "p95": round(sorted_data[int(n * 0.95)] if n > 1 else sorted_data[0], 2),
            "p99": round(sorted_data[int(n * 0.99)] if n > 1 else sorted_data[0], 2),
            "count": n,
        }

    def get_metrics(self) -> dict[str, Any]:
        """
        Return all current metrics as a dictionary.

        Includes counters, per-endpoint breakdowns, latency stats,
        and Claude API call performance.
        """
        uptime_seconds = time.time() - self.started_at

        return {
            "uptime_seconds": round(uptime_seconds, 1),
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "error_rate": round(
                self.total_errors / max(self.total_requests, 1), 4
            ),
            "total_claude_calls": self.total_claude_calls,
            "total_tokens_estimated": self.total_tokens_estimated,
            "prompt_cache": {
                "cache_creation_tokens": self.total_cache_creation_tokens,
                "cache_read_tokens": self.total_cache_read_tokens,
                "cache_hit_rate": round(
                    self.total_cache_read_tokens
                    / max(self.total_cache_read_tokens + self.total_cache_creation_tokens, 1),
                    4,
                ),
            },
            "citations": {
                "total_responses_with_citations": self.total_citation_responses,
                "citation_rate": round(
                    self.total_citation_responses / max(self.total_claude_calls, 1), 4
                ),
            },
            "active_sessions": self.active_sessions,
            "requests_per_second": round(
                self.total_requests / max(uptime_seconds, 1), 2
            ),
            "endpoint_counts": dict(self.endpoint_counts),
            "request_latency_ms": self._compute_stats(self._request_latencies),
            "claude_latency_ms": self._compute_stats(self._claude_latencies),
        }

    def get_analytics(
        self, sessions: dict[str, SessionState]
    ) -> dict[str, Any]:
        """
        Return session-level analytics.

        Computes cartridge distribution, average depth, average
        turns, and mood distribution across all active sessions.

        Args:
            sessions: The active sessions dict from app.py.
        """
        if not sessions:
            return {
                "active_sessions": 0,
                "cartridge_distribution": {},
                "avg_depth": 0.0,
                "avg_turns": 0.0,
                "mood_distribution": {},
                "users": {
                    "anonymous": 0,
                    "identified": 0,
                },
            }

        # Cartridge visit distribution
        cartridge_counts: dict[str, int] = defaultdict(int)
        for state in sessions.values():
            for cart in state.games_played:
                cartridge_counts[cart] += 1

        # Depth and turn averages
        depths = [s.depth for s in sessions.values()]
        turns = [s.turn_count for s in sessions.values()]

        avg_depth = sum(depths) / len(depths) if depths else 0.0
        avg_turns = sum(turns) / len(turns) if turns else 0.0

        # Mood distribution
        mood_counts: dict[str, int] = defaultdict(int)
        for state in sessions.values():
            mood_counts[state.mood] += 1

        # User identification
        anon_count = sum(
            1 for s in sessions.values() if s.user_id == "anonymous"
        )

        return {
            "active_sessions": len(sessions),
            "cartridge_distribution": dict(cartridge_counts),
            "avg_depth": round(avg_depth, 2),
            "avg_turns": round(avg_turns, 2),
            "mood_distribution": dict(mood_counts),
            "users": {
                "anonymous": anon_count,
                "identified": len(sessions) - anon_count,
            },
        }


# ─── Monitoring Middleware ───────────────────────────────────


class MonitoringMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that records request timing for every HTTP request.

    Adds headers:
        X-Request-Id: unique request identifier (UUID4)
        X-Response-Time: response time in milliseconds

    Logs slow requests (>2s) at WARNING level.
    """

    def __init__(self, app: ASGIApp, metrics: MetricsCollector) -> None:
        super().__init__(app)
        self.metrics = metrics

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        endpoint = request.url.path
        is_error = response.status_code >= 400

        # Record in metrics collector
        self.metrics.record_request(endpoint, elapsed_ms, error=is_error)

        # Add response headers
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Response-Time"] = f"{elapsed_ms:.2f}ms"

        # Log slow requests
        if elapsed_ms > 2000.0:
            logger.warning(
                f"[Monitoring] Slow request: {request.method} {endpoint} "
                f"took {elapsed_ms:.0f}ms (request_id={request_id})"
            )

        return response


# ─── Monitoring Endpoints ────────────────────────────────────


def _format_prometheus(metrics: dict[str, Any], sessions_count: int) -> str:
    """
    Format metrics as Prometheus-compatible text exposition format.

    Reference: https://prometheus.io/docs/instrumenting/exposition_formats/
    """
    lines: list[str] = []

    def _metric(name: str, value: Any, help_text: str, mtype: str = "gauge") -> None:
        lines.append(f"# HELP tmos13_{name} {help_text}")
        lines.append(f"# TYPE tmos13_{name} {mtype}")
        lines.append(f"tmos13_{name} {value}")

    _metric("uptime_seconds", metrics["uptime_seconds"], "Server uptime in seconds")
    _metric(
        "requests_total",
        metrics["total_requests"],
        "Total HTTP requests processed",
        "counter",
    )
    _metric(
        "errors_total",
        metrics["total_errors"],
        "Total HTTP errors (4xx/5xx)",
        "counter",
    )
    _metric("error_rate", metrics["error_rate"], "Current error rate (0-1)")
    _metric(
        "claude_calls_total",
        metrics["total_claude_calls"],
        "Total Claude API calls made",
        "counter",
    )
    _metric(
        "tokens_estimated_total",
        metrics["total_tokens_estimated"],
        "Total estimated prompt tokens sent",
        "counter",
    )
    _metric(
        "prompt_cache_creation_tokens_total",
        metrics["prompt_cache"]["cache_creation_tokens"],
        "Total tokens written to Anthropic prompt cache",
        "counter",
    )
    _metric(
        "prompt_cache_read_tokens_total",
        metrics["prompt_cache"]["cache_read_tokens"],
        "Total tokens read from Anthropic prompt cache",
        "counter",
    )
    _metric(
        "prompt_cache_hit_rate",
        metrics["prompt_cache"]["cache_hit_rate"],
        "Prompt cache hit rate (0-1)",
    )
    _metric(
        "citation_responses_total",
        metrics["citations"]["total_responses_with_citations"],
        "Total Claude API responses containing citations",
        "counter",
    )
    _metric(
        "citation_rate",
        metrics["citations"]["citation_rate"],
        "Rate of responses containing citations (0-1)",
    )
    _metric(
        "active_sessions",
        sessions_count,
        "Current number of active sessions",
    )
    _metric(
        "requests_per_second",
        metrics["requests_per_second"],
        "Average requests per second since startup",
    )

    # Request latency stats
    req_lat = metrics["request_latency_ms"]
    _metric(
        "request_latency_ms_avg",
        req_lat["avg"],
        "Average request latency in ms",
    )
    _metric(
        "request_latency_ms_p95",
        req_lat["p95"],
        "95th percentile request latency in ms",
    )
    _metric(
        "request_latency_ms_p99",
        req_lat["p99"],
        "99th percentile request latency in ms",
    )

    # Claude API latency stats
    claude_lat = metrics["claude_latency_ms"]
    _metric(
        "claude_latency_ms_avg",
        claude_lat["avg"],
        "Average Claude API call latency in ms",
    )
    _metric(
        "claude_latency_ms_p95",
        claude_lat["p95"],
        "95th percentile Claude API call latency in ms",
    )
    _metric(
        "claude_latency_ms_p99",
        claude_lat["p99"],
        "99th percentile Claude API call latency in ms",
    )

    # Per-endpoint request counts
    for endpoint, count in metrics.get("endpoint_counts", {}).items():
        safe_endpoint = endpoint.replace("/", "_").strip("_") or "root"
        lines.append(
            f'tmos13_endpoint_requests_total{{endpoint="{endpoint}"}} {count}'
        )

    return "\n".join(lines) + "\n"


def _require_metrics_auth():
    """
    FastAPI dependency: require authentication for monitoring endpoints.

    Supports two modes:
      1. API key via TMOS13_METRICS_KEY env var — clients send
         Authorization: Bearer <key> header. Best for Prometheus scrapers.
      2. JWT auth via the standard auth service — for dashboard access
         by authenticated users.

    If TMOS13_METRICS_KEY is not set and auth is disabled, monitoring
    endpoints are open (development mode only).
    """
    import os
    from fastapi import Depends, HTTPException
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

    _bearer = HTTPBearer(auto_error=False)
    _metrics_key = os.environ.get("TMOS13_METRICS_KEY", "")

    async def _verify(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    ):
        # If no metrics key is configured, fall back to JWT auth
        if not _metrics_key:
            # Try JWT auth
            try:
                from auth import get_auth_service
                auth = get_auth_service()
                if auth.enabled and credentials:
                    auth.verify_token(credentials.credentials)
                    return  # JWT valid
                elif auth.enabled and not credentials:
                    raise HTTPException(401, "Authentication required for monitoring endpoints")
            except HTTPException:
                raise
            except Exception:
                pass  # auth not initialized — allow in dev
            return

        # API key mode
        if not credentials:
            raise HTTPException(
                401,
                "Authentication required for monitoring endpoints. "
                "Provide Authorization: Bearer <TMOS13_METRICS_KEY>",
            )
        if credentials.credentials != _metrics_key:
            raise HTTPException(403, "Invalid metrics API key")

    return _verify


def register_monitoring_endpoints(
    app: FastAPI,
    metrics: MetricsCollector,
    sessions: dict[str, SessionState],
    db: Any,
) -> None:
    """
    Register monitoring and analytics endpoints on the FastAPI app.

    Routes:
        GET /metrics              - Prometheus-compatible text format metrics
        GET /monitoring/dashboard - JSON dashboard with all stats
        GET /monitoring/analytics - Session analytics

    All monitoring endpoints require authentication via either
    TMOS13_METRICS_KEY (API key) or JWT bearer token.
    """
    from fastapi import Depends

    _auth_dep = _require_metrics_auth()

    logger.info("[Monitoring] Registering monitoring endpoints (/metrics, /monitoring/*)")

    # ─── GET /metrics ────────────────────────────────────

    @app.get("/metrics", dependencies=[Depends(_auth_dep)])
    async def prometheus_metrics() -> PlainTextResponse:
        """Prometheus-compatible metrics endpoint. Requires authentication."""
        # Update the active sessions gauge before reporting
        metrics.active_sessions = len(sessions)
        current_metrics = metrics.get_metrics()
        text = _format_prometheus(current_metrics, len(sessions))
        return PlainTextResponse(
            content=text,
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    # ─── GET /monitoring/dashboard ───────────────────────

    @app.get("/monitoring/dashboard", dependencies=[Depends(_auth_dep)])
    async def monitoring_dashboard() -> dict[str, Any]:
        """
        Full monitoring dashboard as JSON. Requires authentication.

        Includes server metrics, session analytics, and system info.
        """
        metrics.active_sessions = len(sessions)
        current_metrics = metrics.get_metrics()
        analytics = metrics.get_analytics(sessions)

        return {
            "server": {
                "env": ENV,
                "model": MODEL,
                "uptime_seconds": current_metrics["uptime_seconds"],
            },
            "metrics": current_metrics,
            "analytics": analytics,
            "health": {
                "status": "online",
                "active_sessions": len(sessions),
                "error_rate": current_metrics["error_rate"],
                "avg_response_ms": current_metrics["request_latency_ms"]["avg"],
                "avg_claude_ms": current_metrics["claude_latency_ms"]["avg"],
            },
        }

    # ─── GET /monitoring/analytics ───────────────────────

    @app.get("/monitoring/analytics", dependencies=[Depends(_auth_dep)])
    async def monitoring_analytics() -> dict[str, Any]:
        """Session analytics: cartridge distribution, depth, turns, mood. Requires authentication."""
        return metrics.get_analytics(sessions)
