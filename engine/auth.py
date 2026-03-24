"""
TMOS13 Authentication

Supabase Auth integration supporting email/password and OAuth providers
(Apple, Google, GitHub). Provides JWT verification, user profiles,
and FastAPI dependency injection for protected routes.
"""
import time
import uuid
import logging
from typing import Optional
from functools import lru_cache
from urllib.parse import urlparse

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

logger = logging.getLogger("tmos13.auth")

# Dedicated audit logger for compliance — SOC 2 requires traceable auth events.
# Can be routed to a separate file/service via logging config.
audit_log = logging.getLogger("tmos13.audit")

# ─── Models ─────────────────────────────────────────────

# ─── RBAC Definitions ────────────────────────────────────
# SOC 2 requires role-based access control. Roles are hierarchical:
#   viewer < user < editor < admin < owner
# Each role inherits all permissions of roles below it.

ROLE_HIERARCHY = ["viewer", "user", "editor", "admin", "owner"]

ROLE_PERMISSIONS = {
    "viewer": {
        "session:read", "health:read", "pack:read",
    },
    "user": {
        "session:read", "session:write", "health:read", "pack:read",
        "notes:read", "notes:write", "files:read", "files:write",
        "audio:use",
    },
    "editor": {
        "session:read", "session:write", "health:read", "pack:read",
        "notes:read", "notes:write", "notes:delete",
        "files:read", "files:write", "files:delete",
        "audio:use", "transcripts:read",
    },
    "admin": {
        "session:read", "session:write", "health:read", "pack:read",
        "notes:read", "notes:write", "notes:delete",
        "files:read", "files:write", "files:delete",
        "audio:use", "transcripts:read", "transcripts:delete",
        "alerts:read", "alerts:write", "alerts:delete",
        "monitoring:read", "billing:read", "users:read",
    },
    "owner": {
        "session:read", "session:write", "health:read", "pack:read",
        "notes:read", "notes:write", "notes:delete",
        "files:read", "files:write", "files:delete",
        "audio:use", "transcripts:read", "transcripts:delete",
        "alerts:read", "alerts:write", "alerts:delete",
        "monitoring:read", "monitoring:write",
        "billing:read", "billing:write",
        "users:read", "users:write", "users:delete",
        "privacy:admin",
    },
}


def scope_user_id(user: "UserProfile", requested_user_id: Optional[str] = None) -> str:
    """Admins+ can query any user. Regular users forced to their own ID."""
    if requested_user_id and user.is_at_least("admin"):
        return requested_user_id
    return user.user_id


_ALLOWED_REDIRECT_HOSTS = {
    "localhost",
    "127.0.0.1",
    "tmos13.ai",
    "www.tmos13.ai",
}


def _validate_redirect_url(url: str) -> bool:
    """Validate redirect URL against allowed hosts to prevent open redirect."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        return (
            parsed.scheme in ("http", "https")
            and host in _ALLOWED_REDIRECT_HOSTS
        )
    except Exception:
        return False


def role_has_permission(role: str, permission: str) -> bool:
    """Check if a role grants a specific permission."""
    return permission in ROLE_PERMISSIONS.get(role, set())


def role_at_least(role: str, minimum: str) -> bool:
    """Check if a role is at or above a minimum level in the hierarchy."""
    try:
        return ROLE_HIERARCHY.index(role) >= ROLE_HIERARCHY.index(minimum)
    except ValueError:
        return False


class UserProfile(BaseModel):
    user_id: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    provider: Optional[str] = None
    tier: str = "free"           # free | pro | enterprise
    role: str = "user"           # viewer | user | editor | admin | owner
    created_at: Optional[float] = None
    last_seen: Optional[float] = None
    # Extended profile fields (migration 018)
    preferred_name: Optional[str] = None
    title: Optional[str] = None
    organization: Optional[str] = None
    org_logo_url: Optional[str] = None
    timezone: str = "UTC"
    language: str = "en"
    communication_style: str = "balanced"
    industry: Optional[str] = None
    use_case: Optional[str] = None
    bio: Optional[str] = None
    onboarded_at: Optional[str] = None
    profile_version: int = 1

    def has_permission(self, permission: str) -> bool:
        """Check if this user has a specific permission."""
        return role_has_permission(self.role, permission)

    def is_at_least(self, minimum_role: str) -> bool:
        """Check if this user's role is at or above a minimum level."""
        return role_at_least(self.role, minimum_role)

