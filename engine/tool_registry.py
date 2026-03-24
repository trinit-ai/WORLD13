"""
TMOS13 Scoped Tool Action Registry

Loads tool declarations from pack manifests, validates action requests
from the LLM pipeline, and dispatches to provider-specific handlers.

SAFETY PRINCIPLES:
- Tools are ONLY available if declared in the active pack's manifest
- Each tool has explicit scopes — the engine rejects out-of-scope operations
- requires_confirmation tools need user consent before execution
- All executions are logged to the tool_audit table
- The model emits action REQUESTS; the engine VALIDATES and EXECUTES
"""
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from tool_providers.base import ToolProvider

logger = logging.getLogger("tmos13.tools")

# ─── Rate Limiting ───────────────────────────────────────────

_DEFAULT_TOOL_RATE_LIMIT = 30  # per pack per hour
_tool_rate_counters: dict[str, list[float]] = {}


def _check_tool_rate_limit(pack_id: str, tool_id: str, limit: int = _DEFAULT_TOOL_RATE_LIMIT) -> bool:
    """Returns True if rate limit exceeded (should block)."""
    key = f"{pack_id}:{tool_id}"
    now = time.time()
    hour_ago = now - 3600

    if key not in _tool_rate_counters:
        _tool_rate_counters[key] = []

    _tool_rate_counters[key] = [t for t in _tool_rate_counters[key] if t > hour_ago]

    if len(_tool_rate_counters[key]) >= limit:
        return True

    _tool_rate_counters[key].append(now)
    return False


# ─── Data Classes ────────────────────────────────────────────

@dataclass
class ToolRequest:
    """Parsed from model output state signal."""
    tool_id: str
    operation: str
    parameters: dict = field(default_factory=dict)
    session_id: str = ""
    requires_confirmation: bool = False


@dataclass
class ToolResult:
    """Returned to the model for conversational response."""
    tool_id: str
    operation: str
    success: bool
    data: dict = field(default_factory=dict)
    display_message: str = ""
    error: Optional[str] = None


# ─── Audit Logging ───────────────────────────────────────────

