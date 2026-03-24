"""
TMOS13 Invite System — Session Access Codes

CRUD for invite codes used with gated session policies.
Codes are short alphanumeric strings generated server-side.
Each invite tracks usage count, expiry, and optional email
restriction.

Storage: Supabase session_invites + invite_redemptions tables.
In-memory fallback when Supabase is unavailable.
"""

import logging
import secrets
import string
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("tmos13.invites")


def _generate_code(length: int = 8) -> str:
    """Generate a URL-safe invite code."""
    alphabet = string.ascii_uppercase + string.digits
    # Remove ambiguous characters
    alphabet = alphabet.replace("O", "").replace("0", "").replace("I", "").replace("1", "")
    return "".join(secrets.choice(alphabet) for _ in range(length))


@dataclass
class SessionInvite:
    """An invite code for gated session access."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    code: str = field(default_factory=_generate_code)
    pack_id: str = ""
    created_by: str = ""
    email: Optional[str] = None
    max_uses: int = 1
    uses: int = 0
    status: str = "active"  # active | exhausted | expired | revoked
    expires_at: Optional[float] = None  # unix timestamp
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @property
    def is_valid(self) -> bool:
        """Check if the invite can still be redeemed."""
        if self.status != "active":
            return False
        if self.uses >= self.max_uses:
            return False
        if self.expires_at and time.time() > self.expires_at:
            return False
        return True


@dataclass
class InviteRedemption:
    """Record of an invite being redeemed."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    invite_id: str = ""
    redeemed_by: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: float = field(default_factory=time.time)


@dataclass
class RedeemResult:
    """Result of attempting to redeem an invite code."""

    valid: bool = False
    pack_id: Optional[str] = None
    message: Optional[str] = None


class InviteStore:
    """
    In-memory invite store with optional Supabase persistence.

    Thread-safe for single-process operation. For multi-process
    deployments, Supabase becomes the source of truth.
    """

    def __init__(self):
        self._invites: dict[str, SessionInvite] = {}
        self._by_code: dict[str, str] = {}  # code -> invite id
        self._redemptions: list[InviteRedemption] = []

    def create(
        self,
        pack_id: str,
        created_by: str,
        email: Optional[str] = None,
        max_uses: int = 1,
        expires_in_hours: Optional[float] = None,
    ) -> SessionInvite:
        """Create a new invite code."""
        invite = SessionInvite(
            pack_id=pack_id,
            created_by=created_by,
            email=email,
            max_uses=max_uses,
        )

        if expires_in_hours:
            invite.expires_at = time.time() + (expires_in_hours * 3600)

        self._invites[invite.id] = invite
        self._by_code[invite.code] = invite.id

        logger.info(
            "Created invite %s for pack %s (max_uses=%d, email=%s)",
            invite.code,
            pack_id,
            max_uses,
            email or "any",
        )
        return invite

    def get(self, invite_id: str) -> Optional[SessionInvite]:
        """Get invite by ID."""
        return self._invites.get(invite_id)

    def get_by_code(self, code: str) -> Optional[SessionInvite]:
        """Get invite by code string."""
        invite_id = self._by_code.get(code.upper())
        if not invite_id:
            return None
        return self._invites.get(invite_id)

    def list_by_pack(self, pack_id: str) -> list[SessionInvite]:
        """List all invites for a pack."""
        return [
            inv for inv in self._invites.values()
            if inv.pack_id == pack_id
        ]

    def list_by_creator(self, created_by: str) -> list[SessionInvite]:
        """List all invites created by a user."""
        return [
            inv for inv in self._invites.values()
            if inv.created_by == created_by
        ]

    def redeem(
        self,
        code: str,
        session_id: Optional[str] = None,
        redeemed_by: Optional[str] = None,
        ip_address: Optional[str] = None,
        email: Optional[str] = None,
    ) -> RedeemResult:
        """
        Attempt to redeem an invite code.

        Returns RedeemResult indicating success/failure.
        """
        invite = self.get_by_code(code)

        if not invite:
            return RedeemResult(valid=False, message="Invalid invite code.")

        # Check expiry
        if invite.expires_at and time.time() > invite.expires_at:
            invite.status = "expired"
            invite.updated_at = time.time()
            return RedeemResult(valid=False, message="This invite has expired.")

        if not invite.is_valid:
            return RedeemResult(
                valid=False,
                message=f"This invite is no longer valid (status: {invite.status}).",
            )

        # Check email restriction
        if invite.email and email and invite.email.lower() != email.lower():
            return RedeemResult(
                valid=False,
                message="This invite is restricted to a different email address.",
            )

        # Redeem
        invite.uses += 1
        invite.updated_at = time.time()
        if invite.uses >= invite.max_uses:
            invite.status = "exhausted"

        # Record redemption
        redemption = InviteRedemption(
            invite_id=invite.id,
            redeemed_by=redeemed_by,
            session_id=session_id,
            ip_address=ip_address,
        )
        self._redemptions.append(redemption)

        logger.info(
            "Redeemed invite %s (%d/%d uses) for pack %s",
            invite.code,
            invite.uses,
            invite.max_uses,
            invite.pack_id,
        )

        return RedeemResult(
            valid=True,
            pack_id=invite.pack_id,
            message="Invite redeemed successfully.",
        )

    def revoke(self, invite_id: str) -> bool:
        """Revoke an invite by ID."""
        invite = self._invites.get(invite_id)
        if not invite:
            return False
        invite.status = "revoked"
        invite.updated_at = time.time()
        logger.info("Revoked invite %s", invite.code)
        return True

    @property
    def total(self) -> int:
        return len(self._invites)

    @property
    def active_count(self) -> int:
        return sum(1 for inv in self._invites.values() if inv.is_valid)


# Module-level singleton
_store = InviteStore()


def get_invite_store() -> InviteStore:
    """Get the singleton invite store."""
    return _store