class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: UserProfile
    expires_in: int

class OAuthStartResponse(BaseModel):
    url: str
    provider: str

class SignUpRequest(BaseModel):
    email: str
    password: str
    display_name: Optional[str] = None

class SignInRequest(BaseModel):
    email: str
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None

class DevSignInRequest(BaseModel):
    """Dev-only sign-in with configurable tier and role."""
    email: str = "dev@tmos13.ai"
    tier: str = "pro"       # free | pro | enterprise
    role: str = "user"      # viewer | user | editor | admin | owner

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    access_token: str
    refresh_token: str
    new_password: str


# ─── Auth Service ───────────────────────────────────────

class AuthService:
    """Wraps Supabase Auth for user management and JWT verification."""

    def __init__(self, supabase_url: str, supabase_anon_key: str, supabase_service_key: str,
                 dev_mode: bool = False):
        self.supabase_url = supabase_url
        self.anon_key = supabase_anon_key
        self.service_key = supabase_service_key
        self._admin_client = None
        self._anon_client = None

        if supabase_url and supabase_service_key:
            from supabase import create_client
            self._admin_client = create_client(supabase_url, supabase_service_key)
            logger.info("Auth service initialized with Supabase (admin client)")

        if supabase_url and supabase_anon_key:
            from supabase import create_client
            self._anon_client = create_client(supabase_url, supabase_anon_key)
            logger.info("Auth service initialized with Supabase (anon client)")

        if not self._admin_client and not self._anon_client:
            logger.warning("Auth service: Supabase not configured — auth features disabled")

        # Dev mode: allow mock auth when Supabase isn't fully configured.
        # Activates when dev_mode=True AND either client is missing.
        self._dev_mode = dev_mode and not self.fully_configured
        self._dev_users: dict[str, UserProfile] = {}          # access_token → profile
        self._dev_refresh_map: dict[str, str] = {}             # refresh_token → access_token

        # Verified-token cache: survives brief Supabase outages / Railway restarts.
        # Maps token → {"profile": UserProfile, "ts": float}
        self._verified_cache: dict[str, dict] = {}
        self._CACHE_TTL = 300  # seconds — serve cached profiles for up to 5 minutes
        if self._dev_mode:
            logger.info("Auth service running in DEV MODE — any credentials accepted")

    @property
    def enabled(self) -> bool:
        return self._admin_client is not None

    @property
    def fully_configured(self) -> bool:
        """True when both admin and anon Supabase clients are available."""
        return self._admin_client is not None and self._anon_client is not None

    # ─── Dev Auth ─────────────────────────────────────────

    def _dev_create_session(self, email: str, tier: str = "pro", role: str = "user") -> AuthResponse:
        """Create a mock auth session for development. No Supabase required."""
        # Deterministic user_id from email so the same email always gets the same user
        user_id = f"dev_{uuid.uuid5(uuid.NAMESPACE_DNS, email).hex[:12]}"
        token = f"dev_{uuid.uuid4().hex}"
        refresh = f"dev_refresh_{uuid.uuid4().hex}"

        profile = UserProfile(
            user_id=user_id,
            email=email,
            display_name=email.split("@")[0],
            provider="dev",
            tier=tier,
            role=role,
            created_at=time.time(),
            last_seen=time.time(),
        )

        self._dev_users[token] = profile
        self._dev_refresh_map[refresh] = token

        audit_log.info(f"AUTH dev_signin user={user_id} email={email} tier={tier} role={role}")

        return AuthResponse(
            access_token=token,
            refresh_token=refresh,
            user=profile,
            expires_in=86400,
        )

    # ─── Email/Password ──────────────────────────────────

    def sign_up(self, email: str, password: str, display_name: Optional[str] = None) -> AuthResponse:
        """Register a new user with email and password."""
        if not self.enabled or not self._anon_client:
            if self._dev_mode:
                return self._dev_create_session(email)
            raise HTTPException(503, "Authentication service unavailable")

        try:
            result = self._anon_client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "display_name": display_name or email.split("@")[0],
                    }
                }
            })

            user = result.user
            session = result.session

            # Create profile in our profiles table
            self._upsert_profile(user.id, email, display_name or email.split("@")[0], "email")
            profile = self._get_profile(user.id)

            audit_log.info(f"AUTH signup_success user={user.id} email={email} provider=email")

            # Sync to Resend audience
            try:
                from email_service import sync_to_resend_contacts
                name_parts = (display_name or email.split("@")[0]).split(None, 1)
                sync_to_resend_contacts(
                    email=email,
                    first_name=name_parts[0] if name_parts else "",
                    last_name=name_parts[1] if len(name_parts) > 1 else "",
                )
            except Exception:
                logger.debug("Resend contact sync on signup skipped", exc_info=True)

            return AuthResponse(
                access_token=session.access_token,
                refresh_token=session.refresh_token,
                user=profile or UserProfile(
                    user_id=user.id,
                    email=email,
                    display_name=display_name or email.split("@")[0],
                    provider="email",
                ),
                expires_in=session.expires_in,
            )
        except Exception as e:
            audit_log.warning(f"AUTH signup_failed email={email} reason={e}")
            logger.error(f"Sign up failed: {e}")
            raise HTTPException(400, f"Sign up failed: {str(e)}")

    def sign_in(self, email: str, password: str) -> AuthResponse:
        """Sign in with email and password."""
        if not self.enabled or not self._anon_client:
            if self._dev_mode:
                return self._dev_create_session(email)
            raise HTTPException(503, "Authentication service unavailable")

        try:
            result = self._anon_client.auth.sign_in_with_password({
                "email": email,
                "password": password,
            })

            user = result.user
            session = result.session

            # Update last seen
            self._touch_profile(user.id)

            profile = self._get_profile(user.id)

            audit_log.info(f"AUTH signin_success user={user.id} email={email} provider=email")

            return AuthResponse(
                access_token=session.access_token,
                refresh_token=session.refresh_token,
                user=profile or UserProfile(
                    user_id=user.id,
                    email=email,
                    provider="email",
                ),
                expires_in=session.expires_in,
            )
        except Exception as e:
            audit_log.warning(f"AUTH signin_failed email={email} reason=invalid_credentials")
            logger.error(f"Sign in failed: {e}")
            raise HTTPException(401, "Invalid email or password")

    def refresh_session(self, refresh_token: str) -> AuthResponse:
        """Refresh an expired session."""
        if not self.enabled or not self._anon_client:
            if self._dev_mode and refresh_token in self._dev_refresh_map:
                old_token = self._dev_refresh_map.pop(refresh_token)
                profile = self._dev_users.pop(old_token, None)
                if profile:
                    return self._dev_create_session(profile.email, profile.tier, profile.role)
            if self._dev_mode:
                raise HTTPException(401, "Invalid refresh token")
            raise HTTPException(503, "Authentication service unavailable")

        try:
            result = self._anon_client.auth.refresh_session(refresh_token)
            user = result.user
            session = result.session
            profile = self._get_profile(user.id)

            if not profile:
                # Profile missing — create it from Supabase auth user data
                email = user.email
                display_name = None
                avatar_url = None
                provider = "unknown"
                if user.user_metadata:
                    display_name = (
                        user.user_metadata.get("full_name")
                        or user.user_metadata.get("name")
                    )
                    avatar_url = user.user_metadata.get("avatar_url")
                if user.app_metadata:
                    provider = user.app_metadata.get("provider", "unknown")
                self._upsert_profile(user.id, email, display_name, provider, avatar_url)
                profile = self._get_profile(user.id)

            return AuthResponse(
                access_token=session.access_token,
                refresh_token=session.refresh_token,
                user=profile or UserProfile(user_id=user.id, email=user.email),
                expires_in=session.expires_in,
            )
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            raise HTTPException(401, "Token refresh failed")

    # ─── OAuth Providers ─────────────────────────────────

    def get_oauth_url(self, provider: str, redirect_url: str) -> OAuthStartResponse:
        """Generate OAuth sign-in URL for Apple, Google, or GitHub."""
        if not self.enabled or not self._anon_client:
            raise HTTPException(503, "Authentication service unavailable")

        valid_providers = {"apple", "google", "github"}
        if provider not in valid_providers:
            raise HTTPException(400, f"Invalid provider: {provider}. Must be one of: {', '.join(valid_providers)}")

        if not _validate_redirect_url(redirect_url):
            raise HTTPException(400, "Invalid redirect URL")

        try:
            result = self._anon_client.auth.sign_in_with_oauth({
                "provider": provider,
                "options": {
                    "redirect_to": redirect_url,
                }
            })

            return OAuthStartResponse(url=result.url, provider=provider)
        except Exception as e:
            logger.error(f"OAuth URL generation failed for {provider}: {e}")
            raise HTTPException(500, f"Failed to start {provider} authentication")

    def handle_oauth_callback(self, access_token: str, refresh_token: str) -> AuthResponse:
        """Exchange OAuth tokens after callback redirect."""
        if not self.enabled or not self._anon_client:
            raise HTTPException(503, "Authentication service unavailable")

        try:
            result = self._anon_client.auth.set_session(access_token, refresh_token)
            user = result.user
            session = result.session

            # Extract provider info
            provider = "oauth"
            if user.app_metadata and "provider" in user.app_metadata:
                provider = user.app_metadata["provider"]

            display_name = None
            email = user.email
            avatar_url = None

            if user.user_metadata:
                display_name = (
                    user.user_metadata.get("full_name")
                    or user.user_metadata.get("name")
                    or user.user_metadata.get("preferred_username")
                )
                avatar_url = user.user_metadata.get("avatar_url")

            self._upsert_profile(user.id, email, display_name, provider, avatar_url)
            profile = self._get_profile(user.id)

            audit_log.info(f"AUTH oauth_success user={user.id} email={email} provider={provider}")

            return AuthResponse(
                access_token=session.access_token,
                refresh_token=session.refresh_token,
                user=profile or UserProfile(
                    user_id=user.id,
                    email=email,
                    display_name=display_name,
                    avatar_url=avatar_url,
                    provider=provider,
                ),
                expires_in=session.expires_in,
            )
        except Exception as e:
            audit_log.warning(f"AUTH oauth_failed provider={provider} reason={e}")
            logger.error(f"OAuth callback handling failed: {e}")
            raise HTTPException(401, "OAuth authentication failed")

    # ─── Token Verification ──────────────────────────────

    def verify_token(self, token: str) -> UserProfile:
        """Verify a JWT access token and return the user profile."""
        if not self.enabled or not self._admin_client:
            if self._dev_mode and token in self._dev_users:
                return self._dev_users[token]
            if self._dev_mode and token.startswith("dev_"):
                # Token is structurally valid but not in _dev_users — server restarted.
                # Rehydrate a synthetic profile so the session survives a Railway redeploy
                # without forcing the user to re-authenticate.
                rehydrated = UserProfile(
                    user_id=f"dev_{uuid.uuid5(uuid.NAMESPACE_DNS, token).hex[:12]}",
                    email="dev@tmos13.ai",
                    display_name="Dev User",
                    provider="dev",
                    tier="pro",
                    role="admin",
                    created_at=time.time(),
                    last_seen=time.time(),
                )
                self._dev_users[token] = rehydrated  # re-register so subsequent calls are instant
                audit_log.info(f"AUTH dev_token_rehydrated user={rehydrated.user_id}")
                return rehydrated
            if self._dev_mode:
                raise HTTPException(401, "Invalid or expired dev token")
            raise HTTPException(503, "Authentication service unavailable")

        # Check verified-token cache first (survives brief Supabase outages)
        cached = self._verified_cache.get(token)
        if cached and (time.time() - cached["ts"]) < self._CACHE_TTL:
            return cached["profile"]

        try:
            result = self._admin_client.auth.get_user(token)
            user = result.user
            profile = self._get_profile(user.id)

            if profile:
                self._verified_cache[token] = {"profile": profile, "ts": time.time()}
                return profile

            # Profile missing — create it from Supabase auth user data
            email = user.email
            display_name = None
            avatar_url = None
            provider = user.app_metadata.get("provider", "unknown") if user.app_metadata else "unknown"
            if user.user_metadata:
                display_name = (
                    user.user_metadata.get("full_name")
                    or user.user_metadata.get("name")
                )
                avatar_url = user.user_metadata.get("avatar_url")
            self._upsert_profile(user.id, email, display_name, provider, avatar_url)
            profile = self._get_profile(user.id)

            result_profile = profile or UserProfile(
                user_id=user.id,
                email=email,
                provider=provider,
            )
            self._verified_cache[token] = {"profile": result_profile, "ts": time.time()}
            return result_profile
        except HTTPException:
            raise
        except Exception as e:
            # Distinguish transient network errors from real auth failures.
            # Supabase client uses httpx; network failures surface as
            # ConnectionError, TimeoutError, OSError, or httpx.TransportError.
            is_transient = isinstance(e, (ConnectionError, TimeoutError, OSError))
            if not is_transient:
                try:
                    import httpx
                    is_transient = isinstance(e, httpx.TransportError)
                except ImportError:
                    pass

            if is_transient:
                stale = self._verified_cache.get(token)
                if stale:
                    logger.warning(f"Supabase unreachable, serving stale profile: {e}")
                    return stale["profile"]
                audit_log.warning(f"AUTH transient_failure reason={e}")
                raise HTTPException(503, "Authentication service temporarily unavailable")

            audit_log.warning(f"AUTH token_invalid reason={e}")
            logger.error(f"Token verification failed: {e}")
            raise HTTPException(401, "Invalid or expired token")

    # ─── Profile Management ──────────────────────────────

    def get_profile(self, user_id: str) -> UserProfile:
        """Get a user's profile."""
        profile = self._get_profile(user_id)
        if not profile:
            raise HTTPException(404, "User profile not found")
        return profile

    def update_profile(self, user_id: str, updates: UpdateProfileRequest) -> UserProfile:
        """Update a user's profile."""
        if not self.enabled:
            raise HTTPException(503, "Authentication service unavailable")

        try:
            update_data = {"updated_at": time.time()}
            if updates.display_name is not None:
                update_data["display_name"] = updates.display_name
            if updates.avatar_url is not None:
                update_data["avatar_url"] = updates.avatar_url

            self._admin_client.table("profiles").update(update_data).eq("user_id", user_id).execute()
            profile = self._get_profile(user_id)
            if not profile:
                raise HTTPException(404, "Profile not found after update")
            return profile
        except Exception as e:
            logger.error(f"Profile update failed: {e}")
            raise HTTPException(500, "Failed to update profile")

    # ─── Password Reset ─────────────────────────────────

    def forgot_password(self, email: str, redirect_url: Optional[str] = None) -> None:
        """Send a password reset email via Supabase."""
        if not self.enabled or not self._anon_client:
            if self._dev_mode:
                logger.info(f"Dev mode: password reset requested for {email} (no email sent)")
                return
            raise HTTPException(503, "Authentication service unavailable")

        if redirect_url and not _validate_redirect_url(redirect_url):
            raise HTTPException(400, "Invalid redirect URL")

        try:
            options = {}
            if redirect_url:
                options["redirect_to"] = redirect_url
            self._anon_client.auth.reset_password_for_email(email, options=options)
            audit_log.info(f"AUTH password_reset_requested email={email}")
        except Exception as e:
            # Don't reveal whether the email exists — always succeed silently
            logger.warning(f"Password reset request error (suppressed): {e}")

    def reset_password(self, access_token: str, refresh_token: str, new_password: str) -> None:
        """Set a new password using the session from a reset email link."""
        if not self.enabled or not self._anon_client:
            raise HTTPException(503, "Authentication service unavailable")

        try:
            # The reset email link contains tokens. The frontend extracts them
            # from the URL hash and sends them here. First, establish the session
            # from those tokens, then update the password.
            self._anon_client.auth.set_session(access_token, refresh_token)
            self._anon_client.auth.update_user({"password": new_password})
            audit_log.info("AUTH password_reset_success")
        except Exception as e:
            logger.error(f"Password reset failed: {e}")
            raise HTTPException(400, "Password reset failed. The link may have expired.")

    def sign_out(self, token: str) -> None:
        """Sign out and invalidate the session."""
        if self._dev_mode:
            self._dev_users.pop(token, None)
            return
        if not self.enabled:
            return
        try:
            self._admin_client.auth.admin.sign_out(token)
        except Exception as e:
            logger.warning(f"Sign out error (non-fatal): {e}")

    # ─── Internal Helpers ────────────────────────────────

    def _upsert_profile(self, user_id: str, email: Optional[str], display_name: Optional[str],
                        provider: str, avatar_url: Optional[str] = None):
        """Create or update user profile in profiles table."""
        if not self._admin_client:
            return
        try:
            self._admin_client.table("profiles").upsert({
                "user_id": user_id,
                "email": email,
                "display_name": display_name or (email.split("@")[0] if email else "User"),
                "avatar_url": avatar_url,
                "provider": provider,
                "updated_at": time.time(),
            }, on_conflict="user_id").execute()
        except Exception as e:
            logger.error(f"Profile upsert failed: {e}")

    def _get_profile(self, user_id: str) -> Optional[UserProfile]:
        """Fetch profile from profiles table."""
        if not self._admin_client:
            return None
        try:
            result = self._admin_client.table("profiles").select("*").eq("user_id", user_id).single().execute()
            if result.data:
                d = result.data
                return UserProfile(
                    user_id=d["user_id"],
                    email=d.get("email"),
                    display_name=d.get("display_name"),
                    avatar_url=d.get("avatar_url"),
                    provider=d.get("provider"),
                    tier=d.get("tier", "free"),
                    role=d.get("role", "user"),
                    created_at=d.get("created_at"),
                    last_seen=d.get("updated_at"),
                    preferred_name=d.get("preferred_name"),
                    title=d.get("title"),
                    organization=d.get("org_name") or d.get("organization"),
                    org_logo_url=d.get("org_logo_url"),
                    timezone=d.get("timezone", "UTC"),
                    language=d.get("language", "en"),
                    communication_style=d.get("communication_style", "balanced"),
                    industry=d.get("industry"),
                    use_case=d.get("use_case"),
                    bio=d.get("bio"),
                    onboarded_at=d.get("onboarded_at"),
                    profile_version=d.get("profile_version", 1),
                )
        except Exception:
            pass
        return None

    def _touch_profile(self, user_id: str):
        """Update last_seen timestamp."""
        if not self._admin_client:
            return
        try:
            self._admin_client.table("profiles").update(
                {"updated_at": time.time()}
            ).eq("user_id", user_id).execute()
        except Exception:
            pass

    # ─── UI Preferences ──────────────────────────────────

    def get_ui_preferences(self, user_id: str) -> dict:
        """Fetch user UI preferences, creating defaults if missing."""
        if not self._admin_client:
            return {}
        try:
            result = self._admin_client.table("user_ui_preferences").select("*").eq("user_id", user_id).single().execute()
            if result.data:
                return {
                    "sidebar_state": result.data.get("sidebar_state", "compact"),
                    "departments_expanded": result.data.get("departments_expanded", False),
                    "last_dashboard_view": result.data.get("last_dashboard_view", "overview"),
                    "brief_dismissed": result.data.get("brief_dismissed", False),
                }
        except Exception:
            pass
        return {
            "sidebar_state": "compact",
            "departments_expanded": False,
            "last_dashboard_view": "overview",
            "brief_dismissed": False,
        }

    def update_ui_preferences(self, user_id: str, updates: dict) -> dict:
        """Update user UI preferences (upsert)."""
        if not self._admin_client:
            return updates
        allowed_keys = {"sidebar_state", "departments_expanded", "last_dashboard_view", "brief_dismissed"}
        clean = {k: v for k, v in updates.items() if k in allowed_keys}
        if not clean:
            return self.get_ui_preferences(user_id)
        try:
            clean["user_id"] = user_id
            self._admin_client.table("user_ui_preferences").upsert(
                clean, on_conflict="user_id"
            ).execute()
        except Exception as e:
            logger.error(f"UI preferences upsert failed: {e}")
        return self.get_ui_preferences(user_id)


