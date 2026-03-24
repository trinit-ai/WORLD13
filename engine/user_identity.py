"""
TMOS13 User Identity — Fibonacci Plume Node 6

Persistent identity model shaped by all user interactions. Aggregates
across sessions, packs, and deliverables to build a first-class profile
that modifies pack behavior before the first exchange.

The transition from memory to identity: the pack knows who it's talking to.
Intake fields pre-populate. The Face recognizes the person.

Prerequisite for the Ambassador "Deploy Yourself" promise — the Ambassador
needs to know who it's representing, not just what protocol to follow.

Sources (priority order):
  1. Profile table (authoritative — user explicitly set these)
  2. Session journals (behavioral inference)
  3. Persistent sessions (captured fields across packs)
  4. Deliverable history (what they've produced)

Follows vault_rag.py / ai_guardrails.py pattern: env config, service class,
singleton init/get.
"""
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("tmos13.user_identity")

# ─── Configuration ─────────────────────────────────────────

USER_IDENTITY_ENABLED = os.environ.get(
    "TMOS13_USER_IDENTITY_ENABLED", "true"
).lower() in ("true", "1", "yes")

# How old the cached identity can be before a rebuild is triggered (hours)
USER_IDENTITY_CACHE_TTL_HOURS = int(os.environ.get(
    "TMOS13_USER_IDENTITY_CACHE_TTL_HOURS", "24"
))

# Max persistent sessions to scan for known_fields
USER_IDENTITY_MAX_SESSIONS = int(os.environ.get(
    "TMOS13_USER_IDENTITY_MAX_SESSIONS", "50"
))

# Max token budget for identity injection block
USER_IDENTITY_MAX_TOKENS = int(os.environ.get(
    "TMOS13_USER_IDENTITY_MAX_TOKENS", "800"
))


# ─── Identity Model ───────────────────────────────────────

@dataclass
class UserIdentity:
    """Persistent identity model shaped by all user interactions."""
    user_id: str = ""

    # Core identity (from profile + inferred)
    preferred_name: Optional[str] = None
    organization: Optional[str] = None
    role: Optional[str] = None
    industry: Optional[str] = None

    # Behavioral model (inferred from session journals)
    communication_style: Optional[str] = None   # direct | detailed | casual | formal
    expertise_level: Optional[str] = None        # technical | executive | generalist
    decision_pattern: Optional[str] = None       # fast | deliberate | consensus-driven

    # Interaction history (aggregated)
    packs_used: list[str] = field(default_factory=list)
    total_sessions: int = 0
    total_deliverables: int = 0
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None

    # Captured knowledge (accumulated fields across all packs)
    known_fields: dict = field(default_factory=dict)
    # e.g. {"company_name": "Conduit Labs", "budget_range": "$100-200K"}

    # Pack-specific preferences
    pack_preferences: dict = field(default_factory=dict)
    # e.g. {"legal_intake": {"preferred_case_type": "PI"}}

    # Identity confidence
    confidence: float = 0.0   # 0.0 = no data, 1.0 = rich profile
    last_updated: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


# ─── Identity Service ────────────────────────────────────

