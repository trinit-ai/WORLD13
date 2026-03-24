"""
TMOS13 Error Handling

Standard error model for all API responses.
Provides consistent error shape: {"error": {"code": "...", "message": "..."}}
"""
from enum import Enum

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel


# ─── Error Codes ─────────────────────────────────────────

class ErrorCode(str, Enum):
    """Standard error codes returned by all API endpoints."""
    # Client errors (4xx)
    VALIDATION_ERROR = "validation_error"
    INVALID_INPUT = "invalid_input"
    RATE_LIMITED = "rate_limited"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    SESSION_NOT_FOUND = "session_not_found"
    SESSION_EXPIRED = "session_expired"
    MESSAGE_TOO_LONG = "message_too_long"
    INVALID_PACK = "invalid_pack"
    BOT_DETECTED = "bot_detected"
    CHALLENGE_REQUIRED = "challenge_required"
    SPEND_CAP_REACHED = "spend_cap_reached"

    # Server errors (5xx)
    INTERNAL_ERROR = "internal_error"
    LLM_ERROR = "llm_error"
    DATABASE_ERROR = "database_error"
    SERVICE_UNAVAILABLE = "service_unavailable"


# ─── Response Models ─────────────────────────────────────

class ErrorDetail(BaseModel):
    """Structured error detail included in all error responses."""
    code: str
    message: str

class ErrorResponse(BaseModel):
    """Standard error response shape. All API errors return this."""
    error: ErrorDetail


# ─── Exception Class ─────────────────────────────────────

class APIError(Exception):
    """
    Raise from any endpoint to return a structured error response.

    Usage:
        raise APIError(ErrorCode.RATE_LIMITED, "Too many requests", 429)
    """
    def __init__(self, code: ErrorCode | str, message: str, status_code: int = 400):
        self.code = code if isinstance(code, str) else code.value
        self.message = message
        self.status_code = status_code
        super().__init__(message)


# ─── Exception Handlers ─────────────────────────────────

async def api_error_handler(_request: Request, exc: APIError) -> JSONResponse:
    """Handle APIError exceptions with structured response."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    """Convert FastAPI's HTTPException to our standard error shape."""
    # Map common HTTP status codes to our error codes
    code_map = {
        400: ErrorCode.VALIDATION_ERROR,
        401: ErrorCode.UNAUTHORIZED,
        403: ErrorCode.FORBIDDEN,
        404: ErrorCode.NOT_FOUND,
        422: ErrorCode.VALIDATION_ERROR,
        429: ErrorCode.RATE_LIMITED,
        500: ErrorCode.INTERNAL_ERROR,
        503: ErrorCode.SERVICE_UNAVAILABLE,
    }
    code = code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code.value, "message": message}},
    )


async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions. Returns 500 with generic message."""
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": "An unexpected error occurred",
            }
        },
    )


def register_error_handlers(app):
    """Register all error handlers on a FastAPI app."""
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