# ─── FastAPI Dependencies ───────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=False)

_auth_service: Optional[AuthService] = None


def init_auth_service(supabase_url: str, anon_key: str, service_key: str,
                      dev_mode: bool = False) -> AuthService:
    """Initialize the global auth service. Called during app lifespan."""
    global _auth_service
    _auth_service = AuthService(supabase_url, anon_key, service_key, dev_mode=dev_mode)
    return _auth_service


def get_auth_service() -> AuthService:
    """Get the global auth service instance."""
    if _auth_service is None:
        raise HTTPException(503, "Auth service not initialized")
    return _auth_service


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Optional[UserProfile]:
    """
    FastAPI dependency: extract and verify the Bearer token.
    Returns UserProfile if authenticated, None if no token provided.
    """
    if credentials is None:
        return None

    auth = get_auth_service()
    return auth.verify_token(credentials.credentials)


async def require_auth(
    user: Optional[UserProfile] = Depends(get_current_user),
) -> UserProfile:
    """FastAPI dependency: require authentication. 401 if not authenticated."""
    if user is None:
        raise HTTPException(401, "Authentication required")
    return user


async def require_tier(required: str = "pro"):
    """Factory for tier-gated dependencies."""
    tier_order = {"free": 0, "pro": 1, "enterprise": 2}

    async def check_tier(user: UserProfile = Depends(require_auth)) -> UserProfile:
        if tier_order.get(user.tier, 0) < tier_order.get(required, 1):
            raise HTTPException(403, f"This feature requires a {required} subscription")
        return user

    return check_tier


