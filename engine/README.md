# TMOS13 Engine — Python Backend

FastAPI server with REST and WebSocket endpoints. Handles command routing,
prompt assembly, session state management, response parsing, and all
infrastructure integrations.

## Quick Start

```bash
pip install -e ".[dev]"
export ANTHROPIC_API_KEY=your-key-here
uvicorn app:app --host 0.0.0.0 --port 8000
```

Server: `http://localhost:8000`
WebSocket: `ws://localhost:8000/ws`
Health: `GET /health`

## Module Overview

| Module | Purpose |
|--------|---------|
| `app.py` | Server entry point, REST + WebSocket endpoints |
| `router.py` | Deterministic command routing (priority-ordered) |
| `assembler.py` | Dynamic prompt assembly (~80% token reduction) |
| `state.py` | Session state manager (in-memory + persistence) |
| `parser.py` | LLM response parsing + state signal extraction |
| `pack_loader.py` | Manifest-driven pack loading + validation |
| `config.py` | Environment configuration + pack accessors |
| `auth.py` | OAuth authentication (Apple, Google, GitHub) + RBAC |
| `billing.py` | Stripe billing integration |
| `db.py` | Persistence (Supabase / SQLite) |
| `cache.py` | Redis / in-memory caching |
| `rag.py` | Retrieval-augmented generation pipeline |
| `llm_provider.py` | LLM abstraction (Anthropic, Ollama, Stub) |
| `mcp_server.py` | Model Context Protocol server (20 tools) |
| `mcp_connectors.py` | 12 service connectors (4 always-enabled + 8 stubs) |
| `audio.py` | STT/TTS (OpenAI, Google, Azure, ElevenLabs) |
| `files.py` | File upload, chunking, validation |
| `notes.py` | Knowledge base with TF-IDF search + auto-linking |
| `transcripts.py` | Session recording + contact extraction |
| `alerts.py` | Alert classification (6 trigger types) + dispatch |
| `deliverables.py` | Transcript-to-document generation pipeline |
| `ambassador_service.py` | Autonomous email processing + thread management |
| `architect.py` | Classification + artifact orchestration |
| `feed_router.py` | Feed portal intent routing to connectors |
| `card_formatter.py` | Connector result → typed FeedCard mapping |
| `email_exchange.py` | Email thread state + reply chain management |
| `monitoring.py` | Prometheus metrics + monitoring dashboard |
| `security_headers.py` | Security middleware + X-Request-ID |
| `privacy.py` | GDPR/CCPA consent, data export, deletion |

77 modules total. See [docs/architecture.md](../docs/architecture.md) for details.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Required for LLM inference |
| `TMOS13_MODEL` | `claude-sonnet-4-6` | LLM model identifier |
| `TMOS13_PORT` | `8000` | Server port |
| `TMOS13_ENV` | `development` | Environment mode |
| `TMOS13_PACK` | `tmos13_site` | Active pack identifier |

See `../.env.example` for the complete list.

## Tests

```bash
# From repo root
python -m pytest tests/ -v
```