class UserIdentityService:
    """Builds and maintains persistent user identity models."""

    def __init__(self, db=None, journal_service=None):
        self._db = db
        self._journal_service = journal_service
        logger.info("User identity service initialized")

    @property
    def enabled(self) -> bool:
        return USER_IDENTITY_ENABLED and self._db is not None

    async def get_identity(self, user_id: str) -> Optional[UserIdentity]:
        """
        Load or build user identity. Primary entry point.

        Returns None for anonymous users or when disabled.
        """
        if not self.enabled:
            return None
        if not user_id or user_id == "anonymous":
            return None

        # Fast path: load from identity cache table
        cached = await self._load_cached(user_id)
        if cached and not self._is_stale(cached):
            return cached

        # Rebuild from all sources
        return await self.rebuild_identity(user_id)

    async def rebuild_identity(self, user_id: str) -> UserIdentity:
        """Rebuild identity from all available sources."""
        identity = UserIdentity(user_id=user_id)

        # Source 1: Profile table (authoritative — user-provided)
        await self._merge_profile(identity)

        # Source 2: Session journals (behavioral inference)
        await self._merge_journals(identity)

        # Source 3: Persistent sessions (captured fields across packs)
        await self._merge_persistent_sessions(identity)

        # Source 4: Deliverable history
        await self._merge_deliverables(identity)

        # Compute confidence score
        identity.confidence = compute_confidence(identity)
        identity.last_updated = datetime.now(timezone.utc).isoformat()

        # Cache the rebuilt identity
        await self._cache_identity(identity)

        logger.info(
            "Identity rebuilt: user=%s confidence=%.0f%% sessions=%d fields=%d",
            user_id, identity.confidence * 100,
            identity.total_sessions, len(identity.known_fields),
        )
        return identity

    async def update_from_session(self, user_id: str, session_state: dict):
        """
        Incremental update after a session completes.

        Instead of full rebuild, merges new session data into cached identity.
        Full rebuild happens on next get_identity() if TTL expired.
        """
        if not self.enabled:
            return
        if not user_id or user_id == "anonymous":
            return

        try:
            cached = await self._load_cached(user_id)
            if not cached:
                # No cached identity — schedule a full rebuild next time
                return

            # Merge new captured fields
            forms = session_state.get("forms", {})
            for form_data in forms.values():
                if isinstance(form_data, dict):
                    for k, v in form_data.items():
                        if k != "submitted_at" and v is not None:
                            cached.known_fields[k] = v

            # Update counters
            cached.total_sessions += 1
            pack_id = session_state.get("pack_id", "")
            if pack_id and pack_id not in cached.packs_used:
                cached.packs_used.append(pack_id)
            cached.last_seen = datetime.now(timezone.utc).isoformat()

            # Recompute confidence
            cached.confidence = compute_confidence(cached)
            cached.last_updated = datetime.now(timezone.utc).isoformat()

            await self._cache_identity(cached)
        except Exception as e:
            logger.warning("Identity incremental update failed: %s", e)

    # ─── Source Mergers ───────────────────────────────────

    async def _merge_profile(self, identity: UserIdentity):
        """Merge explicit profile data (highest priority — user-provided)."""
        if not self._db:
            return
        try:
            result = (
                self._db.table("profiles")
                .select(
                    "preferred_name, display_name, org_name, title, bio, "
                    "industry, use_case, communication_style"
                )
                .eq("user_id", identity.user_id)
                .maybe_single()
                .execute()
            )
            if not result.data:
                return
            row = result.data
            identity.preferred_name = row.get("preferred_name") or row.get("display_name")
            identity.organization = row.get("org_name")
            identity.role = row.get("title")
            identity.industry = row.get("industry")
            style = row.get("communication_style")
            if style and style != "balanced":
                identity.communication_style = style
        except Exception as e:
            logger.warning("Identity profile merge failed: %s", e)

    async def _merge_journals(self, identity: UserIdentity):
        """Infer behavioral model from session journal history."""
        if not self._db:
            return
        try:
            from session_journal import aggregate_user_model
            result = (
                self._db.table("session_journals")
                .select("*")
                .eq("user_id", identity.user_id)
                .order("session_ended_at", desc=True)
                .limit(USER_IDENTITY_MAX_SESSIONS)
                .execute()
            )
            journals = result.data if result and result.data else []
            if not journals:
                return

            model = aggregate_user_model(journals)
            identity.total_sessions = model.get("total_sessions", 0)
            identity.packs_used = list(model.get("packs_used", {}).keys())
            identity.first_seen = model.get("first_session_date")
            identity.last_seen = model.get("last_session_date")

            # Infer expertise and decision pattern from journal data
            identity.expertise_level = _infer_expertise(journals)
            identity.decision_pattern = _infer_decision_pattern(journals)
        except Exception as e:
            logger.warning("Identity journal merge failed: %s", e)

    async def _merge_persistent_sessions(self, identity: UserIdentity):
        """Accumulate captured fields from all persistent sessions."""
        if not self._db:
            return
        try:
            result = (
                self._db.table("persistent_sessions")
                .select("pack_id, captured_fields")
                .eq("user_id", identity.user_id)
                .eq("status", "active")
                .order("last_seen_at", desc=True)
                .limit(USER_IDENTITY_MAX_SESSIONS)
                .execute()
            )
            rows = result.data if result and result.data else []
            for row in rows:
                pack_id = row.get("pack_id", "")
                captured = row.get("captured_fields", {})
                if not isinstance(captured, dict):
                    continue

                # Accumulate into known_fields (later values don't overwrite)
                for k, v in captured.items():
                    if k not in identity.known_fields and v is not None:
                        identity.known_fields[k] = v

                # Track pack-specific preferences
                if pack_id and captured:
                    if pack_id not in identity.pack_preferences:
                        identity.pack_preferences[pack_id] = {}
                    identity.pack_preferences[pack_id].update(
                        {k: v for k, v in captured.items() if v is not None}
                    )
        except Exception as e:
            logger.warning("Identity persistent sessions merge failed: %s", e)

    async def _merge_deliverables(self, identity: UserIdentity):
        """Count and categorize deliverable history."""
        if not self._db:
            return
        try:
            result = (
                self._db.table("deliverables")
                .select("id", count="exact")
                .eq("user_id", identity.user_id)
                .execute()
            )
            identity.total_deliverables = result.count if result.count else 0
        except Exception as e:
            logger.warning("Identity deliverables merge failed: %s", e)

    # ─── Cache Operations ─────────────────────────────────

    async def _load_cached(self, user_id: str) -> Optional[UserIdentity]:
        """Load cached identity from the user_identities table."""
        if not self._db:
            return None
        try:
            result = (
                self._db.table("user_identities")
                .select("*")
                .eq("user_id", user_id)
                .maybe_single()
                .execute()
            )
            if not result.data:
                return None
            return _row_to_identity(result.data)
        except Exception as e:
            logger.warning("Identity cache load failed: %s", e)
            return None

    async def _cache_identity(self, identity: UserIdentity):
        """Upsert identity into the user_identities cache table."""
        if not self._db:
            return
        try:
            now = datetime.now(timezone.utc).isoformat()
            row = {
                "user_id": identity.user_id,
                "preferred_name": identity.preferred_name,
                "organization": identity.organization,
                "role": identity.role,
                "industry": identity.industry,
                "communication_style": identity.communication_style,
                "expertise_level": identity.expertise_level,
                "decision_pattern": identity.decision_pattern,
                "packs_used": identity.packs_used,
                "total_sessions": identity.total_sessions,
                "total_deliverables": identity.total_deliverables,
                "first_seen": identity.first_seen,
                "last_seen": identity.last_seen,
                "known_fields": identity.known_fields,
                "pack_preferences": identity.pack_preferences,
                "confidence": identity.confidence,
                "last_rebuilt_at": now,
                "updated_at": now,
            }
            self._db.table("user_identities").upsert(
                row, on_conflict="uq_user_identity"
            ).execute()
        except Exception as e:
            logger.warning("Identity cache save failed: %s", e)

    def _is_stale(self, identity: UserIdentity) -> bool:
        """Check if cached identity has exceeded the TTL."""
        if not identity.last_updated:
            return True
        try:
            updated = datetime.fromisoformat(
                identity.last_updated.replace("Z", "+00:00")
            )
            age_hours = (
                datetime.now(timezone.utc) - updated
            ).total_seconds() / 3600
            return age_hours > USER_IDENTITY_CACHE_TTL_HOURS
        except (ValueError, TypeError):
            return True


