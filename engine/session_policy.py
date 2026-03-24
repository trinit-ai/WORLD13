"""
TMOS13 Session Policy — Gated / Timed / Metered / Deferred Auth

Enforces session-level access policies defined in pack manifests.
Five policy types:

  open           — No restrictions. Default for most packs.
  auth_required  — Requires authentication before any interaction.
  gated          — Requires invite code or specific access grant.
  ticketed       — Requires a purchased ticket/credit.
  metered        — Free tier with usage limits (turns/tokens/cost).

Deferred Auth:
  When enabled, anonymous sessions are allowed initially but the
  policy enforcer triggers authentication at configurable thresholds
  (turn count, token usage, cost, or elapsed time).

The enforcer runs as a pre-flight check before process_message.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("tmos13.policy")


@dataclass
class DeferredAuthTrigger:
    """A threshold that triggers deferred authentication."""

    trigger_type: str  # turns | cost | tokens | time_seconds
    threshold: float


@dataclass
class MeteringConfig:
    """Metering limits for free-tier usage."""

    free_turns: int = 10
    free_tokens: int = 50000
    overage_action: str = "prompt_auth"  # prompt_auth | block | meter_warning


@dataclass
class SessionPolicyConfig:
    """Pack-level session policy configuration."""

    policy_type: str = "open"
    deferred_auth_enabled: bool = False
    deferred_auth_triggers: list[DeferredAuthTrigger] = field(default_factory=list)
    deferred_auth_grace_message: Optional[str] = None
    max_anonymous_turns: int = 0
    require_invite: bool = False
    invite_codes_enabled: bool = False
    metering: Optional[MeteringConfig] = None


@dataclass
class PolicyCheckResult:
    """Result of a policy enforcement check."""

    action: str = "allow"  # allow | prompt_auth | require_invite | require_ticket | block | meter_warning
    reason: Optional[str] = None
    remaining_turns: Optional[int] = None
    remaining_tokens: Optional[int] = None
    auth_url: Optional[str] = None


@dataclass
class SessionUsage:
    """Tracks cumulative usage for a session."""

    session_id: str
    turns: int = 0
    tokens: int = 0
    cost_usd: float = 0.0
    started_at: float = field(default_factory=time.time)
    authenticated: bool = False
    invite_redeemed: bool = False
    gated_at: Optional[float] = None


class SessionPolicyEnforcer:
    """
    Enforces session policies. Maintains in-memory usage tracking
    per session, with periodic persistence to Supabase.
    """

    def __init__(self):
        self._usage: dict[str, SessionUsage] = {}
        self._stats = {
            "total_checks": 0,
            "by_action": {
                "allow": 0,
                "prompt_auth": 0,
                "require_invite": 0,
                "require_ticket": 0,
                "block": 0,
                "meter_warning": 0,
            },
        }

    def get_or_create_usage(self, session_id: str) -> SessionUsage:
        """Get or create usage tracking for a session."""
        if session_id not in self._usage:
            self._usage[session_id] = SessionUsage(session_id=session_id)
        return self._usage[session_id]

    def record_turn(
        self,
        session_id: str,
        tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        """Record a turn's usage against the session."""
        usage = self.get_or_create_usage(session_id)
        usage.turns += 1
        usage.tokens += tokens
        usage.cost_usd += cost_usd

    def mark_authenticated(self, session_id: str) -> None:
        """Mark a session as authenticated (deferred auth completed)."""
        usage = self.get_or_create_usage(session_id)
        usage.authenticated = True

    def mark_invite_redeemed(self, session_id: str) -> None:
        """Mark a session as having redeemed an invite."""
        usage = self.get_or_create_usage(session_id)
        usage.invite_redeemed = True

    def check(
        self,
        session_id: str,
        config: SessionPolicyConfig,
        is_authenticated: bool = False,
    ) -> PolicyCheckResult:
        """
        Run the policy check for a session. Called before each
        message is processed.
        """
        self._stats["total_checks"] += 1
        usage = self.get_or_create_usage(session_id)

        # Track external auth state
        if is_authenticated:
            usage.authenticated = True

        # ─── Open Policy ──────────────────────────────────
        if config.policy_type == "open":
            # Even open policies support deferred auth
            if config.deferred_auth_enabled and not usage.authenticated:
                result = self._check_deferred_triggers(usage, config)
                if result:
                    self._record_action(result.action)
                    return result
            self._record_action("allow")
            return PolicyCheckResult(action="allow")

        # ─── Auth Required ────────────────────────────────
        if config.policy_type == "auth_required":
            if not is_authenticated:
                self._record_action("prompt_auth")
                return PolicyCheckResult(
                    action="prompt_auth",
                    reason="Authentication required to use this service.",
                )
            self._record_action("allow")
            return PolicyCheckResult(action="allow")

        # ─── Gated ────────────────────────────────────────
        if config.policy_type == "gated":
            if config.require_invite and not usage.invite_redeemed:
                self._record_action("require_invite")
                return PolicyCheckResult(
                    action="require_invite",
                    reason="An invite code is required to access this session.",
                )
            if not is_authenticated:
                self._record_action("prompt_auth")
                return PolicyCheckResult(
                    action="prompt_auth",
                    reason="Authentication required for gated session.",
                )
            self._record_action("allow")
            return PolicyCheckResult(action="allow")

        # ─── Ticketed ─────────────────────────────────────
        if config.policy_type == "ticketed":
            # Ticket validation would check against billing/credits
            if not is_authenticated:
                self._record_action("prompt_auth")
                return PolicyCheckResult(
                    action="prompt_auth",
                    reason="Authentication required for ticketed session.",
                )
            # TODO: Check ticket/credit balance
            self._record_action("allow")
            return PolicyCheckResult(action="allow")

        # ─── Metered ──────────────────────────────────────
        if config.policy_type == "metered" and config.metering:
            metering = config.metering
            remaining_turns = max(0, metering.free_turns - usage.turns)
            remaining_tokens = max(0, metering.free_tokens - usage.tokens)

            # If authenticated, no metering limits
            if is_authenticated or usage.authenticated:
                self._record_action("allow")
                return PolicyCheckResult(action="allow")

            # Check if free tier exhausted
            if usage.turns >= metering.free_turns or usage.tokens >= metering.free_tokens:
                action = metering.overage_action
                self._record_action(action)
                if usage.gated_at is None:
                    usage.gated_at = time.time()
                return PolicyCheckResult(
                    action=action,
                    reason=f"Free tier limit reached ({metering.free_turns} turns / {metering.free_tokens} tokens).",
                    remaining_turns=0,
                    remaining_tokens=0,
                )

            # Warning at 80% usage
            if usage.turns >= int(metering.free_turns * 0.8):
                self._record_action("allow")
                return PolicyCheckResult(
                    action="allow",
                    reason=f"{remaining_turns} free turns remaining.",
                    remaining_turns=remaining_turns,
                    remaining_tokens=remaining_tokens,
                )

            self._record_action("allow")
            return PolicyCheckResult(
                action="allow",
                remaining_turns=remaining_turns,
                remaining_tokens=remaining_tokens,
            )

        # Fallback: allow
        self._record_action("allow")
        return PolicyCheckResult(action="allow")

    def _check_deferred_triggers(
        self,
        usage: SessionUsage,
        config: SessionPolicyConfig,
    ) -> Optional[PolicyCheckResult]:
        """Check deferred auth triggers against current usage."""
        elapsed = time.time() - usage.started_at

        for trigger in config.deferred_auth_triggers:
            triggered = False

            if trigger.trigger_type == "turns" and usage.turns >= trigger.threshold:
                triggered = True
            elif trigger.trigger_type == "tokens" and usage.tokens >= trigger.threshold:
                triggered = True
            elif trigger.trigger_type == "cost" and usage.cost_usd >= trigger.threshold:
                triggered = True
            elif trigger.trigger_type == "time_seconds" and elapsed >= trigger.threshold:
                triggered = True

            if triggered:
                if usage.gated_at is None:
                    usage.gated_at = time.time()
                return PolicyCheckResult(
                    action="prompt_auth",
                    reason=config.deferred_auth_grace_message
                    or "Please sign in to continue your session.",
                )

        return None

    def _record_action(self, action: str) -> None:
        """Record action in stats."""
        if action in self._stats["by_action"]:
            self._stats["by_action"][action] += 1

    def cleanup_session(self, session_id: str) -> None:
        """Remove usage tracking for a closed session."""
        self._usage.pop(session_id, None)

    @property
    def stats(self) -> dict:
        return dict(self._stats)

    @property
    def active_sessions(self) -> int:
        return len(self._usage)


