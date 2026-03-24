"""
13TMOS Engine — Distilled Protocol Kernel

Minimal FastAPI app. No auth middleware beyond MCP_API_KEY.
No Supabase. No billing. Clean kernel.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

# Load .env from project root
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("13tmos")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from mcp_server import MCPServer, register_mcp_endpoints
    from mcp_transport import register_mcp_transport

    mcp = MCPServer()
    register_mcp_endpoints(app, mcp)
    register_mcp_transport(app, mcp)

    # Register channels
    from channel_whatsapp import register_whatsapp_channel
    from channel_telegram import register_telegram_channel
    from channel_email import register_email_channel
    from channel_sms import register_sms_channel
    from channel_discord import register_discord_channel
    from channel_slack import register_slack_channel
    from channel_messenger import register_messenger_channel
    from channel_instagram import register_instagram_channel
    from channel_web import register_web_channel
    from channel_iot import register_iot_channel
    from api_channels import register_channel_api
    register_whatsapp_channel(app)
    register_telegram_channel(app)
    register_email_channel(app)
    register_sms_channel(app)
    register_discord_channel(app)
    register_slack_channel(app)
    register_messenger_channel(app)
    register_instagram_channel(app)
    register_web_channel(app)
    register_iot_channel(app)
    register_channel_api(app)

    vault_path = os.path.abspath(os.getenv("TMOS13_VAULT_DIR", str(ROOT_DIR / "vault")))

    logger.info("13TMOS engine online")
    logger.info("  Packs: %d active (deployed + library) | %d stubs", mcp.active_pack_count, mcp.stub_count)
    logger.info("  Model: %s", os.getenv("TMOS13_MODEL", "claude-sonnet-4-6"))
    logger.info("  MCP SSE transport: /sse")
    logger.info("  Channels: whatsapp, telegram, email, sms, discord, slack, messenger, instagram, web, iot")
    logger.info("  Channel API: /channels/seed | /channels/sessions")
    logger.info("  Vault: %s (writable: %s)", vault_path, os.access(vault_path, os.W_OK))
    logger.info("  Tools: %d", mcp.tool_count)

    yield


app = FastAPI(title="13TMOS Engine", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {
        "status": "online",
        "service": "13TMOS",
        "model": os.getenv("TMOS13_MODEL", "claude-sonnet-4-6"),
        "version": "0.1.0",
    }


@app.get("/drafts")
async def list_draft_packs():
    """List all draft packs with metadata."""
    import yaml

    library_dir = ROOT_DIR / "protocols" / "library"
    drafts = []
    for cat_dir in sorted(library_dir.iterdir()):
        if not cat_dir.is_dir():
            continue
        for pack_dir in sorted(cat_dir.iterdir()):
            if not pack_dir.is_dir():
                continue
            h = pack_dir / "header.yaml"
            if h.exists():
                data = yaml.safe_load(h.read_text())
                if data and data.get("status") == "draft":
                    drafts.append({
                        "pack_id": data.get("pack_id"),
                        "name": data.get("name"),
                        "category": data.get("category"),
                        "description": data.get("description"),
                        "estimated_turns": data.get("estimated_turns"),
                        "requires_review": data.get("requires_review", False),
                        "draft_date": data.get("draft_date"),
                    })
    return {"drafts": drafts, "total": len(drafts)}


@app.get("/vault/status")
async def vault_status():
    import sqlite3

    vault_dir = os.getenv("TMOS13_VAULT_DIR", str(ROOT_DIR / "vault"))
    db_path = os.path.join(vault_dir, "sessions.db")
    config_db = str(ROOT_DIR / "config" / "13tmos.db")

    db_exists = os.path.exists(db_path)
    db_size = os.path.getsize(db_path) if db_exists else 0

    session_count = 0
    if db_exists:
        try:
            conn = sqlite3.connect(db_path)
            row = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
            session_count = row[0] if row else 0
            conn.close()
        except Exception:
            pass

    # Channel sessions live in config/13tmos.db
    channel_session_count = 0
    config_db_exists = os.path.exists(config_db)
    config_db_size = os.path.getsize(config_db) if config_db_exists else 0
    if config_db_exists:
        try:
            conn = sqlite3.connect(config_db)
            row = conn.execute("SELECT COUNT(*) FROM channel_sessions").fetchone()
            channel_session_count = row[0] if row else 0
            conn.close()
        except Exception:
            pass

    return {
        "vault_dir": vault_dir,
        "vault_writable": os.access(vault_dir, os.W_OK),
        "vault_db": db_path,
        "vault_db_exists": db_exists,
        "vault_db_size_bytes": db_size,
        "vault_sessions": session_count,
        "config_db": config_db,
        "config_db_exists": config_db_exists,
        "config_db_size_bytes": config_db_size,
        "channel_sessions": channel_session_count,
    }