# ─── Behavioral Inference (simple heuristics) ─────────────

def _infer_expertise(journals: list[dict]) -> Optional[str]:
    """
    Infer expertise level from session journal patterns.

    Heuristic: high depth + many cartridges = technical,
    low depth + quick sessions = executive.
    """
    if not journals:
        return None
    total_depth = sum(j.get("depth", 0) for j in journals)
    total_turns = sum(j.get("turn_count", 0) for j in journals)
    avg_depth = total_depth / len(journals) if journals else 0
    avg_turns = total_turns / len(journals) if journals else 0

    if avg_depth >= 3 and avg_turns >= 15:
        return "technical"
    if avg_depth <= 1 and avg_turns <= 8:
        return "executive"
    return "generalist"


def _infer_decision_pattern(journals: list[dict]) -> Optional[str]:
    """
    Infer decision pattern from session journal patterns.

    Heuristic: few turns to outcome = fast, many turns = deliberate.
    """
    if not journals:
        return None
    sessions_with_outcome = [
        j for j in journals if j.get("session_outcome")
    ]
    if not sessions_with_outcome:
        return None
    avg_turns = sum(j.get("turn_count", 0) for j in sessions_with_outcome) / len(sessions_with_outcome)
    if avg_turns <= 6:
        return "fast"
    if avg_turns >= 20:
        return "deliberate"
    return None


# ─── Confidence Scoring ───────────────────────────────────

