"""
TMOS13 Feature Flags — LaunchDarkly Integration

Gradual rollout, A/B testing, and kill switches.
Falls back to local JSON config when LaunchDarkly is not configured.
"""
import json
import logging
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger("tmos13.flags")


# ─── Default Flags ──────────────────────────────────────

DEFAULT_FLAGS = {
    # Feature gates
    "new_cartridge_enabled": False,
    "advanced_rag": False,
    "multiplayer_beta": False,
    "voice_input": False,

    # Rollout percentages (0-100)
    "hybrid_rag_rollout": 0,
    "vector_search_rollout": 0,

    # Kill switches
    "maintenance_mode": False,
    "disable_signups": False,
    "disable_billing": False,

    # Experiments
    "onboarding_variant": "control",
    "pricing_page_variant": "control",
    "depth_meter_style": "classic",

    # Limits
    "free_tier_daily_messages": 50,
    "pro_tier_daily_messages": 500,
    "max_concurrent_sessions": 3,

    # Abuse Shield
    "abuse_shield_enabled": False,
    "turnstile_enabled": False,
    "behavioral_analysis": False,
    "cost_circuit_breakers": False,
}


class FeatureFlagService:
    """Feature flag management with LaunchDarkly and local fallback."""

    def __init__(self, sdk_key: str = "", local_overrides: dict = None):
        self._ld_client = None
        self._local_flags = {**DEFAULT_FLAGS, **(local_overrides or {})}
        self._overrides_file = Path(__file__).parent / "flags_override.json"

        # Load local overrides file if it exists
        if self._overrides_file.exists():
            try:
                with open(self._overrides_file) as f:
                    file_overrides = json.load(f)
                self._local_flags.update(file_overrides)
                logger.info(f"Loaded {len(file_overrides)} flag overrides from file")
            except Exception as e:
                logger.warning(f"Failed to load flag overrides: {e}")

        if not sdk_key:
            logger.info("LaunchDarkly not configured — using local flags")
            return

        try:
            import ldclient
            from ldclient.config import Config

            config = Config(sdk_key)
            ldclient.set_config(config)
            self._ld_client = ldclient.get()

            if self._ld_client.is_initialized():
                logger.info("LaunchDarkly connected")
            else:
                logger.warning("LaunchDarkly client failed to initialize — using local flags")
                self._ld_client = None
        except ImportError:
            logger.warning("ldclient not installed — using local flags")
        except Exception as e:
            logger.error(f"LaunchDarkly init failed: {e}")

    @property
    def enabled(self) -> bool:
        return self._ld_client is not None

    def _ld_context(self, user_id: str, tier: str = "free", **attrs) -> Any:
        """Build a LaunchDarkly context object."""
        if not self._ld_client:
            return None
        try:
            from ldclient import Context
            builder = Context.builder(user_id)
            builder.set("tier", tier)
            for k, v in attrs.items():
                builder.set(k, v)
            return builder.build()
        except Exception:
            return None

    def get_flag(self, flag_key: str, user_id: str = "anonymous",
                 tier: str = "free", default: Any = None) -> Any:
        """Get a feature flag value."""
        # Check local overrides first
        if flag_key in self._local_flags and not self._ld_client:
            return self._local_flags[flag_key]

        if self._ld_client:
            ctx = self._ld_context(user_id, tier)
            if ctx:
                fallback = self._local_flags.get(flag_key, default)
                return self._ld_client.variation(flag_key, ctx, fallback)

        return self._local_flags.get(flag_key, default)

    def is_enabled(self, flag_key: str, user_id: str = "anonymous",
                   tier: str = "free") -> bool:
        """Check if a boolean feature flag is enabled."""
        return bool(self.get_flag(flag_key, user_id, tier, default=False))

    def get_variant(self, flag_key: str, user_id: str = "anonymous",
                    tier: str = "free") -> str:
        """Get a multivariate flag value as string."""
        return str(self.get_flag(flag_key, user_id, tier, default="control"))

    def get_limit(self, flag_key: str, user_id: str = "anonymous",
                  tier: str = "free") -> int:
        """Get a numeric flag value."""
        return int(self.get_flag(flag_key, user_id, tier, default=0))

    # ─── Message Limits ──────────────────────────────────

    def get_daily_message_limit(self, tier: str = "free") -> int:
        """Get the daily message limit for a tier."""
        key = f"{tier}_tier_daily_messages"
        return self.get_limit(key, tier=tier)

    # ─── Local Override Management ───────────────────────

    def set_local_override(self, flag_key: str, value: Any):
        """Set a local flag override (dev/testing)."""
        self._local_flags[flag_key] = value

    def remove_local_override(self, flag_key: str):
        """Remove a local override, reverting to default."""
        if flag_key in DEFAULT_FLAGS:
            self._local_flags[flag_key] = DEFAULT_FLAGS[flag_key]

    def save_overrides(self):
        """Persist local overrides to file."""
        overrides = {
            k: v for k, v in self._local_flags.items()
            if k not in DEFAULT_FLAGS or v != DEFAULT_FLAGS[k]
        }
        with open(self._overrides_file, "w") as f:
            json.dump(overrides, f, indent=2)

    def get_all_flags(self, user_id: str = "anonymous", tier: str = "free") -> dict:
        """Get all flag values."""
        return {
            key: self.get_flag(key, user_id, tier)
            for key in self._local_flags
        }

    def get_status(self) -> dict:
        return {
            "enabled": self.enabled,
            "backend": "launchdarkly" if self.enabled else "local",
            "total_flags": len(self._local_flags),
        }


# ─── Module State ───────────────────────────────────────



# ─── Endpoint Registration ──────────────────────────────

def register_flag_endpoints(app, flag_service: FeatureFlagService):
    """Register /flags/* endpoints (debug-only)."""

    from config import DEBUG

    if not DEBUG:
        return

    from fastapi import Depends
    from auth import require_auth, UserProfile

    @app.get("/flags")
    async def get_all_flags(user: UserProfile = Depends(require_auth)):
        return flag_service.get_all_flags(user.user_id, user.tier)

    @app.get("/flags/{flag_key}")
    async def get_flag(flag_key: str, user: UserProfile = Depends(require_auth)):
        return {"key": flag_key, "value": flag_service.get_flag(flag_key, user.user_id, user.tier)}

    @app.put("/flags/{flag_key}")
    async def set_flag(flag_key: str, value: Any):
        flag_service.set_local_override(flag_key, value)
        return {"key": flag_key, "value": value, "status": "override_set"}

    logger.info("Feature flag endpoints registered: /flags/* (debug only)")
