"""
TMOS13 Configuration

All settings loaded from environment variables with safe defaults.
Uses .env file in development (via python-dotenv).
"""
import os
import logging
from pathlib import Path

from dotenv import load_dotenv

# Load .env file (no-op in production where vars are set by Vercel/Docker)
load_dotenv(Path(__file__).parent.parent / ".env")


def _env(primary: str, fallback: str = None, default: str = "") -> str:
    """Read env var with fallback alias support for backward compatibility."""
    val = os.environ.get(primary)
    if val is not None:
        return val
    if fallback:
        val = os.environ.get(fallback)
        if val is not None:
            logger.info(f"Using deprecated env var {fallback}. Migrate to {primary}.")
            return val
    return default


# ─── Environment ─────────────────────────────────────────
# _env() requires logger, so bootstrap with direct reads first
_raw_env = os.environ.get("TMOS13_ENV") or os.environ.get("RABBITHOLE_ENV", "development")
ENV = _raw_env
DEBUG = ENV == "development"
_raw_log_level = os.environ.get("TMOS13_LOG_LEVEL") or os.environ.get("RABBITHOLE_LOG_LEVEL", "DEBUG" if DEBUG else "INFO")
LOG_LEVEL = _raw_log_level

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tmos13")

# ─── API ─────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = _env("TMOS13_MODEL", "RABBITHOLE_MODEL", "claude-sonnet-4-6")
MAX_TOKENS = 4096
PROMPT_CACHE_ENABLED = os.environ.get("PROMPT_CACHE_ENABLED", "true").lower() in ("true", "1", "yes")

# ─── Server ──────────────────────────────────────────────
PORT = int(_env("TMOS13_PORT", "RABBITHOLE_PORT", os.environ.get("PORT", "8000")))
HOST = _env("TMOS13_HOST", "RABBITHOLE_HOST", "0.0.0.0")

# ─── Security ────────────────────────────────────────────
_PRODUCTION_ORIGINS = [
    "https://tmos13.ai",
    "https://www.tmos13.ai",
    "https://tmos13-ai-tmos13.vercel.app",
]
ALLOWED_ORIGINS = list(set(
    [
        o.strip()
        for o in os.environ.get(
            "ALLOWED_ORIGINS",
            "http://localhost:3000,http://localhost:5173"
        ).split(",")
        if o.strip()
    ] + _PRODUCTION_ORIGINS
))
RATE_LIMIT_RPM = int(_env("TMOS13_RATE_LIMIT_RPM", "RATE_LIMIT_RPM", "60"))
MAX_MESSAGE_LENGTH = int(_env("TMOS13_MAX_MESSAGE_LENGTH", "MAX_MESSAGE_LENGTH", "4000"))
MAX_SESSIONS = int(_env("TMOS13_MAX_SESSIONS", "MAX_SESSIONS", "1000"))
SESSION_MAX_AGE_SECONDS = int(_env("SESSION_MAX_AGE_SECONDS", default="0"))  # 0 = disabled (vault handles continuity)
SESSION_IDLE_TIMEOUT_SECONDS = int(_env("SESSION_IDLE_TIMEOUT_SECONDS", default="300"))  # 0 = disabled

# ─── Monitoring Auth ────────────────────────────────────
TMOS13_METRICS_KEY = os.environ.get("TMOS13_METRICS_KEY", "")

# ─── Database (Supabase) ─────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# ─── Stripe ─────────────────────────────────────────────
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PUBLIC_KEY = os.environ.get("STRIPE_PUBLIC_KEY", "")

# ─── Auth ───────────────────────────────────────────────
AUTH_REDIRECT_URL = os.environ.get("AUTH_REDIRECT_URL", "http://localhost:3000/auth/callback")

# ─── Redis ──────────────────────────────────────────────
REDIS_URL = os.environ.get("REDIS_URL", "")

# ─── Sentry ─────────────────────────────────────────────
SENTRY_DSN = os.environ.get("SENTRY_DSN", "")