def compute_confidence(identity: UserIdentity) -> float:
    """Score how complete the identity model is. 0.0 to 1.0."""
    score = 0.0
    if identity.preferred_name:
        score += 0.15
    if identity.organization:
        score += 0.15
    if identity.role:
        score += 0.1
    if identity.communication_style:
        score += 0.1
    if identity.expertise_level:
        score += 0.1
    if identity.total_sessions > 5:
        score += 0.1
    if identity.total_deliverables > 3:
        score += 0.1
    if len(identity.known_fields) > 5:
        score += 0.1
    if identity.industry:
        score += 0.1
    return min(score, 1.0)


# ─── Assembler Formatting ────────────────────────────────

def format_identity_block(
    identity: UserIdentity,
    pack_id: Optional[str] = None,
    max_tokens: int = USER_IDENTITY_MAX_TOKENS,
) -> str:
    """
    Format identity as a [USER IDENTITY] injection block for the assembler.

    Returns "" if identity is None or confidence < 0.1.
    """
    if not identity or identity.confidence < 0.1:
        return ""

    char_budget = max_tokens * 4
    lines = ["[USER IDENTITY]"]

    if identity.preferred_name:
        lines.append(f"Name: {identity.preferred_name}")
    if identity.organization:
        lines.append(f"Organization: {identity.organization}")
    if identity.role:
        lines.append(f"Role: {identity.role}")
    if identity.industry:
        lines.append(f"Industry: {identity.industry}")
    if identity.communication_style:
        lines.append(f"Communication style: {identity.communication_style}")
    if identity.expertise_level:
        lines.append(f"Expertise: {identity.expertise_level}")
    if identity.decision_pattern:
        lines.append(f"Decision pattern: {identity.decision_pattern}")

    # Interaction summary
    if identity.total_sessions > 0:
        lines.append(
            f"History: {identity.total_sessions} sessions, "
            f"{identity.total_deliverables} deliverables, "
            f"{len(identity.packs_used)} packs"
        )

    # Known fields — pre-populate so the pack doesn't re-ask
    if identity.known_fields:
        used = sum(len(line) for line in lines)
        field_lines = ["", "Known information (do not re-ask unless verifying):"]
        for key, value in identity.known_fields.items():
            entry = f"  {key}: {value}"
            if used + len(entry) + 200 > char_budget:
                break
            field_lines.append(entry)
            used += len(entry)
        lines.extend(field_lines)

    # Pack-specific preferences
    if pack_id and pack_id in identity.pack_preferences:
        prefs = identity.pack_preferences[pack_id]
        if prefs:
            lines.append("")
            lines.append("Preferences for this pack:")
            for key, value in prefs.items():
                lines.append(f"  {key}: {value}")

    lines.append(f"Identity confidence: {identity.confidence:.0%}")
    lines.append(
        "\nINSTRUCTION: Use this identity to personalize. Address the user by name "
        "when natural. Do NOT re-collect known fields unless the user indicates "
        "information has changed. Adapt communication style to their preference."
    )
    lines.append("[/USER IDENTITY]")

    return "\n".join(lines)


# ─── Row Conversion ───────────────────────────────────────

def _row_to_identity(row: dict) -> UserIdentity:
    """Convert a Supabase row to a UserIdentity."""
    return UserIdentity(
        user_id=row.get("user_id", ""),
        preferred_name=row.get("preferred_name"),
        organization=row.get("organization"),
        role=row.get("role"),
        industry=row.get("industry"),
        communication_style=row.get("communication_style"),
        expertise_level=row.get("expertise_level"),
        decision_pattern=row.get("decision_pattern"),
        packs_used=row.get("packs_used") or [],
        total_sessions=row.get("total_sessions", 0),
        total_deliverables=row.get("total_deliverables", 0),
        first_seen=row.get("first_seen"),
        last_seen=row.get("last_seen"),
        known_fields=row.get("known_fields") or {},
        pack_preferences=row.get("pack_preferences") or {},
        confidence=row.get("confidence", 0.0),
        last_updated=row.get("updated_at"),
    )


# ─── Singleton ────────────────────────────────────────────

_identity_service: Optional[UserIdentityService] = None


def init_identity_service(db=None, journal_service=None) -> UserIdentityService:
    """Initialize the global identity service. Called during app lifespan."""
    global _identity_service
    _identity_service = UserIdentityService(db=db, journal_service=journal_service)
    return _identity_service


def get_identity_service() -> Optional[UserIdentityService]:
    """Get the global identity service instance. Returns None if not initialized."""
    return _identity_service