def require_role(minimum_role: str):
    """
    FastAPI dependency factory: require a minimum role level.

    Usage:
        @app.get("/admin/users", dependencies=[Depends(require_role("admin"))])
    """
    async def _check(request: Request, user: UserProfile = Depends(require_auth)) -> UserProfile:
        if not user.is_at_least(minimum_role):
            audit_log.warning(
                f"RBAC role_denied user={user.user_id} role={user.role} "
                f"required={minimum_role} method={request.method} path={request.url.path}"
            )
            raise HTTPException(
                403,
                f"Insufficient permissions. Required role: {minimum_role}",
            )
        return user
    return _check


def require_permission(permission: str):
    """
    FastAPI dependency factory: require a specific permission.

    Usage:
        @app.delete("/notes/{id}", dependencies=[Depends(require_permission("notes:delete"))])
    """
    async def _check(request: Request, user: UserProfile = Depends(require_auth)) -> UserProfile:
        if not user.has_permission(permission):
            audit_log.warning(
                f"RBAC permission_denied user={user.user_id} role={user.role} "
                f"permission={permission} method={request.method} path={request.url.path}"
            )
            raise HTTPException(
                403,
                f"Insufficient permissions. Required: {permission}",
            )
        return user
    return _check


# ─── Endpoint Registration ──────────────────────────────

