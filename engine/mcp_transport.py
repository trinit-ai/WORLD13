"""
MCP SSE Transport Layer for TMOS13

Implements the Model Context Protocol SSE transport specification,
allowing Claude Desktop and other MCP clients to connect to the
TMOS13 engine via the standard MCP handshake.

Endpoints added:
  GET  /sse              -- open SSE stream, receive session endpoint
  POST /messages/{sid}   -- send JSON-RPC 2.0 messages
  GET  /mcp/manifest     -- MCP server manifest (name, version, tools)

The existing /mcp/call and /mcp/tools endpoints are untouched.
"""

import asyncio
import json
import logging
import os
import uuid
from typing import AsyncIterator

from fastapi import FastAPI, Request, Response, HTTPException
from sse_starlette.sse import EventSourceResponse

from mcp_server import MCPServer, TOOL_DEFINITIONS

logger = logging.getLogger("tmos13.mcp_transport")

# ─── Session Store ────────────────────────────────────────────

# In-memory: session_id -> asyncio.Queue
_sse_sessions: dict[str, asyncio.Queue] = {}

MCP_API_KEY = os.environ.get("MCP_API_KEY", "")


def _check_mcp_auth(request: Request) -> bool:
    """Validate MCP API key from header or query param.

    MCP_API_KEY is required. No dev mode bypass — the kernel requires the key always.
    """
    if not MCP_API_KEY:
        logger.error("MCP_API_KEY not set -- all SSE connections rejected")
        return False

    # Check Authorization header
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        if token == MCP_API_KEY:
            return True

    # Check query param
    api_key = request.query_params.get("api_key", "")
    if api_key == MCP_API_KEY:
        return True

    return False


# ─── SSE Stream Generator ────────────────────────────────────

async def _sse_stream(session_id: str, request: Request) -> AsyncIterator[dict]:
    """Yield SSE events from the session queue."""
    queue = _sse_sessions.get(session_id)
    if not queue:
        return

    try:
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            try:
                message = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send keepalive comment to prevent connection timeout
                yield {"comment": "keepalive"}
                continue

            if message is None:
                # Sentinel for shutdown
                break

            yield {"event": "message", "data": json.dumps(message)}
    finally:
        _sse_sessions.pop(session_id, None)
        logger.info("SSE session closed: %s", session_id[:8])


# ─── JSON-RPC 2.0 Helpers ────────────────────────────────────

def _jsonrpc_response(req_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _jsonrpc_error(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _build_mcp_tools_list() -> list[dict]:
    """Convert TOOL_DEFINITIONS to MCP spec format (inputSchema not input_schema)."""
    tools = []
    for tool in TOOL_DEFINITIONS:
        mcp_tool = {
            "name": tool["name"],
            "description": tool.get("description", ""),
        }
        # MCP spec uses inputSchema, our internal format uses input_schema
        schema = tool.get("input_schema", tool.get("inputSchema", {}))
        mcp_tool["inputSchema"] = schema
        tools.append(mcp_tool)
    return tools


# ─── Endpoint Registration ────────────────────────────────────

def register_mcp_transport(app: FastAPI, mcp_server: MCPServer) -> None:
    """Register SSE transport endpoints alongside existing /mcp/call endpoints."""

    @app.get("/sse")
    async def sse_endpoint(request: Request):
        """Open an SSE stream for MCP communication."""
        if not _check_mcp_auth(request):
            raise HTTPException(401, "Invalid or missing MCP API key")

        session_id = str(uuid.uuid4())
        queue: asyncio.Queue = asyncio.Queue()
        _sse_sessions[session_id] = queue

        logger.info("SSE session opened: %s", session_id[:8])

        # Send the endpoint event first, then stream
        async def event_generator():
            # Initial endpoint event per MCP spec
            yield {
                "event": "endpoint",
                "data": f"/messages/{session_id}",
            }
            # Then stream messages from queue
            async for event in _sse_stream(session_id, request):
                yield event

        return EventSourceResponse(
            event_generator(),
            media_type="text/event-stream",
        )

    @app.post("/messages/{session_id}")
    async def message_endpoint(session_id: str, request: Request):
        """Receive JSON-RPC 2.0 messages from MCP client."""
        queue = _sse_sessions.get(session_id)
        if not queue:
            raise HTTPException(404, f"Session {session_id} not found or expired")

        try:
            body = await request.json()
        except Exception:
            raise HTTPException(400, "Invalid JSON body")

        method = body.get("method", "")
        req_id = body.get("id")
        params = body.get("params", {})

        logger.info("MCP message: method=%s session=%s", method, session_id[:8])

        if method == "initialize":
            # MCP handshake
            response = _jsonrpc_response(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "TMOS13", "version": "1.0"},
            })
            await queue.put(response)

        elif method == "notifications/initialized":
            # Client acknowledgment, no response needed
            pass

        elif method == "tools/list":
            # Return tool definitions in MCP format
            tools = _build_mcp_tools_list()
            response = _jsonrpc_response(req_id, {"tools": tools})
            await queue.put(response)

        elif method == "tools/call":
            # Invoke a tool
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})

            result = await mcp_server.handle_tool_call(tool_name, arguments)

            if "error" in result:
                response = _jsonrpc_response(req_id, {
                    "content": [{"type": "text", "text": str(result["error"])}],
                    "isError": True,
                })
            else:
                # Format result as text content
                result_text = result.get("result", "")
                if isinstance(result_text, dict):
                    result_text = json.dumps(result_text, indent=2, default=str)
                elif not isinstance(result_text, str):
                    result_text = str(result_text)

                response = _jsonrpc_response(req_id, {
                    "content": [{"type": "text", "text": result_text}],
                    "isError": False,
                })
            await queue.put(response)

        elif method == "ping":
            response = _jsonrpc_response(req_id, {})
            await queue.put(response)

        else:
            response = _jsonrpc_error(req_id, -32601, f"Method not found: {method}")
            await queue.put(response)

        # Return 202 Accepted -- actual result goes via SSE stream
        return Response(status_code=202)

    @app.get("/mcp/manifest")
    async def mcp_manifest():
        """MCP server manifest for discovery."""
        return {
            "name": "TMOS13",
            "version": "1.0",
            "description": "TMOS13 AI Protocol Engine -- pack-governed sessions, Vault, GitHub, Notes",
            "tools_count": len(TOOL_DEFINITIONS),
            "protocol": "MCP SSE 2024-11-05",
        }

    logger.info(
        "MCP SSE transport registered: GET /sse, POST /messages/{sid}, GET /mcp/manifest (%d tools)",
        len(TOOL_DEFINITIONS),
    )