def get_policy_config_from_manifest(manifest: dict) -> SessionPolicyConfig:
    """Extract session policy config from a pack manifest."""
    policy = manifest.get("session_policy", {})
    deferred = policy.get("deferred_auth", {})
    metering_raw = policy.get("metering")

    triggers = []
    for t in deferred.get("triggers", []):
        triggers.append(DeferredAuthTrigger(
            trigger_type=t.get("type", "turns"),
            threshold=t.get("threshold", 0),
        ))

    metering = None
    if metering_raw:
        metering = MeteringConfig(
            free_turns=metering_raw.get("free_turns", 10),
            free_tokens=metering_raw.get("free_tokens", 50000),
            overage_action=metering_raw.get("overage_action", "prompt_auth"),
        )

    return SessionPolicyConfig(
        policy_type=policy.get("policy_type") or policy.get("type", "open"),
        deferred_auth_enabled=deferred.get("enabled", False),
        deferred_auth_triggers=triggers,
        deferred_auth_grace_message=deferred.get("grace_message"),
        max_anonymous_turns=policy.get("max_anonymous_turns", 0),
        require_invite=policy.get("require_invite", False),
        invite_codes_enabled=policy.get("invite_codes_enabled", False),
        metering=metering,
    )


# Module-level singleton
_enforcer = SessionPolicyEnforcer()


def get_policy_enforcer() -> SessionPolicyEnforcer:
    """Get the singleton policy enforcer instance."""
    return _enforcer