async def log_tool_audit(
    db,
    request: ToolRequest,
    pack_id: str,
    provider: str,
    status: str,
    scope_valid: bool = True,
    params_valid: bool = True,
    confirmation_required: bool = False,
    confirmation_received: bool = False,
    provider_response: dict = None,
    error_message: str = "",
    duration_ms: int = 0,
    persistent_session_id: str = "",
) -> str | None:
    """Log a tool action to the audit table."""
    if db is None:
        return None

    audit_id = str(uuid.uuid4())
    row = {
        "id": audit_id,
        "session_id": request.session_id,
        "persistent_session_id": persistent_session_id or None,
        "pack_id": pack_id,
        "tool_id": request.tool_id,
        "operation": request.operation,
        "provider": provider,
        "parameters": request.parameters,
        "scope_valid": scope_valid,
        "params_valid": params_valid,
        "confirmation_required": confirmation_required,
        "confirmation_received": confirmation_received,
        "status": status,
        "provider_response": provider_response or {},
        "error_message": error_message,
        "duration_ms": duration_ms,
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "executed_at": datetime.now(timezone.utc).isoformat() if status == "executed" else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        db.table("tool_audit").insert(row).execute()
        return audit_id
    except Exception as e:
        logger.warning(f"Failed to log tool audit: {e}")
        return None


# ─── ToolRegistry ────────────────────────────────────────────

class ToolRegistry:
    """Manages available tools for packs and dispatches validated requests."""

    def __init__(self, supabase_client=None):
        self.db = supabase_client
        self._providers: dict[str, ToolProvider] = {}
        self._pack_tools: dict[str, dict] = {}  # pack_id → {tool_id: tool_decl}

    def register_provider(self, provider_name: str, provider: ToolProvider):
        """Register a tool provider (Calendly, HubSpot, Stripe, etc.)."""
        self._providers[provider_name] = provider
        logger.info(f"Tool provider registered: {provider_name}")

    def load_pack_tools(self, pack_id: str, manifest: dict):
        """Load tool declarations from a pack manifest's 'tools' section."""
        tools_section = manifest.get("tools", {})
        if tools_section:
            self._pack_tools[pack_id] = tools_section
            logger.info(f"Loaded {len(tools_section)} tool(s) for pack {pack_id}")

    def get_available_tools(self, pack_id: str) -> list[dict]:
        """
        Return list of tools available for a pack.
        Used by the assembler to inject tool descriptions into the system prompt.
        """
        tools = self._pack_tools.get(pack_id, {})
        available = []
        for tool_id, tool_decl in tools.items():
            if not tool_decl.get("enabled", True):
                continue
            available.append({
                "tool_id": tool_id,
                "description": tool_decl.get("description", ""),
                "provider": tool_decl.get("provider", "internal"),
                "scopes": tool_decl.get("scopes", []),
                "requires_confirmation": tool_decl.get("requires_confirmation", False),
                "config": tool_decl.get("config", {}),
            })
        return available

    def get_tool_declaration(self, pack_id: str, tool_id: str) -> dict | None:
        """Get a specific tool's manifest declaration."""
        return self._pack_tools.get(pack_id, {}).get(tool_id)

    async def validate_and_execute(
        self,
        request: ToolRequest,
        pack_id: str,
        session_state=None,
    ) -> ToolResult:
        """
        Main execution pipeline:
        1. Check tool_id exists in pack manifest
        2. Check operation is within declared scopes
        3. Validate parameters against tool config constraints
        4. If requires_confirmation and not yet confirmed, return confirmation request
        5. Execute via provider
        6. Log to tool_audit
        7. Return ToolResult
        """
        # 1. Tool exists in manifest?
        tool_decl = self.get_tool_declaration(pack_id, request.tool_id)
        if tool_decl is None:
            error = f"Tool '{request.tool_id}' is not declared in pack '{pack_id}'"
            await log_tool_audit(
                self.db, request, pack_id, "unknown",
                status="rejected", scope_valid=False, error_message=error,
            )
            return ToolResult(
                tool_id=request.tool_id,
                operation=request.operation,
                success=False,
                error=error,
                display_message=f"This tool is not available.",
            )

        # Disabled?
        if not tool_decl.get("enabled", True):
            error = f"Tool '{request.tool_id}' is disabled"
            return ToolResult(
                tool_id=request.tool_id, operation=request.operation,
                success=False, error=error,
                display_message="This tool is currently disabled.",
            )

        provider_name = tool_decl.get("provider", "internal")

        # 2. Scope validation
        scopes = tool_decl.get("scopes", [])
        if scopes and request.operation not in scopes:
            error = f"Operation '{request.operation}' not in scopes {scopes}"
            await log_tool_audit(
                self.db, request, pack_id, provider_name,
                status="rejected", scope_valid=False, error_message=error,
            )
            return ToolResult(
                tool_id=request.tool_id, operation=request.operation,
                success=False, error=error,
                display_message="This operation is not permitted.",
            )

        # 3. Parameter validation
        config = tool_decl.get("config", {})
        param_error = self._validate_parameters(request.tool_id, request.parameters, config)
        if param_error:
            await log_tool_audit(
                self.db, request, pack_id, provider_name,
                status="rejected", params_valid=False, error_message=param_error,
            )
            return ToolResult(
                tool_id=request.tool_id, operation=request.operation,
                success=False, error=param_error,
                display_message=param_error,
            )

        # 4. Rate limit
        if _check_tool_rate_limit(pack_id, request.tool_id):
            error = f"Rate limit exceeded for {request.tool_id}"
            await log_tool_audit(
                self.db, request, pack_id, provider_name,
                status="rate_limited", error_message=error,
            )
            return ToolResult(
                tool_id=request.tool_id, operation=request.operation,
                success=False, error=error,
                display_message="Too many requests. Please try again later.",
            )

        # 5. Confirmation gate
        requires_confirmation = tool_decl.get("requires_confirmation", False)
        if requires_confirmation and not request.requires_confirmation:
            # Not yet confirmed — hold the request
            await log_tool_audit(
                self.db, request, pack_id, provider_name,
                status="requested", confirmation_required=True,
            )
            confirmation_msg = tool_decl.get("confirmation_message", "")
            return ToolResult(
                tool_id=request.tool_id, operation=request.operation,
                success=False,
                error="confirmation_required",
                display_message=confirmation_msg or "Please confirm this action.",
                data={"confirmation_required": True},
            )

        # 6. Execute via provider
        provider = self._providers.get(provider_name)
        if provider is None:
            error = f"Provider '{provider_name}' not registered"
            await log_tool_audit(
                self.db, request, pack_id, provider_name,
                status="failed", error_message=error,
            )
            return ToolResult(
                tool_id=request.tool_id, operation=request.operation,
                success=False, error=error,
                display_message="This integration is not configured.",
            )

        start_ms = time.time() * 1000
        try:
            provider_response = await provider.execute(
                operation=request.operation,
                parameters=request.parameters,
                config=config,
            )
            duration_ms = int(time.time() * 1000 - start_ms)

            success = provider_response.get("success", False)
            message = provider_response.get("message", "")

            await log_tool_audit(
                self.db, request, pack_id, provider_name,
                status="executed" if success else "failed",
                confirmation_required=requires_confirmation,
                confirmation_received=requires_confirmation,
                provider_response=provider_response,
                duration_ms=duration_ms,
            )

            return ToolResult(
                tool_id=request.tool_id,
                operation=request.operation,
                success=success,
                data=provider_response,
                display_message=message,
                error=None if success else message,
            )

        except Exception as e:
            duration_ms = int(time.time() * 1000 - start_ms)
            error_msg = str(e)
            logger.error(f"Tool execution failed: {request.tool_id}.{request.operation}: {error_msg}")
            await log_tool_audit(
                self.db, request, pack_id, provider_name,
                status="failed", error_message=error_msg, duration_ms=duration_ms,
            )
            return ToolResult(
                tool_id=request.tool_id, operation=request.operation,
                success=False, error=error_msg,
                display_message="An error occurred while executing this action.",
            )

    def _validate_parameters(self, tool_id: str, params: dict, config: dict) -> str | None:
        """
        Validate parameters against tool config constraints.
        Returns error string if invalid, None if valid.
        """
        # Check allowed_fields (CRM-style field restriction)
        allowed_fields = config.get("allowed_fields")
        if allowed_fields:
            extra = set(params.keys()) - set(allowed_fields) - {"contact_id"}
            if extra:
                return f"Fields not allowed: {', '.join(sorted(extra))}"

        # Check max_amount_cents (payment ceiling)
        max_amount = config.get("max_amount_cents")
        if max_amount is not None:
            amount = params.get("amount_cents", 0)
            if isinstance(amount, (int, float)) and amount > max_amount:
                return f"Amount {amount} exceeds maximum of {max_amount} cents."

        # Check allowed_products (payment product restriction)
        allowed_products = config.get("allowed_products")
        if allowed_products:
            product = params.get("product_id", "")
            if product and product not in allowed_products:
                return f"Product '{product}' is not allowed."

        return None
