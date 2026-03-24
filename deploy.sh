#!/bin/bash
# 13TMOS — Customer Instance Provisioner
#
# Usage:
#   ./deploy.sh                    # Interactive setup
#   ./deploy.sh --name "Acme Corp" # Pre-fill customer name
#
# This script provisions a new 13TMOS instance by:
#   1. Generating a .env from .env.example with customer values
#   2. Validating required keys
#   3. Building and launching via docker compose
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

banner() {
    echo -e "${CYAN}"
    echo "  ╔══════════════════════════════════════╗"
    echo "  ║     13TMOS — Instance Provisioner    ║"
    echo "  ╚══════════════════════════════════════╝"
    echo -e "${NC}"
}

info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; }

prompt_value() {
    local label="$1"
    local default="$2"
    local result
    if [ -n "$default" ]; then
        read -rp "  $label [$default]: " result
        echo "${result:-$default}"
    else
        read -rp "  $label: " result
        echo "$result"
    fi
}

prompt_secret() {
    local label="$1"
    local result
    read -rsp "  $label: " result
    echo ""
    echo "$result"
}

# --- Parse args ---
CUSTOMER_NAME=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --name) CUSTOMER_NAME="$2"; shift 2 ;;
        --help|-h)
            echo "Usage: ./deploy.sh [--name \"Customer Name\"]"
            exit 0 ;;
        *) shift ;;
    esac
done

# --- Main ---
banner

# Check prerequisites
command -v docker >/dev/null 2>&1 || { error "Docker not found. Install Docker first."; exit 1; }
docker compose version >/dev/null 2>&1 || { error "Docker Compose not found."; exit 1; }

if [ -f .env ]; then
    warn ".env already exists."
    read -rp "  Overwrite? (y/N): " overwrite
    if [[ ! "$overwrite" =~ ^[Yy]$ ]]; then
        info "Keeping existing .env"
        echo ""
        read -rp "  Start containers? (Y/n): " start
        if [[ ! "$start" =~ ^[Nn]$ ]]; then
            docker compose up -d --build
            info "13TMOS is running on port ${PORT:-8000}"
        fi
        exit 0
    fi
fi

echo -e "\n${CYAN}── Customer Configuration ──${NC}\n"

if [ -z "$CUSTOMER_NAME" ]; then
    CUSTOMER_NAME=$(prompt_value "Customer / org name" "")
fi
info "Provisioning for: $CUSTOMER_NAME"

echo -e "\n${CYAN}── Required Keys ──${NC}\n"

ANTHROPIC_KEY=$(prompt_secret "Anthropic API key")
if [ -z "$ANTHROPIC_KEY" ]; then
    error "Anthropic API key is required."
    exit 1
fi

MCP_KEY=$(prompt_value "MCP API key (for SSE transport)" "$(openssl rand -hex 16 2>/dev/null || echo 'changeme')")

echo -e "\n${CYAN}── Model Selection ──${NC}\n"
echo "  1) claude-sonnet-4-6 (recommended — fast, cost-effective)"
echo "  2) claude-opus-4-6 (maximum capability)"
echo "  3) claude-haiku-4-5 (fastest, lowest cost)"
MODEL_CHOICE=$(prompt_value "Choice" "1")
case "$MODEL_CHOICE" in
    2) MODEL="claude-opus-4-6" ;;
    3) MODEL="claude-haiku-4-5" ;;
    *) MODEL="claude-sonnet-4-6" ;;
esac

echo -e "\n${CYAN}── Default Pack ──${NC}\n"
DEFAULT_PACK=$(prompt_value "Default pack ID" "guest")

echo -e "\n${CYAN}── Port ──${NC}\n"
PORT=$(prompt_value "Host port" "8000")

echo -e "\n${CYAN}── Channels (optional — press Enter to skip) ──${NC}\n"

