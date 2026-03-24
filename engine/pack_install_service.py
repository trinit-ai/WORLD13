"""
TMOS13 Pack Install Service (Fibonacci Plume Node 12)

Manages the lifecycle of pack installations — which published registry packs
a user has installed, paused, or uninstalled. Distinct from user_packs
(user-CREATED packs).

Singleton pattern following pipeline_service.py / pack_registry.py.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

import config as cfg

logger = logging.getLogger("tmos13.pack_install")


class PackInstallService:
    """Manages pack install lifecycle for authenticated users."""

    def __init__(self, db=None):
        self._db = db

    @property
    def enabled(self) -> bool:
        return cfg.PACK_INSTALL_ENABLED and self._db is not None

    # ─── Install ────────────────────────────────────────────

    def install(
        self,
        user_id: str,
        pack_id: str,
        source: str = "manual",
        stripe_session_id: str | None = None,
    ) -> dict:
        """
        Install a pack for a user. Upsert semantics:
        - New row → insert with status=active
        - Existing uninstalled → update to active
        - Already active/paused → no-op, return existing
        """
        if not self.enabled:
            return {"pack_id": pack_id, "status": "active", "source": source}

        # Check max installs
        current_count = self._count_active_installs(user_id)
        if current_count >= cfg.PACK_INSTALL_MAX_PER_USER:
            raise ValueError(
                f"Maximum installs ({cfg.PACK_INSTALL_MAX_PER_USER}) reached. "
                f"Uninstall a pack before installing a new one."
            )

        now = datetime.now(timezone.utc).isoformat()

        try:
            # Check if row exists
            existing = (
                self._db.table("pack_installs")
                .select("id, status, source")
                .eq("user_id", user_id)
                .eq("pack_id", pack_id)
                .limit(1)
                .execute()
            )

            if existing.data:
                row = existing.data[0]
                if row["status"] == "uninstalled":
                    # Re-install
                    self._db.table("pack_installs").update({
                        "status": "active",
                        "source": source,
                        "stripe_session_id": stripe_session_id,
                        "updated_at": now,
                    }).eq("id", row["id"]).execute()
                    return {"pack_id": pack_id, "status": "active", "source": source}
                else:
                    # Already active or paused
                    return {"pack_id": pack_id, "status": row["status"], "source": row["source"]}
            else:
                # New install
                insert_data = {
                    "user_id": user_id,
                    "pack_id": pack_id,
                    "status": "active",
                    "source": source,
                    "installed_at": now,
                    "updated_at": now,
                }
                if stripe_session_id:
                    insert_data["stripe_session_id"] = stripe_session_id
                self._db.table("pack_installs").insert(insert_data).execute()
                return {"pack_id": pack_id, "status": "active", "source": source}
        except ValueError:
            raise  # Re-raise max installs error
        except Exception as e:
            logger.error(f"Failed to install pack {pack_id} for user {user_id}: {e}")
            return {"pack_id": pack_id, "status": "error", "error": str(e)}

    # ─── Uninstall ──────────────────────────────────────────

    def uninstall(self, user_id: str, pack_id: str) -> bool:
        """Soft-delete: sets status to 'uninstalled'."""
        if not self.enabled:
            return True

        try:
            self._db.table("pack_installs").update({
                "status": "uninstalled",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("user_id", user_id).eq("pack_id", pack_id).neq(
                "status", "uninstalled"
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to uninstall pack {pack_id}: {e}")
            return False

    # ─── Activate / Pause ───────────────────────────────────

    def activate(self, user_id: str, pack_id: str) -> bool:
        """Transition paused → active."""
        return self._transition(user_id, pack_id, from_status="paused", to_status="active")

    def pause(self, user_id: str, pack_id: str) -> bool:
        """Transition active → paused."""
        return self._transition(user_id, pack_id, from_status="active", to_status="paused")

    def _transition(self, user_id: str, pack_id: str, from_status: str, to_status: str) -> bool:
        if not self.enabled:
            return True
        try:
            self._db.table("pack_installs").update({
                "status": to_status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("user_id", user_id).eq("pack_id", pack_id).eq(
                "status", from_status
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to transition pack {pack_id} {from_status}→{to_status}: {e}")
            return False

    # ─── Query ──────────────────────────────────────────────

    def get_user_installs(self, user_id: str, status_filter: str | None = None) -> list[dict]:
        """Get all installs for a user, optionally filtered by status."""
        if not self.enabled:
            return []

        try:
            query = (
                self._db.table("pack_installs")
                .select("*")
                .eq("user_id", user_id)
            )
            if status_filter:
                query = query.eq("status", status_filter)
            else:
                query = query.neq("status", "uninstalled")

            result = query.order("installed_at", desc=True).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to get installs for user {user_id}: {e}")
            return []

    def is_installed(self, user_id: str, pack_id: str) -> bool:
        """Check if a pack is installed (active or paused) for a user."""
        if not self.enabled:
            return False

        try:
            result = (
                self._db.table("pack_installs")
                .select("status")
                .eq("user_id", user_id)
                .eq("pack_id", pack_id)
                .in_("status", ["active", "paused"])
                .limit(1)
                .execute()
            )
            return bool(result.data)
        except Exception as e:
            logger.error(f"Failed to check install status: {e}")
            return False

    def get_install_status(self, user_id: str, pack_id: str) -> str | None:
        """Get the install status for a specific pack. Returns None if not found."""
        if not self.enabled:
            return None

        try:
            result = (
                self._db.table("pack_installs")
                .select("status")
                .eq("user_id", user_id)
                .eq("pack_id", pack_id)
                .limit(1)
                .execute()
            )
            if result.data:
                return result.data[0]["status"]
            return None
        except Exception as e:
            logger.error(f"Failed to get install status: {e}")
            return None

    # ─── Auto-Install Defaults ──────────────────────────────

    def auto_install_defaults(self, user_id: str) -> int:
        """
        Install default packs for a new user. Idempotent.
        Returns count of newly installed packs.
        """
        if not self.enabled:
            return 0

        count = 0
        for pack_id in cfg.PACK_INSTALL_DEFAULT_PACKS:
            pack_id = pack_id.strip()
            if not pack_id:
                continue
            status = self.get_install_status(user_id, pack_id)
            if status is None:
                result = self.install(user_id, pack_id, source="default")
                if result.get("status") == "active":
                    count += 1

        if count:
            logger.info(f"Auto-installed {count} default packs for user {user_id}")
        return count

    # ─── Stripe Completion ──────────────────────────────────

    def complete_stripe_install(
        self, user_id: str, pack_id: str, stripe_session_id: str
    ) -> dict:
        """Install a pack as a completed Stripe purchase."""
        return self.install(
            user_id, pack_id,
            source="stripe",
            stripe_session_id=stripe_session_id,
        )

    # ─── Internal ───────────────────────────────────────────

    def _count_active_installs(self, user_id: str) -> int:
        """Count active + paused installs for max enforcement."""
        try:
            result = (
                self._db.table("pack_installs")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .in_("status", ["active", "paused"])
                .execute()
            )
            return result.count if result.count is not None else 0
        except Exception:
            return 0


# ─── Singleton ──────────────────────────────────────────────

_pack_install_service: Optional[PackInstallService] = None


def init_pack_install_service(db=None) -> PackInstallService:
    """Initialize the global pack install service. Called during app lifespan."""
    global _pack_install_service
    _pack_install_service = PackInstallService(db=db)
    logger.info("Pack install service initialized (enabled=%s)", _pack_install_service.enabled)
    return _pack_install_service


def get_pack_install_service() -> Optional[PackInstallService]:
    """Get the global pack install service instance."""
    return _pack_install_service
