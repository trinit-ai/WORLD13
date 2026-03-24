"""
TMOS13 Security Headers Middleware

Adds standard security headers to all HTTP responses.
Required for SOC 2 compliance and general hardening.

Headers added:
    X-Request-ID (correlation ID for audit trail)
    Strict-Transport-Security (HSTS)
    X-Content-Type-Options
    X-Frame-Options
    X-XSS-Protection
    Referrer-Policy
    Permissions-Policy
    Content-Security-Policy (configurable)
    Cache-Control (for sensitive endpoints)
"""
import logging
import uuid
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

logger = logging.getLogger("tmos13.security")

# Endpoints that should never be cached
_SENSITIVE_PATHS = frozenset({
    "/auth/", "/privacy/", "/billing/", "/monitoring/",
    "/metrics", "/alerts", "/transcripts",
})


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects security headers on every HTTP response.

    Args:
        app: The ASGI application.
        environment: 'production' or 'development'. HSTS is only
                     enforced in production.
        csp_policy: Optional Content-Security-Policy override.
    """

    def __init__(
        self,
        app: ASGIApp,
        environment: str = "development",
        csp_policy: Optional[str] = None,
    ) -> None:
        super().__init__(app)
        self.environment = environment
        self.csp_policy = csp_policy or self._default_csp()

    def _default_csp(self) -> str:
        """Sensible default CSP for an API server."""
        return "; ".join([
            "default-src 'none'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ])

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Request ID correlation — SOC 2 Processing Integrity (CC7.1)
        # Accept client-provided ID or generate one. Flows through logs for audit trail.
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)

        response.headers["X-Request-ID"] = request_id

        # HSTS — only in production (requires HTTPS)
        if self.environment == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Prevent MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Clickjacking protection
        response.headers["X-Frame-Options"] = "DENY"

        # Legacy XSS filter (still respected by some browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer policy — send origin only, no full URL
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy — disable sensitive browser features
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), "
            "payment=(), usb=(), magnetometer=(), gyroscope=()"
        )

        # Content Security Policy
        response.headers["Content-Security-Policy"] = self.csp_policy

        # Cache-Control for sensitive endpoints
        path = request.url.path
        if any(path.startswith(p) for p in _SENSITIVE_PATHS):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"

        return response