TWILIO_SID=$(prompt_value "Twilio Account SID" "")
TWILIO_TOKEN=""
TWILIO_WA_FROM=""
if [ -n "$TWILIO_SID" ]; then
    TWILIO_TOKEN=$(prompt_secret "Twilio Auth Token")
    TWILIO_WA_FROM=$(prompt_value "Twilio WhatsApp From" "whatsapp:+14155238886")
fi

TELEGRAM_TOKEN=$(prompt_value "Telegram Bot Token" "")
RESEND_KEY=$(prompt_value "Resend API Key (email)" "")
DISCORD_TOKEN=$(prompt_value "Discord Bot Token" "")
DISCORD_PUBKEY=""
if [ -n "$DISCORD_TOKEN" ]; then
    DISCORD_PUBKEY=$(prompt_value "Discord Public Key" "")
fi

SLACK_TOKEN=$(prompt_value "Slack Bot Token" "")
SLACK_SECRET=""
if [ -n "$SLACK_TOKEN" ]; then
    SLACK_SECRET=$(prompt_secret "Slack Signing Secret")
fi

META_PAGE_TOKEN=$(prompt_value "Meta Page Token (Messenger/Instagram)" "")
META_VERIFY=""
if [ -n "$META_PAGE_TOKEN" ]; then
    META_VERIFY=$(prompt_value "Meta Verify Token" "tmos13duck")
fi

# --- Write .env ---
echo -e "\n${CYAN}── Writing .env ──${NC}\n"

cat > .env << ENVEOF
# 13TMOS Instance — $CUSTOMER_NAME
# Generated $(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Required
ANTHROPIC_API_KEY=$ANTHROPIC_KEY
MCP_API_KEY=$MCP_KEY

# Engine
TMOS13_MODEL=$MODEL
TMOS13_PACK=$DEFAULT_PACK
PORT=$PORT

# Channels — WhatsApp / SMS (Twilio)
TWILIO_ACCOUNT_SID=$TWILIO_SID
TWILIO_AUTH_TOKEN=$TWILIO_TOKEN
TWILIO_WHATSAPP_FROM=$TWILIO_WA_FROM
TMOS13_WHATSAPP_PACK=$DEFAULT_PACK
SMS_DEFAULT_PACK=$DEFAULT_PACK

# Channels — Telegram
TELEGRAM_BOT_TOKEN=$TELEGRAM_TOKEN
TELEGRAM_DEFAULT_PACK=$DEFAULT_PACK

# Channels — Email (Resend)
RESEND_API_KEY=$RESEND_KEY
EMAIL_DEFAULT_PACK=$DEFAULT_PACK

# Channels — Discord
DISCORD_BOT_TOKEN=$DISCORD_TOKEN
DISCORD_PUBLIC_KEY=$DISCORD_PUBKEY
DISCORD_DEFAULT_PACK=$DEFAULT_PACK

# Channels — Slack
SLACK_BOT_TOKEN=$SLACK_TOKEN
SLACK_SIGNING_SECRET=$SLACK_SECRET
SLACK_DEFAULT_PACK=$DEFAULT_PACK

# Channels — Meta (Messenger + Instagram)
META_PAGE_TOKEN=$META_PAGE_TOKEN
META_VERIFY_TOKEN=$META_VERIFY
MESSENGER_DEFAULT_PACK=$DEFAULT_PACK
INSTAGRAM_DEFAULT_PACK=$DEFAULT_PACK

# Channels — Web
WEB_DEFAULT_PACK=$DEFAULT_PACK
ENVEOF

info ".env written"

# --- Build & Launch ---
echo -e "\n${CYAN}── Building & Launching ──${NC}\n"

docker compose up -d --build

echo ""
info "13TMOS instance provisioned for $CUSTOMER_NAME"
info "Engine: http://localhost:$PORT"
info "Health: http://localhost:$PORT/health"
info "MCP:    http://localhost:$PORT/sse"
echo ""
echo -e "${CYAN}Useful commands:${NC}"
echo "  docker compose logs -f        # Watch logs"
echo "  docker compose down            # Stop"
echo "  docker compose up -d           # Restart"
echo "  ./run.sh                       # CLI console"
echo ""
