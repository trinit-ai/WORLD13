# 13TMOS — Enterprise Docker Deployment Guide

## Overview

13TMOS runs as a single Docker container with persistent local storage (SQLite + flat files). No external database required. One container, one volume, one `.env` file.

**Stack**: Python 3.12-slim · FastAPI · Uvicorn · Anthropic Claude API · SQLite vault

**Requirements**: Docker 24+ with Compose V2, an Anthropic API key, ~512MB RAM

---

## Quick Start

```bash
git clone <repo-url> 13tmos && cd 13tmos
./deploy.sh                         # interactive provisioner
curl http://localhost:8000/health    # verify
```

Or manually:

```bash
cp .env.example .env                # fill in your keys
docker compose up -d --build
```

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│  Docker Container: 13tmos-engine                 │
│                                                  │
│  ┌──────────────┐   ┌─────────────────────────┐ │
│  │  Uvicorn      │   │  Protocols              │ │
│  │  (ASGI)       │   │  ├── packs/     (28)    │ │
│  │  ┌──────────┐ │   │  ├── library/   (379)   │ │
│  │  │ FastAPI  │ │   │  ├── shared/            │ │
│  │  │ Engine   │─┼───│  └── private/   (ro)    │ │
│  │  └──────────┘ │   └─────────────────────────┘ │
│  └──────┬───────┘                                │
│         │            ┌─────────────────────────┐ │
│    9 Channel         │  Persistent Volumes      │ │
│    Adapters          │  ├── vault/  (SQLite)    │ │
│    (WA/TG/Email/     │  └── output/ (delivers) │ │
│     SMS/Discord/     └─────────────────────────┘ │
│     Slack/Messenger/                             │
│     Instagram/Web)                               │
│                                                  │
│  :8000 ─── /health /sse /channels/* /vault/*     │
└──────────────────────────────────────────────────┘
```

---

## Dockerfile Breakdown

```dockerfile
FROM python:3.12-slim
WORKDIR /app

# Dependencies first (layer caching)
COPY engine/pyproject.toml engine/pyproject.toml
RUN pip install --no-cache-dir "./engine"

# Source (invalidates cache on code changes only)
COPY engine/ engine/
COPY protocols/ protocols/
COPY config/ config/

# Writable directories for vault + deliverables
RUN mkdir -p vault output && chmod 777 vault output

WORKDIR /app/engine
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

**Layer strategy**: Dependencies are installed before source copy. Code changes don't trigger a full pip reinstall. The image is ~180MB.

---

## docker-compose.yml Breakdown

```yaml
services:
  engine:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: 13tmos-engine
    ports:
      - "${PORT:-8000}:${PORT:-8000}"
    env_file:
      - .env
    volumes:
      - vault_data:/app/vault        # Persistent — sessions, config, channel state
      - output_data:/app/output      # Persistent — generated deliverables
      - ./protocols/private:/app/protocols/private:ro  # Read-only private packs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:${PORT:-8000}/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  vault_data:
    driver: local
  output_data:
    driver: local
```

| Component | Purpose |
|---|---|
| `vault_data` | SQLite databases — `sessions.db` (vault records), `13tmos.db` (channel sessions, config). Survives container rebuilds. |
| `output_data` | Deliverables written by `/close`. Ephemeral by nature but persisted for retrieval. |
| `protocols/private:ro` | Customer-specific or proprietary packs. Mounted read-only. Never baked into the image. |
| `restart: unless-stopped` | Auto-restart on crash. Survives host reboot unless explicitly stopped. |
| `healthcheck` | Hits `/health` every 30s. Docker marks container unhealthy after 3 consecutive failures. |
| `max-size: 10m, max-file: 3` | Log rotation — 30MB max disk for container logs. |

---

## deploy.sh — Interactive Provisioner

```bash
./deploy.sh                      # Full interactive setup
./deploy.sh --name "Acme Corp"   # Pre-fill customer name
./deploy.sh -h                   # Usage help
```

The provisioner walks through:

1. **Customer name** — stamped in `.env` header
2. **Anthropic API key** — required, masked input
3. **MCP API key** — auto-generated random hex if skipped
4. **Model selection** — Sonnet (default), Opus, or Haiku
5. **Default pack** — `guest` by default
6. **Port** — 8000 by default
7. **Channel credentials** — all optional, press Enter to skip each

Output: writes `.env`, runs `docker compose up -d --build`.

If `.env` already exists, prompts before overwriting. Can also just start containers with the existing config.

---

## Configuration Reference

### Required

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key (sk-ant-...) |
| `MCP_API_KEY` | SSE transport auth token (any string — used by MCP clients) |

### Engine

| Variable | Default | Description |
|---|---|---|
| `TMOS13_MODEL` | `claude-sonnet-4-6` | Model for all sessions. Options: `claude-sonnet-4-6`, `claude-opus-4-6`, `claude-haiku-4-5` |
| `TMOS13_PACK` | `guest` | Default pack when no pack is specified |
| `PORT` | `8000` | HTTP listen port |
| `TMOS13_VAULT_DIR` | `./vault` | Vault storage path (inside container: `/app/vault`) |
| `TMOS13_INSTANCE_NAME` | — | Display name for this instance |

### Channels

All channels are opt-in. Unconfigured channels return 503 on their webhook endpoints.

| Channel | Variables | Notes |
|---|---|---|
| **WhatsApp** | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM` | Twilio sandbox or production number |
| **SMS** | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` | Shares Twilio creds with WhatsApp |
| **Telegram** | `TELEGRAM_BOT_TOKEN` | From @BotFather |
| **Email** | `RESEND_API_KEY` | Resend.com for send; inbound via webhook |
| **Discord** | `DISCORD_BOT_TOKEN`, `DISCORD_PUBLIC_KEY` | Bot must be added to server |
| **Slack** | `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET` | Slack app with Events API enabled |
| **Messenger** | `META_PAGE_TOKEN`, `META_VERIFY_TOKEN` | Facebook Page access token |
| **Instagram** | `META_PAGE_TOKEN`, `META_VERIFY_TOKEN` | Shared with Messenger |
| **Web** | `WEB_DEFAULT_PACK` | WebSocket — no external credentials |

Each channel has a `*_DEFAULT_PACK` variable (e.g., `TELEGRAM_DEFAULT_PACK=guest`) that determines which pack handles new conversations on that channel.

---

## API Endpoints

| Path | Method | Auth | Description |
|---|---|---|---|
| `/health` | GET | None | Health check — returns status, model, version |
| `/sse` | GET | `MCP_API_KEY` | MCP Server-Sent Events transport |
| `/drafts` | GET | None | List draft packs in library |
| `/vault/status` | GET | None | Vault diagnostics — DB size, session count |
| `/channels/seed` | POST | None | Pre-load a channel session with context |
| `/channels/sessions` | GET | None | List active channel sessions |
| `/frontier` | GET | None | Pack library coverage map |
| `/channels/{channel}/webhook` | POST | Varies | Channel-specific webhook (Twilio HMAC, Meta verify, etc.) |
| `/channels/web/{token}` | WS | Token | WebSocket channel |

---

## Delivery Models

### Model 1: Dedicated Instance (Recommended)

One container per customer. Full data isolation. Each customer gets their own:
- API keys and model selection
- Protocol packs (deployed + private)
- Vault data (sessions, config, channel state)
- Channel configuration

**Best for**: Enterprise customers, regulated industries, customers with custom packs.

**Provisioning**:
```bash
git clone <repo-url> /opt/13tmos-acme
cd /opt/13tmos-acme
./deploy.sh --name "Acme Corp"
```

**Multi-customer on one host**:
```bash
# Customer A on port 8001
cd /opt/13tmos-acme && PORT=8001 docker compose up -d

# Customer B on port 8002
cd /opt/13tmos-globex && PORT=8002 docker compose up -d
```

Each instance has its own Docker volumes. No shared state.

### Model 2: Self-Hosted License

Customer runs on their own infrastructure. Ship them:

| Deliverable | Description |
|---|---|
| Source archive or Docker image | `docker save 13tmos-engine > 13tmos.tar` |
| `.env.example` | Configuration template |
| `deploy.sh` | Provisioning script |
| `docker-compose.yml` | Orchestration |
| `docs/DEPLOY.md` | This guide |
| `docs/CHANNELS.md` | Per-channel webhook setup |
| Private pack archive (optional) | Customer-specific protocols |

**Pre-built image delivery**:
```bash
# Build and export
docker compose build
docker save 13tmos-engine:latest | gzip > 13tmos-image.tar.gz

# Customer loads
docker load < 13tmos-image.tar.gz
docker compose up -d
```

### Model 3: SaaS Multi-Tenant

Single instance, multiple customers. Requires tenant isolation middleware (not included in base engine). Use Supabase RLS, API gateway tenant routing, or equivalent.

---

## Production Hardening

### TLS Termination

The engine serves plain HTTP. Use a reverse proxy for TLS:

**Caddy** (automatic HTTPS):
```
13tmos.example.com {
    reverse_proxy localhost:8000
}
```

**Nginx**:
```nginx
server {
    listen 443 ssl;
    server_name 13tmos.example.com;
    ssl_certificate /etc/ssl/certs/13tmos.pem;
    ssl_certificate_key /etc/ssl/private/13tmos.key;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support (web channel)
    location /channels/web/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # SSE support (MCP transport)
    location /sse {
        proxy_pass http://localhost:8000;
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
    }
}
```

### Resource Limits

```yaml
# Add to docker-compose.yml under engine service
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 1G
    reservations:
      cpus: '0.5'
      memory: 256M
```

### Network Isolation

```yaml
# Add to docker-compose.yml
networks:
  13tmos:
    driver: bridge

services:
  engine:
    networks:
      - 13tmos
```

### Read-Only Filesystem

For maximum security, run the container with a read-only root filesystem:

```yaml
services:
  engine:
    read_only: true
    tmpfs:
      - /tmp
    volumes:
      - vault_data:/app/vault
      - output_data:/app/output
```

---

## Volumes & Persistence

### What Lives Where

| Volume | Path in Container | Contents | Critical? |
|---|---|---|---|
| `vault_data` | `/app/vault` | `sessions.db` (vault records), `sessions/` (JSON transcripts) | Yes — all session data |
| `output_data` | `/app/output` | Deliverables from `/close` | No — regenerable |
| `protocols/private` (bind) | `/app/protocols/private` | Customer-specific packs | Depends |

### Backup

```bash
# Stop for consistent snapshot
docker compose stop
docker cp 13tmos-engine:/app/vault ./vault-backup-$(date +%Y%m%d)
docker compose start
```

**Automated daily backup** (cron):
```bash
0 2 * * * cd /opt/13tmos && docker cp 13tmos-engine:/app/vault /backups/vault-$(date +\%Y\%m\%d) 2>/dev/null
```

**Volume-level backup** (doesn't require stop):
```bash
docker run --rm \
  -v 13tmos_vault_data:/source:ro \
  -v /backups:/target \
  alpine tar czf /target/vault-$(date +%Y%m%d).tar.gz -C /source .
```

### Restore

```bash
docker compose down
docker volume rm 13tmos_vault_data
docker volume create 13tmos_vault_data
docker run --rm \
  -v 13tmos_vault_data:/target \
  -v /backups:/source:ro \
  alpine tar xzf /source/vault-20260317.tar.gz -C /target
docker compose up -d
```

### Migration Between Hosts

```bash
# Source host
docker run --rm -v 13tmos_vault_data:/data:ro -v $(pwd):/out alpine \
  tar czf /out/vault-export.tar.gz -C /data .

# Transfer
scp vault-export.tar.gz user@newhost:/opt/13tmos/

# Destination host
docker volume create 13tmos_vault_data
docker run --rm -v 13tmos_vault_data:/data -v $(pwd):/in:ro alpine \
  tar xzf /in/vault-export.tar.gz -C /data
```

---

## Platform-Specific Deployment

### Railway

Already configured via `railway.toml`:
```toml
[build]
builder = "dockerfile"
dockerfilePath = "Dockerfile"

[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 300

[[volumes]]
mount = "/app/vault"
```

Push to GitHub — Railway auto-deploys. Vault persists across redeploys via Railway volumes.

### AWS ECS / Fargate

1. Push image to ECR:
```bash
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
docker tag 13tmos-engine:latest <account>.dkr.ecr.<region>.amazonaws.com/13tmos:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/13tmos:latest
```

2. Create task definition with EFS volume for vault persistence
3. Create service with ALB for TLS termination + health check on `/health`
4. Store secrets in AWS Secrets Manager, inject via task definition

### GCP Cloud Run

```bash
gcloud run deploy 13tmos \
  --image gcr.io/PROJECT/13tmos:latest \
  --port 8000 \
  --memory 512Mi \
  --set-env-vars "ANTHROPIC_API_KEY=..." \
  --allow-unauthenticated
```

Note: Cloud Run is stateless. For vault persistence, mount a Cloud Storage FUSE volume or use an external database adapter.

### Azure Container Apps

```bash
az containerapp create \
  --name 13tmos \
  --resource-group mygroup \
  --image 13tmos-engine:latest \
  --target-port 8000 \
  --env-vars "ANTHROPIC_API_KEY=..." \
  --min-replicas 1 --max-replicas 1
```

Mount Azure Files for vault persistence.

### Bare Metal / VPS

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh

# Clone and deploy
git clone <repo-url> /opt/13tmos && cd /opt/13tmos
./deploy.sh --name "Production"

# (Optional) Set up Caddy for automatic TLS
sudo apt install caddy
echo '13tmos.example.com { reverse_proxy localhost:8000 }' | sudo tee /etc/caddy/Caddyfile
sudo systemctl restart caddy
```

---

## Monitoring & Observability

### Health Check

```bash
curl -s http://localhost:8000/health | jq
```

Returns:
```json
{
  "status": "online",
  "service": "13TMOS",
  "model": "claude-sonnet-4-6",
  "version": "0.1.0"
}
```

### Vault Status

```bash
curl -s http://localhost:8000/vault/status | jq
```

Returns DB sizes, session counts, writable status.

### Container Health

```bash
docker inspect --format='{{.State.Health.Status}}' 13tmos-engine
docker compose ps                    # Shows health status
docker stats 13tmos-engine           # CPU, memory, network I/O
```

### Logs

```bash
docker compose logs -f               # Stream all logs
docker compose logs --since 1h       # Last hour
docker compose logs --tail 100       # Last 100 lines
```

Log format: `2026-03-17 14:30:00 [INFO] 13tmos: Engine online`

### Uptime Monitoring

Point any HTTP monitor at `/health`. Expected response: HTTP 200 with `{"status": "online"}`.

---

## Operations Playbook

### Start / Stop / Restart

```bash
docker compose up -d                 # Start (detached)
docker compose down                  # Stop and remove container
docker compose restart               # Restart in place
docker compose up -d --build         # Rebuild and restart
```

### Update to Latest Version

```bash
git pull                             # Pull latest code + protocols
docker compose up -d --build         # Rebuild with new code
```

Vault data survives rebuilds — it lives in Docker volumes, not the container.

### Add a Private Pack

```bash
# Create pack directory
mkdir -p protocols/private/my_custom_pack

# Add pack files (manifest.json, master.md, boot.md, etc.)
# Pack is immediately available — mounted read-only into the container

# If container is running, restart to pick up new packs
docker compose restart
```

### Deploy a Library Pack

```bash
# Copy from library to deployed packs
cp -r protocols/library/legal/legal_intake protocols/packs/legal_intake

# Rebuild to include in image
docker compose up -d --build
```

### Change Model

Edit `.env`:
```
TMOS13_MODEL=claude-opus-4-6
```

Then restart:
```bash
docker compose restart
```

### Shell into Container

```bash
docker compose exec engine bash
# or for the CLI console:
docker compose exec engine python3 console.py
```

### View SQLite Vault Directly

```bash
docker compose exec engine sqlite3 /app/vault/sessions.db ".tables"
docker compose exec engine sqlite3 /app/vault/sessions.db "SELECT COUNT(*) FROM sessions"
```

---

## Protocol Packs

| Directory | Count | Description |
|---|---|---|
| `protocols/packs/` | 28 | Deployed packs — full manifests, runnable, customer-facing |
| `protocols/library/` | 379 | Library packs across 24 categories — authored with manifests |
| `protocols/shared/` | — | Shared protocols loaded into every session (branding, company_profile) |
| `protocols/private/` | — | Customer-specific packs, mounted read-only, never in the image |

**Total visible to engine**: 381 (deduplicated — deployed packs take priority).

### 24 Library Categories

agriculture, architecture, consulting, creative, criminal_justice, diplomatic, education, engineering, finance, government, hospitality, hr, insurance, legal, media, medical, mental_health, personal, real_estate, research, sales, simulations, social_work, sports

---

## Security Considerations

| Layer | Mechanism |
|---|---|
| **API auth** | `MCP_API_KEY` guards the SSE/MCP transport |
| **Channel auth** | Each channel validates its own signatures (Twilio HMAC, Discord Ed25519, Slack HMAC-SHA256, Meta verify token) |
| **Vault isolation** | SQLite on a dedicated volume — no network-accessible database |
| **Private packs** | Mounted read-only, never committed to git, never baked into Docker image |
| **Log rotation** | 30MB cap via Docker json-file driver |
| **Container restart** | `unless-stopped` policy — recovers from crashes, survives reboots |
| **Health monitoring** | Built-in Docker healthcheck with configurable thresholds |

### Secrets Management

- Never commit `.env` to git (it's in `.gitignore`)
- For production, use your platform's secret manager (AWS Secrets Manager, GCP Secret Manager, Railway variables, etc.)
- The `MCP_API_KEY` should be a strong random string — `deploy.sh` generates one automatically

---

## Troubleshooting

| Symptom | Diagnosis | Fix |
|---|---|---|
| Container won't start | `docker compose logs` | Check `ANTHROPIC_API_KEY` in `.env` |
| Health check failing | `docker compose ps` shows "unhealthy" | Verify port mapping, check if port is already in use |
| No packs loading | `/health` works but sessions fail | Ensure `protocols/` was copied — check Dockerfile build output |
| Channel not responding | Webhook returns 503 | Verify channel-specific env vars are set |
| Vault not writable | `/vault/status` shows `writable: false` | Check volume mount permissions: `docker compose exec engine ls -la /app/vault` |
| Out of disk | Container logs growing | Log rotation should handle this — verify `max-size` in compose |
| Slow responses | High latency on all sessions | Check model choice (Haiku fastest), check Anthropic API status |
| Container keeps restarting | OOM or crash loop | Add resource limits, check `docker compose logs` for Python tracebacks |
| SQLite locked | Concurrent write errors | Single-container design prevents this — if seen, check for duplicate containers |