# ─── PostHog ────────────────────────────────────────────
POSTHOG_API_KEY = os.environ.get("POSTHOG_API_KEY", "")
POSTHOG_HOST = os.environ.get("POSTHOG_HOST", "https://app.posthog.com")

# ─── Resend (Email) ────────────────────────────────────
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "TMOS13 <noreply@tmos13.ai>")
TMOS13_RESEND_API_KEY = RESEND_API_KEY  # canonical alias
RESEND_AUDIENCE_ID = os.environ.get("RESEND_AUDIENCE_ID", "")

# ─── Gmail Sync (IMAP) ────────────────────────────────
GMAIL_EMAIL = os.environ.get("GMAIL_EMAIL", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

# ─── Scheduling Link (appended to outbound emails) ────
TMOS13_SCHEDULING_URL = os.environ.get("TMOS13_SCHEDULING_URL", "")

# ─── Contact Form ────────────────────────────────────
TMOS13_CONTACT_EMAIL = os.environ.get("TMOS13_CONTACT_EMAIL", "hello@tmos13.ai")

# ─── Owner (System Account for Demo Sessions) ────────
TMOS13_OWNER_ID = os.environ.get("TMOS13_OWNER_ID", "a9b2591c-a66d-4ad7-97b2-166a160dbbdd")

# ─── Guest Turn Limit ────────────────────────────────
GUEST_TURN_LIMIT = int(os.environ.get("GUEST_TURN_LIMIT", "30"))
SESSION_LIMIT_MESSAGE = (
    "You've reached the end of this demo session. "
    "Create a free account to continue — no credit card required."
)

# ─── Inbound Email ────────────────────────────────────
TMOS13_RESEND_WEBHOOK_SECRET = _env("TMOS13_RESEND_WEBHOOK_SECRET", "RABBITHOLE_RESEND_WEBHOOK_SECRET", "")
TMOS13_INBOUND_ENABLED = _env("TMOS13_INBOUND_ENABLED", "RABBITHOLE_INBOUND_ENABLED", "false").lower() == "true"
TMOS13_INBOUND_DOMAIN = _env("TMOS13_INBOUND_DOMAIN", "RABBITHOLE_INBOUND_DOMAIN", "tmos13.ai")
TMOS13_INBOUND_REPLY_FROM = _env("TMOS13_INBOUND_REPLY_FROM", "RABBITHOLE_INBOUND_REPLY_FROM", "TMOS13 <noreply@tmos13.ai>")

# ─── Web Search (Brave) ──────────────────────────────────
BRAVE_SEARCH_API_KEY = os.environ.get("BRAVE_SEARCH_API_KEY", "")
WEB_SEARCH_ENABLED = os.environ.get("WEB_SEARCH_ENABLED", "true").lower() == "true"
WEB_SEARCH_MAX_RESULTS = int(os.environ.get("WEB_SEARCH_MAX_RESULTS", "5"))

# ─── Pinecone (Vector RAG) ─────────────────────────────
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
PINECONE_INDEX = os.environ.get("PINECONE_INDEX", "tmos13-rag")
EMBEDDING_API_KEY = os.environ.get("EMBEDDING_API_KEY", "")

# ─── LaunchDarkly (Feature Flags) ──────────────────────
LAUNCHDARKLY_SDK_KEY = os.environ.get("LAUNCHDARKLY_SDK_KEY", "")

# ─── OneSignal (Push Notifications) ────────────────────
ONESIGNAL_API_KEY = os.environ.get("ONESIGNAL_API_KEY", "")
ONESIGNAL_APP_ID = os.environ.get("ONESIGNAL_APP_ID", "")

# ─── OpenTelemetry (Tracing) ──────────────────────────
OTLP_ENDPOINT = os.environ.get("OTLP_ENDPOINT", "")

# ─── RevenueCat (Mobile Billing) ──────────────────────
REVENUECAT_API_KEY = os.environ.get("REVENUECAT_API_KEY", "")
REVENUECAT_WEBHOOK_SECRET = os.environ.get("REVENUECAT_WEBHOOK_SECRET", "")

# ─── LLM Provider ──────────────────────────────────────
# Provider: anthropic | ollama | stub (auto-detected if not set)
TMOS13_LLM_PROVIDER = os.environ.get("TMOS13_LLM_PROVIDER", "")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:4b")

# ─── Audio (STT / TTS) ──────────────────────────────────
TMOS13_STT_PROVIDER = os.environ.get("TMOS13_STT_PROVIDER", "")  # openai | google | azure | stub
TMOS13_TTS_PROVIDER = os.environ.get("TMOS13_TTS_PROVIDER", "")  # openai | elevenlabs | azure | stub
TMOS13_TTS_VOICE = os.environ.get("TMOS13_TTS_VOICE", "alloy")   # default voice ID
TMOS13_TTS_MODEL = os.environ.get("TMOS13_TTS_MODEL", "tts-1")   # openai model variant
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
AZURE_SPEECH_KEY = os.environ.get("AZURE_SPEECH_KEY", "")
AZURE_SPEECH_REGION = os.environ.get("AZURE_SPEECH_REGION", "eastus")
GOOGLE_SPEECH_CREDENTIALS = os.environ.get("GOOGLE_SPEECH_CREDENTIALS", "")

# ─── Abuse Shield ───────────────────────────────────────
ABUSE_SHIELD_ENABLED = os.environ.get("ABUSE_SHIELD_ENABLED", "false").lower() == "true"
TURNSTILE_SECRET_KEY = os.environ.get("TURNSTILE_SECRET_KEY", "")
TURNSTILE_SITE_KEY = os.environ.get("TURNSTILE_SITE_KEY", "")

# ─── Registration Gate ─────────────────────────────────────
REGISTRATION_OPEN = os.environ.get("REGISTRATION_OPEN", "false").lower() in ("true", "1", "yes")

# ─── Self-Consulting System (Fibonacci Plume Node 10) ──────
SELF_CONSULTING_ENABLED = os.environ.get("SELF_CONSULTING_ENABLED", "true").lower() in ("true", "1", "yes")
SELF_CONSULTING_CONFIDENCE_THRESHOLD = float(os.environ.get("SELF_CONSULTING_CONFIDENCE_THRESHOLD", "0.2"))
SELF_CONSULTING_MAX_TOKENS = int(os.environ.get("SELF_CONSULTING_MAX_TOKENS", "1000"))

# ─── Battle Protocol (Fibonacci Plume Node 8) ──────────────
BATTLE_ENABLED = os.environ.get("TMOS13_BATTLE_ENABLED", "true").lower() in ("true", "1", "yes")
BATTLE_MAX_TURNS = int(os.environ.get("TMOS13_BATTLE_MAX_TURNS", "50"))
BATTLE_STALL_THRESHOLD = int(os.environ.get("TMOS13_BATTLE_STALL_THRESHOLD", "3"))
BATTLE_CONTEXT_MAX_TOKENS = int(os.environ.get("TMOS13_BATTLE_CONTEXT_MAX_TOKENS", "800"))

# ─── TimeKeeper (Fibonacci Plume Node 11) ────────────────
TIMEKEEPER_ENABLED = os.environ.get("TMOS13_TIMEKEEPER_ENABLED", "true").lower() in ("true", "1", "yes")
TIMEKEEPER_EVAL_INTERVAL = int(os.environ.get("TMOS13_TIMEKEEPER_EVAL_INTERVAL", "60"))  # seconds
TIMEKEEPER_MAX_SCHEDULE_ENTRIES = int(os.environ.get("TMOS13_TIMEKEEPER_MAX_ENTRIES", "50"))

# ─── Pack Install (Fibonacci Plume Node 12) ───────────────
PACK_INSTALL_ENABLED = os.environ.get("TMOS13_PACK_INSTALL_ENABLED", "true").lower() in ("true", "1", "yes")
PACK_INSTALL_DEFAULT_PACKS = os.environ.get("TMOS13_PACK_INSTALL_DEFAULT_PACKS", "customer_support,lead_qualification").split(",")
PACK_INSTALL_MAX_PER_USER = int(os.environ.get("TMOS13_PACK_INSTALL_MAX_PER_USER", "50"))

# ─── The Loop (Fibonacci Plume Node 13) ──────────────────
LOOP_ENABLED = os.environ.get("TMOS13_LOOP_ENABLED", "true").lower() in ("true", "1", "yes")
LOOP_MAX_AUTO_SESSIONS = int(os.environ.get("TMOS13_LOOP_MAX_AUTO_SESSIONS", "10"))
LOOP_CHAIN_ENABLED = os.environ.get("TMOS13_LOOP_CHAIN_ENABLED", "true").lower() in ("true", "1", "yes")
LOOP_SEND_ENABLED = os.environ.get("TMOS13_LOOP_SEND_ENABLED", "true").lower() in ("true", "1", "yes")

# ─── Daily Briefing ─────────────────────────────────────
TMOS13_BRIEFING_ENABLED = os.environ.get("TMOS13_BRIEFING_ENABLED", "true").lower() in ("true", "1", "yes")

# ─── Compound Memory + Feedback ──────────────────────────
COMPOUND_MEMORY_ENABLED = os.environ.get("TMOS13_COMPOUND_MEMORY_ENABLED", "true").lower() in ("true", "1", "yes")
INSIGHT_MAX_TOKENS = int(os.environ.get("TMOS13_INSIGHT_MAX_TOKENS", "150"))
FEEDBACK_ENABLED = os.environ.get("TMOS13_FEEDBACK_ENABLED", "true").lower() in ("true", "1", "yes")
FEEDBACK_MAX_INJECTIONS = int(os.environ.get("TMOS13_FEEDBACK_MAX_INJECTIONS", "5"))
FEEDBACK_MAX_TOKENS = int(os.environ.get("TMOS13_FEEDBACK_MAX_TOKENS", "800"))

# ─── Semantic Memory ─────────────────────────────────────
VECTOR_SEARCH_ENABLED = os.environ.get("TMOS13_VECTOR_SEARCH_ENABLED", "true").lower() in ("true", "1", "yes")
VECTOR_EMBED_ON_SAVE = os.environ.get("TMOS13_VECTOR_EMBED_ON_SAVE", "true").lower() in ("true", "1", "yes")
MEMORY_CONSOLIDATION_ENABLED = os.environ.get("TMOS13_MEMORY_CONSOLIDATION_ENABLED", "true").lower() in ("true", "1", "yes")
MEMORY_CONSOLIDATION_THRESHOLD = int(os.environ.get("TMOS13_MEMORY_CONSOLIDATION_THRESHOLD", "5"))
MEMORY_CONSOLIDATION_INTERVAL_HOURS = int(os.environ.get("TMOS13_MEMORY_CONSOLIDATION_INTERVAL_HOURS", "6"))
MEMORY_CONSOLIDATION_MAX_TOKENS = int(os.environ.get("TMOS13_MEMORY_CONSOLIDATION_MAX_TOKENS", "1000"))
RELEVANCE_SCORING_ENABLED = os.environ.get("TMOS13_RELEVANCE_SCORING_ENABLED", "true").lower() in ("true", "1", "yes")
RELEVANCE_BOOST_FACTOR = float(os.environ.get("TMOS13_RELEVANCE_BOOST_FACTOR", "0.3"))

# ─── Pack Intelligence ────────────────────────────────────
PACK_STATS_ENABLED = os.environ.get("TMOS13_PACK_STATS_ENABLED", "true").lower() in ("true", "1", "yes")
PACK_STATS_INTERVAL_HOURS = int(os.environ.get("TMOS13_PACK_STATS_INTERVAL_HOURS", "24"))
PACK_STATS_LOOKBACK_DAYS = int(os.environ.get("TMOS13_PACK_STATS_LOOKBACK_DAYS", "90"))

# ─── Manifest (Append-Only Event Log) ────────────────────
TMOS13_MANIFEST_ENABLED = _env("TMOS13_MANIFEST_ENABLED", default="true").lower() in ("true", "1", "yes")

# ─── Normalization Layer ──────────────────────────────────
TMOS13_NORMALIZATION_ENABLED = _env("TMOS13_NORMALIZATION_ENABLED", default="true").lower() in ("true", "1", "yes")
TMOS13_NORMALIZATION_MODEL = _env("TMOS13_NORMALIZATION_MODEL", default="claude-haiku-4-5-20251001")

# ─── Feed Portal ─────────────────────────────────────────
FEED_LLM_FALLBACK = os.environ.get("FEED_LLM_FALLBACK", "true").lower() in ("true", "1", "yes")
FEED_MAX_CHAIN_DEPTH = int(os.environ.get("FEED_MAX_CHAIN_DEPTH", "3"))

# ─── Feed Connector API Keys ────────────────────────────
# Free-tier connectors. Falls back to simulated data if not set.
OPENWEATHER_API_KEY = _env("OPENWEATHER_API_KEY", default="")
NEWS_API_KEY = _env("NEWS_API_KEY", default="")

# GitHub connector
GITHUB_TOKEN = _env("TMOS13_GITHUB_PAT", "GITHUB_TOKEN", "")
GITHUB_REPO = _env("GITHUB_REPO", default="trinit-ai/tmos13.ai")
GITHUB_OWNER = _env("TMOS13_GITHUB_OWNER", default="trinit-ai")
GITHUB_ENABLED = bool(GITHUB_TOKEN)

# ─── Vault / Google Drive ─────────────────────────────────
GOOGLE_DRIVE_CLIENT_ID = _env("GOOGLE_DRIVE_CLIENT_ID", "TMOS13_GOOGLE_DRIVE_CLIENT_ID", "")
GOOGLE_DRIVE_CLIENT_SECRET = _env("GOOGLE_DRIVE_CLIENT_SECRET", "TMOS13_GOOGLE_DRIVE_CLIENT_SECRET", "")
GOOGLE_DRIVE_REDIRECT_URI = _env(
    "GOOGLE_DRIVE_REDIRECT_URI", "TMOS13_GOOGLE_DRIVE_REDIRECT_URI",
    "https://tmos13.ai/api/vault/sync/callback",
)
VAULT_STORAGE_LIMIT_MB = int(_env("VAULT_STORAGE_LIMIT_MB", "TMOS13_VAULT_STORAGE_LIMIT_MB", "500"))

# ─── Paths ───────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
PROTOCOL_DIR = BASE_DIR / "protocol"

# ─── Pack System ─────────────────────────────────────────
TMOS13_PACK = os.environ.get("TMOS13_PACK", "guest")
PACKS_DIR = BASE_DIR.parent / "protocols" / "packs"

# Lazy-initialized pack singleton
_pack = None
_pack_load_failed = False  # prevents infinite retry on broken manifests


def get_pack(pack_id: str = None):
    """
    Get a PackLoader instance.

    With no arguments, returns the default pack singleton (lazy-initialized).
    With a pack_id, returns a cached PackLoader for that pack.

    Falls back to hardcoded defaults if pack loading fails.
    """
    global _pack, _pack_load_failed

    if pack_id and pack_id != TMOS13_PACK:
        return _load_pack(pack_id)

    if _pack is not None:
        return _pack
    if _pack_load_failed:
        return None  # don't retry a known-broken default pack

    try:
        from pack_loader import PackLoader
        _pack = PackLoader(TMOS13_PACK)
    except Exception as e:
        logger.warning(f"Pack loading failed for '{TMOS13_PACK}', using hardcoded fallback: {e}")
        _pack_load_failed = True
    return _pack


# Per-pack cache for multi-pack sessions (shared across app.py)
_pack_cache: dict = {}


def _load_pack(pack_id: str):
    """Load and cache a PackLoader by pack_id."""
    if pack_id in _pack_cache:
        return _pack_cache[pack_id]
    try:
        from pack_loader import PackLoader
        pack = PackLoader(pack_id)
        _pack_cache[pack_id] = pack
        return pack
    except Exception as e:
        logger.warning(f"Pack loading failed for '{pack_id}': {e}")
        return None


def reset_pack():
    """Reset the default pack singleton (for testing or live reload)."""
    global _pack, _pack_load_failed
    _pack = None
    _pack_load_failed = False


def get_pack_ids() -> list[str]:
    """Return a list of available pack IDs by scanning the packs directory."""
    pack_ids = []
    if PACKS_DIR.exists():
        for path in sorted(PACKS_DIR.iterdir()):
            if path.is_dir() and (path / "manifest.json").exists():
                pack_ids.append(path.name)
    return pack_ids


# ─── Cartridge Map ───────────────────────────────────────
# Last-resort fallback when PackLoader fails. guest pack is assembled now,
# so these file refs are stale —
# but the fallback only fires if the manifest can't load at all.
_FALLBACK_CARTRIDGES = {
    "about":      {"name": "About",          "number": 1},
    "product":    {"name": "Product",        "number": 2},
    "pricing":    {"name": "Pricing",        "number": 3},
    "docs":       {"name": "Documentation",  "number": 4},
    "faq":        {"name": "FAQ",            "number": 5},
    "security":   {"name": "Security",       "number": 6},
    "contact":    {"name": "Contact",        "number": 7},
    "onboarding": {"name": "Onboarding",    "number": 8},
    "legal":      {"name": "Legal",          "number": 9},
}


def get_cartridges():
    """Get cartridges from active pack, with fallback."""
    pack = get_pack()
    if pack:
        return pack.cartridges
    return _FALLBACK_CARTRIDGES


# ─── Settings Defaults ───────────────────────────────────
_FALLBACK_DEFAULT_SETTINGS = {
    "tone": "conversational",
    "verbosity": "balanced",
    "formatting": "clean",
}


def get_default_settings():
    """Get default settings from active pack, with fallback."""
    pack = get_pack()
    if pack:
        return pack.settings_defaults
    return _FALLBACK_DEFAULT_SETTINGS


# ─── Startup Validation ─────────────────────────────────
def validate_config():
    """Check required config at startup. Raises on fatal issues in production."""
    errors = []
    if not ANTHROPIC_API_KEY:
        errors.append("ANTHROPIC_API_KEY is not set")
    if not SUPABASE_URL and ENV == "production":
        logger.warning("CONFIG: SUPABASE_URL is not set — falling back to SQLite (not recommended for production)")
    if not SUPABASE_SERVICE_ROLE_KEY and ENV == "production":
        logger.warning("CONFIG: SUPABASE_SERVICE_ROLE_KEY is not set — falling back to local storage (not recommended for production)")
    if not PROTOCOL_DIR.exists():
        errors.append(f"Protocol directory not found: {PROTOCOL_DIR}")
    # Validate pack loads successfully
    try:
        pack = get_pack()
        if pack:
            logger.info(f"Active pack: {pack.name} v{pack.version} ({pack.pack_id})")
    except Exception as e:
        errors.append(f"Pack loading failed: {e}")
    if errors:
        for e in errors:
            logger.error(f"CONFIG: {e}")
        if ENV == "production":
            raise RuntimeError(f"Fatal config errors: {'; '.join(errors)}")
        else:
            logger.warning("Running in development mode with missing config — some features disabled")