def register_auth_endpoints(app, auth_service: AuthService):
    """Register all /auth/* endpoints on the FastAPI app."""

    @app.post("/auth/signup", response_model=AuthResponse)
    async def signup(req: SignUpRequest):
        """Register a new account with email and password."""
        from config import REGISTRATION_OPEN
        if not REGISTRATION_OPEN:
            raise HTTPException(
                403,
                "Registration is currently by invitation only. Contact hello@tmos13.ai for access.",
            )
        return auth_service.sign_up(req.email, req.password, req.display_name)

    @app.post("/auth/signin", response_model=AuthResponse)
    async def signin(req: SignInRequest):
        """Sign in with email and password."""
        return auth_service.sign_in(req.email, req.password)

    @app.post("/auth/refresh", response_model=AuthResponse)
    async def refresh(req: RefreshRequest):
        """Refresh an expired access token."""
        return auth_service.refresh_session(req.refresh_token)

    @app.post("/auth/signout")
    async def signout(user: UserProfile = Depends(require_auth),
                      credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme)):
        """Sign out and invalidate the current session."""
        auth_service.sign_out(credentials.credentials)
        return {"status": "signed_out"}

    @app.get("/auth/oauth/{provider}", response_model=OAuthStartResponse)
    async def oauth_start(provider: str, redirect_url: str = "http://localhost:3000/auth/callback"):
        """Start OAuth flow for Apple, Google, or GitHub."""
        return auth_service.get_oauth_url(provider, redirect_url)

    @app.post("/auth/oauth/callback", response_model=AuthResponse)
    async def oauth_callback(access_token: str, refresh_token: str):
        """Complete OAuth flow after provider redirect."""
        return auth_service.handle_oauth_callback(access_token, refresh_token)

    @app.post("/auth/forgot-password")
    async def forgot_password(req: ForgotPasswordRequest):
        """Send a password reset email."""
        auth_service.forgot_password(req.email)
        return {"status": "ok"}

    @app.post("/auth/reset-password")
    async def reset_password(req: ResetPasswordRequest):
        """Set a new password using tokens from the reset email link."""
        auth_service.reset_password(req.access_token, req.refresh_token, req.new_password)
        return {"status": "ok"}

    @app.get("/auth/me", response_model=UserProfile)
    async def get_me(user: UserProfile = Depends(require_auth)):
        """Get the authenticated user's profile."""
        return user

    @app.get("/auth/me/debug")
    async def debug_me(user: UserProfile = Depends(require_auth)):
        """Full auth state dump for the authenticated user."""
        return {
            "user_id": user.user_id,
            "email": user.email,
            "role": user.role,
            "tier": user.tier,
            "provider": user.provider,
            "permissions": sorted(list(ROLE_PERMISSIONS.get(user.role, set()))),
            "role_hierarchy_index": ROLE_HIERARCHY.index(user.role) if user.role in ROLE_HIERARCHY else -1,
            "is_owner": user.role == "owner",
            "is_admin_or_above": user.is_at_least("admin"),
            "display_name": user.display_name,
            "created_at": user.created_at,
            "last_seen": user.last_seen,
        }

    @app.patch("/auth/me", response_model=UserProfile)
    async def update_me(updates: UpdateProfileRequest, user: UserProfile = Depends(require_auth)):
        """Update the authenticated user's profile."""
        return auth_service.update_profile(user.user_id, updates)

    # ─── UI Preferences ────────────────────────────────────

    @app.get("/auth/me/preferences")
    async def get_preferences(user: UserProfile = Depends(require_auth)):
        """Get the authenticated user's UI preferences."""
        return auth_service.get_ui_preferences(user.user_id)

    @app.patch("/auth/me/preferences")
    async def update_preferences(updates: dict, user: UserProfile = Depends(require_auth)):
        """Update the authenticated user's UI preferences."""
        return auth_service.update_ui_preferences(user.user_id, updates)

    # ─── Dev-only endpoint ────────────────────────────────
    if auth_service._dev_mode:
        @app.post("/auth/dev/signin", response_model=AuthResponse)
        async def dev_signin(req: DevSignInRequest):
            """Dev-only: sign in with any tier/role. No Supabase required."""
            valid_tiers = {"free", "pro", "enterprise"}
            if req.tier not in valid_tiers:
                raise HTTPException(400, f"Invalid tier. Must be one of: {', '.join(valid_tiers)}")
            valid_roles = set(ROLE_HIERARCHY)
            if req.role not in valid_roles:
                raise HTTPException(400, f"Invalid role. Must be one of: {', '.join(valid_roles)}")
            return auth_service._dev_create_session(req.email, req.tier, req.role)

        logger.info("Dev auth endpoint registered: POST /auth/dev/signin")

    logger.info("Auth endpoints registered: /auth/*")
