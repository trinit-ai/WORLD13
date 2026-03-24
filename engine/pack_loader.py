"""
TMOS13 Pack Loader

Loads and validates pack manifests from protocols/packs/{pack_id}/manifest.json.
Replaces hardcoded cartridge definitions, commands, and feature flags with
data-driven configuration sourced from manifest files.

Supports two manifest schemas:
  - Legacy (guest, enterprise): pack_id, personality, cartridges as dict,
    commands.numerical, settings_defaults, file-based cartridge refs.
  - V2 (CRM, legal_intake, etc.): id, cartridges as array, protocol-based refs,
    pattern-based commands, settings, icon/category/theme/description.

The loader normalizes both to a common internal format.

Usage:
    from pack_loader import PackLoader
    pack = PackLoader("guest")
    pack.cartridges        # dict of cartridge definitions
    pack.nav_patterns      # pre-compiled regex navigation patterns
    pack.features          # feature flag dict
"""
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("tmos13.pack_loader")

# ─── Pack Aliases ──────────────────────────────────────────
# Backward-compat: old pack IDs resolve to their renamed successors.
PACK_ALIASES = {"tmos13_site": "guest"}

# ─── Paths ─────────────────────────────────────────────────

_THIS_DIR = Path(__file__).parent
PACKS_DIR = _THIS_DIR.parent / "protocols" / "packs"
LIBRARY_DIR = _THIS_DIR.parent / "protocols" / "library"
SCHEMA_PATH = _THIS_DIR.parent / "protocols" / "schema" / "manifest.schema.json"

# ─── Pack Filtering ────────────────────────────────────────

# Packs excluded from the public catalog (templates + legacy)
_EXCLUDED_PREFIXES = ("base_",)
_EXCLUDED_IDS = frozenset({"enterprise"})

# Regex to detect unresolved template variables like {{Simulator Name}}
_TEMPLATE_VAR_RE = re.compile(r"\{\{.+?\}\}")


def _is_deployable(pack_dir_name: str) -> bool:
    """Check if a pack should appear in the public catalog."""
    if any(pack_dir_name.startswith(p) for p in _EXCLUDED_PREFIXES):
        return False
    if pack_dir_name in _EXCLUDED_IDS:
        return False
    return True


def _has_template_vars(manifest: dict) -> bool:
    """Check if a manifest contains unresolved {{...}} template variables."""
    for field in ("name", "description", "icon", "id"):
        val = manifest.get(field, "")
        if isinstance(val, str) and _TEMPLATE_VAR_RE.search(val):
            return True
    # Check theme accent — a template color breaks CSS
    theme = manifest.get("theme", {})
    accent = theme.get("accent", "")
    if isinstance(accent, str) and _TEMPLATE_VAR_RE.search(accent):
        return True
    return False


# ─── Legacy Pack Metadata ──────────────────────────────────
# Old-style manifests (guest, enterprise) lack icon/category/theme.
# These defaults enrich them during normalization.

_LEGACY_ICONS = {
    "guest": "\U0001F535",
    "enterprise": "\U0001F3E2",
}

_LEGACY_CATEGORIES = {
    "guest": "home",
    "enterprise": "verticals",
}

_LEGACY_THEMES = {
    "guest": {"accent": "#2563EB", "surface": "#060a0d", "text": "#E5E7EB"},
    "enterprise": {"accent": "#5B8DEF", "surface": "#0A0D11", "text": "#E5E7EB"},
}


class PackValidationError(Exception):
    """Raised when a pack manifest fails validation."""
    pass


class PackLoader:
    """
    Loads a TMOS13 experience pack from its manifest.

    Each pack defines cartridges, commands, features, personality,
    and settings that drive the engine's behavior for a specific vertical.
    """

    def __init__(self, pack_id: str = None):
        raw_id = pack_id or os.environ.get("TMOS13_PACK", "guest")
        self.pack_id = PACK_ALIASES.get(raw_id, raw_id)
        self.protocol_dir = PACKS_DIR / self.pack_id
        self._raw_manifest: dict = self._load_manifest()
        self._manifest: dict = self._normalize(self._raw_manifest)
        self._compiled_nav: Optional[dict] = None
        self._validate()
        logger.info(f"Pack loaded: {self.pack_id} ({self.name} v{self.version})")

    def _load_manifest(self) -> dict:
        """Load and parse the manifest.json for this pack."""
        manifest_path = self.protocol_dir / "manifest.json"
        if not manifest_path.exists():
            raise PackValidationError(
                f"Pack manifest not found: {manifest_path}"
            )
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise PackValidationError(
                f"Invalid JSON in pack manifest {manifest_path}: {e}"
            )

    # ─── Schema Normalization ────────────────────────────────

    def _is_v2(self, m: dict) -> bool:
        """Detect v2-style manifest (array cartridges, 'id' field, etc.)."""
        return isinstance(m.get("cartridges"), list) or "id" in m and "pack_id" not in m

    def _normalize(self, m: dict) -> dict:
        """Normalize manifest to internal canonical format."""
        if not self._is_v2(m):
            return self._enrich_legacy(m)
        return self._normalize_v2(m)

    def _enrich_legacy(self, m: dict) -> dict:
        """Add missing metadata fields to legacy manifests."""
        out = dict(m)
        if "icon" not in out:
            out["icon"] = _LEGACY_ICONS.get(self.pack_id, "")
        if "category" not in out:
            out["category"] = _LEGACY_CATEGORIES.get(self.pack_id, "")
        if "description" not in out:
            out["description"] = out.get("philosophy", "")
        if "theme" not in out:
            out["theme"] = _LEGACY_THEMES.get(self.pack_id, {})
        return out

    def _normalize_v2(self, m: dict) -> dict:
        """Convert v2 manifest to the canonical internal format."""
        out = dict(m)

        # ─── pack_id: v2 uses 'id', canonicalize to pack_id
        out["pack_id"] = self.pack_id  # always use directory name

        # ─── cartridges: array -> dict
        if isinstance(m.get("cartridges"), list):
            is_mono = m.get("assembly_mode") == "monolithic"
            carts = {}
            for i, c in enumerate(m["cartridges"]):
                key = c["id"]
                carts[key] = {
                    "name": c["name"],
                    "number": c.get("number", i + 1),
                }
                if is_mono:
                    if "section" in c:
                        carts[key]["section"] = c["section"]
                else:
                    carts[key]["file"] = c.get("protocol", c.get("file", f"{key}.md"))
                if "description" in c:
                    carts[key]["description"] = c["description"]
                if "state_class" in c:
                    carts[key]["state_class"] = c["state_class"]
                if "data_rail" in c:
                    carts[key]["data_rail"] = c["data_rail"]
                if "data_rails" in c:
                    carts[key]["data_rails"] = c["data_rails"]
                if c.get("passive"):
                    carts[key]["passive"] = True
                    carts[key].pop("file", None)  # passive carts have no local protocol file
            out["cartridges"] = carts

        # ─── personality: synthesize from available fields if missing
        if "personality" not in out:
            out["personality"] = {
                "tone": m.get("settings", {}).get("tone", {}).get("default", "conversational"),
                "warmth": 0.6,
                "humor": 0.2,
                "formality": 0.5,
                "identity_name": m.get("name", self.pack_id),
                "identity_description": m.get("description", ""),
            }

        # ─── settings_defaults: v2 uses 'settings' with {default, options} structure
        if "settings_defaults" not in out and "settings" in m:
            defaults = {}
            for key, val in m["settings"].items():
                if isinstance(val, dict) and "default" in val:
                    defaults[key] = val["default"]
                else:
                    defaults[key] = val
            out["settings_defaults"] = defaults

        # ─── commands: normalize v2 navigation format
        commands = dict(m.get("commands", {}))

        # Ensure numerical section exists
        if "numerical" not in commands:
            commands["numerical"] = {}

        # Normalize navigation: v2 uses {name: {pattern, cartridge}}
        # -> canonical: {pattern_str: {action, target, meta?}}
        raw_nav = commands.get("navigation", {})
        if raw_nav and isinstance(next(iter(raw_nav.values()), None), dict):
            first_val = next(iter(raw_nav.values()))
            if "cartridge" in first_val or "pattern" in first_val:
                normalized_nav = {}
                for _name, entry in raw_nav.items():
                    pattern = entry.get("pattern", _name)
                    target = entry.get("cartridge", entry.get("target", _name))
                    normalized_nav[pattern] = {
                        "action": "navigate",
                        "target": target,
                    }
                    if "meta" in entry:
                        normalized_nav[pattern]["meta"] = entry["meta"]
                commands["navigation"] = normalized_nav

        # Normalize session commands: v2 uses {name: {pattern, action}}
        # -> canonical: {PATTERN: {action, label?, response?}}
        raw_session = commands.get("session", {})
        if raw_session and isinstance(next(iter(raw_session.values()), None), dict):
            first_val = next(iter(raw_session.values()))
            if "pattern" in first_val:
                normalized_session = {}
                for cmd_name, entry in raw_session.items():
                    action_str = entry.get("action", cmd_name)
                    # Map v2 action names to canonical actions
                    if action_str == "reset_session":
                        canonical_action = "direct"
                        response = "Session reset. How can I help you?"
                    elif action_str == "show_menu":
                        canonical_action = "menu"
                        response = None
                    elif action_str == "show_status":
                        canonical_action = "direct"
                        response = None
                    elif action_str == "escalate_to_agent":
                        canonical_action = "direct"
                        response = None
                    else:
                        canonical_action = "direct"
                        response = None

                    key = cmd_name.upper()
                    normalized_session[key] = {"action": canonical_action}
                    if response:
                        normalized_session[key]["response"] = response
                    # Store the regex pattern for matching
                    normalized_session[key]["_pattern"] = entry.get("pattern", "")
                commands["session"] = normalized_session

        out["commands"] = commands

        # ─── tagline: derive from description if not present
        if "tagline" not in out and "description" in m:
            desc = m["description"]
            # Use first sentence or first 80 chars
            dot_idx = desc.find(".")
            if 0 < dot_idx < 80:
                out["tagline"] = desc[:dot_idx + 1]
            else:
                out["tagline"] = desc[:80]

        return out

    def _validate(self):
        """Validate the normalized manifest structure and referenced files."""
        m = self._manifest
        errors = []

        # Required top-level fields (after normalization)
        for field in ("pack_id", "name", "version", "cartridges",
                      "system_screens", "commands", "features"):
            if field not in m:
                errors.append(f"Missing required field: {field}")

        if errors:
            raise PackValidationError(
                f"Pack '{self.pack_id}' manifest errors: {'; '.join(errors)}"
            )

        # Validate referenced protocol files exist
        missing_files = []
        is_mono = m.get("assembly_mode") == "monolithic"

        if is_mono:
            # Monolithic: validate single compiled protocol file
            proto_file = m.get("protocol_file", "")
            if not proto_file:
                errors.append("Monolithic assembly_mode requires 'protocol_file' field")
            else:
                filepath = self.protocol_dir / proto_file
                if not filepath.exists():
                    missing_files.append(f"protocol_file: {proto_file}")
        else:
            # Assembled: validate individual cartridge files
            for key, cart in m.get("cartridges", {}).items():
                if cart.get("passive"):
                    continue  # passive cartridges load from shared protocol dir
                filepath = self.protocol_dir / cart.get("file", "")
                if not filepath.exists():
                    missing_files.append(f"cartridge '{key}': {cart.get('file')}")

            for screen, sv in m.get("system_screens", {}).items():
                filename = sv.get("file", "") if isinstance(sv, dict) else sv
                if filename and '.' in filename:
                    filepath = self.protocol_dir / filename
                    if not filepath.exists():
                        missing_files.append(f"system_screen '{screen}': {filename}")

        if missing_files:
            errors.append(f"Missing protocol files: {', '.join(missing_files)}")

        # Validate navigation regex patterns compile
        nav = m.get("commands", {}).get("navigation", {})
        if isinstance(nav, dict):
            patterns = list(nav.keys())
        elif isinstance(nav, list):
            patterns = [item.get("pattern", "") for item in nav if isinstance(item, dict)]
        else:
            patterns = []
        for pattern_str in patterns:
            if pattern_str:
                try:
                    re.compile(pattern_str)
                except re.error as e:
                    errors.append(f"Invalid navigation regex '{pattern_str}': {e}")

        self._validate_rails(errors)

        if errors:
            raise PackValidationError(
                f"Pack '{self.pack_id}' validation errors: {'; '.join(errors)}"
            )

    def _validate_rails(self, errors: list[str]):
        """Validate data_rail / data_rails field definitions on cartridges."""
        _ALLOWED_TYPES = {
            "text", "email", "password", "number", "date",
            "address", "phone", "select",
        }
        for cart_id, cart in self._manifest.get("cartridges", {}).items():
            rails_to_check = {}
            if "data_rail" in cart:
                rails_to_check["default"] = cart["data_rail"]
            if "data_rails" in cart:
                for rail_id, rail_def in cart["data_rails"].items():
                    rails_to_check[rail_id] = rail_def
            for rail_id, rail_def in rails_to_check.items():
                fields = rail_def.get("fields", [])
                seen_ids = set()
                for f in fields:
                    fid = f.get("id", "")
                    if not fid:
                        errors.append(
                            f"Cartridge '{cart_id}' rail '{rail_id}': "
                            f"field missing 'id'"
                        )
                        continue
                    if fid in seen_ids:
                        errors.append(
                            f"Cartridge '{cart_id}' rail '{rail_id}': "
                            f"duplicate field id '{fid}'"
                        )
                    seen_ids.add(fid)
                    ftype = f.get("type", "")
                    if ftype not in _ALLOWED_TYPES:
                        errors.append(
                            f"Cartridge '{cart_id}' rail '{rail_id}': "
                            f"field '{fid}' has invalid type '{ftype}'"
                        )
                    if ftype == "select" and not f.get("options"):
                        errors.append(
                            f"Cartridge '{cart_id}' rail '{rail_id}': "
                            f"select field '{fid}' has no options"
                        )

    # ─── Properties ──────────────────────────────────────────

    @property
    def routing_strategy(self) -> str:
        """Routing strategy: 'passthrough' (default), 'regex', 'menu', or 'conversational'."""
        return self._manifest.get("routing", {}).get("strategy", "passthrough")

    @property
    def routing_config(self) -> dict:
        """Full routing configuration from pack manifest."""
        return dict(self._manifest.get("routing", {}))

    @property
    def assembly_mode(self) -> str:
        """Assembly mode: 'assembled' (default) or 'monolithic'."""
        return self._manifest.get("assembly_mode", "assembled")

    @property
    def is_monolithic(self) -> bool:
        """Whether this pack uses monolithic assembly (single compiled protocol file)."""
        return self.assembly_mode == "monolithic"

    @property
    def protocol_file(self) -> str:
        """Monolithic protocol file name (only for assembly_mode='monolithic')."""
        return self._manifest.get("protocol_file", "")

    @property
    def name(self) -> str:
        return self._manifest.get("name", self.pack_id)

    @property
    def version(self) -> str:
        return self._manifest.get("version", "0.0")

    @property
    def tagline(self) -> str:
        return self._manifest.get("tagline", "")

    @property
    def philosophy(self) -> str:
        return self._manifest.get("philosophy", "")

    @property
    def personality(self) -> dict:
        return self._manifest.get("personality", {})

    @property
    def icon(self) -> str:
        return self._manifest.get("icon", "")

    @property
    def category(self) -> str:
        return self._manifest.get("category", "")

    @property
    def description(self) -> str:
        return self._manifest.get("description", "")

    @property
    def theme(self) -> dict:
        return dict(self._manifest.get("theme", {}))

    @property
    def cartridges(self) -> dict:
        """Cartridge map in the format expected by config.py."""
        result = {}
        is_mono = self._manifest.get("assembly_mode") == "monolithic"
        for key, cart in self._manifest.get("cartridges", {}).items():
            if cart.get("passive"):
                continue  # passive cartridges excluded from runtime map
            entry = {
                "name": cart["name"],
                "number": cart["number"],
            }
            if is_mono:
                entry["section"] = cart.get("section", "")
            else:
                entry["file"] = cart["file"]
            if "description" in cart:
                entry["description"] = cart["description"]
            if "state_class" in cart:
                entry["state_class"] = cart["state_class"]
            result[key] = entry
        return result

    @property
    def system_screens(self) -> dict:
        """Map of screen_name -> filename."""
        raw = self._manifest.get("system_screens", {})
        return {
            k: (v.get("file", "") if isinstance(v, dict) else v)
            for k, v in raw.items()
        }

    @property
    def numerical_commands(self) -> dict:
        """Map of number string -> {action, target?, response?}."""
        return dict(self._manifest.get("commands", {}).get("numerical", {}))

    @property
    def session_commands(self) -> dict:
        """Map of command string -> {action, label?, response?}."""
        return dict(self._manifest.get("commands", {}).get("session", {}))

    @property
    def nav_patterns(self) -> dict:
        """
        Pre-compiled navigation patterns.
        Returns: dict of compiled_regex -> (action, target, meta_dict)
        """
        if self._compiled_nav is not None:
            return self._compiled_nav

        self._compiled_nav = {}
        raw = self._manifest.get("commands", {}).get("navigation", {})
        for pattern_str, cmd in raw.items():
            try:
                compiled = re.compile(r"\b(" + pattern_str + r")", re.IGNORECASE)
            except re.error:
                # Skip patterns that can't compile with word boundaries
                try:
                    compiled = re.compile(pattern_str, re.IGNORECASE)
                except re.error:
                    logger.warning(f"Pack {self.pack_id}: skipping invalid nav pattern: {pattern_str}")
                    continue
            action = cmd.get("action", "navigate")
            target = cmd.get("target", "")
            meta = cmd.get("meta", {})
            self._compiled_nav[compiled] = (action, target, meta)

        return self._compiled_nav

    @property
    def features(self) -> dict:
        return dict(self._manifest.get("features", {}))

    @property
    def settings_defaults(self) -> dict:
        return dict(self._manifest.get("settings_defaults", {}))

    @property
    def alerts_config(self) -> dict:
        """Alert configuration from pack manifest (rules, recipients, quiet hours)."""
        return dict(self._manifest.get("alerts", {}))

    @property
    def library_config(self) -> dict:
        """Library metadata from pack manifest."""
        return dict(self._manifest.get("library", {}))

    @property
    def delivery_config(self) -> dict:
        """Delivery configuration from pack manifest (Fibonacci Plume Node 4)."""
        return dict(self._manifest.get("delivery", {}))

    @property
    def pipeline_config(self) -> dict:
        """Pipeline configuration from pack manifest (Fibonacci Plume Node 5)."""
        return dict(self._manifest.get("pipeline", {}))

    @property
    def knowledge_config(self) -> dict:
        """Knowledge bridge configuration from pack manifest (Fibonacci Plume Node 7)."""
        return dict(self._manifest.get("knowledge", {}))

    @property
    def battle_config(self) -> dict:
        """Battle protocol config from pack manifest (Fibonacci Plume Node 8)."""
        return dict(self._manifest.get("battle", {}))

    @property
    def schedule_config(self) -> dict:
        """Schedule configuration from pack manifest (Fibonacci Plume Node 11)."""
        return dict(self._manifest.get("schedule", {}))

    @property
    def manifest(self) -> dict:
        """Full manifest dict (read-only copy)."""
        return dict(self._manifest)

    # ─── Helpers ─────────────────────────────────────────────

    def has_feature(self, feature_name: str) -> bool:
        """Check if a feature is enabled in this pack."""
        return self.features.get(feature_name, False)

    def get_cartridge_names(self) -> list[str]:
        """Return ordered list of cartridge display names."""
        carts = sorted(
            [(k, v) for k, v in self._manifest.get("cartridges", {}).items()
             if not v.get("passive")],
            key=lambda kv: kv[1].get("number", 999),
        )
        return [c[1]["name"] for c in carts]

    def get_menu_text(self) -> str:
        """Generate the cartridge menu text for session commands."""
        names = self.get_cartridge_names()
        return " | ".join(names)

    def get_pack_rail(self, rail_id: str) -> dict | None:
        """Look up a pack-level data_rail tab by ID."""
        tabs = self._manifest.get("data_rail", {}).get("tabs", [])
        for tab in tabs:
            if tab.get("id") == rail_id and tab.get("type") == "pack":
                return tab
        return None

    def get_all_pack_rails(self) -> dict[str, dict]:
        """All pack-level rails (type=pack tabs) keyed by tab ID."""
        tabs = self._manifest.get("data_rail", {}).get("tabs", [])
        return {t["id"]: t for t in tabs if t.get("type") == "pack" and t.get("fields")}

    def get_rail_schema(self, cartridge_id: str, rail_id: str | None = None) -> dict | None:
        """
        Get the rail schema for a cartridge.

        Args:
            cartridge_id: The cartridge key.
            rail_id: Rail name, or None / "default" for the singular data_rail.

        Returns:
            Rail definition dict with trigger, fields[], or None if not found.
        """
        cart = self._manifest.get("cartridges", {}).get(cartridge_id)
        if not cart:
            return None
        if rail_id is None or rail_id == "default":
            return cart.get("data_rail")
        return cart.get("data_rails", {}).get(rail_id)

    def get_all_rails(self, cartridge_id: str) -> dict:
        """
        Get all rail definitions for a cartridge.

        Returns:
            Dict of rail_id -> rail_def. "default" key for singular data_rail.
            Empty dict if no rails defined.
        """
        cart = self._manifest.get("cartridges", {}).get(cartridge_id)
        if not cart:
            return {}
        rails = {}
        if "data_rail" in cart:
            rails["default"] = cart["data_rail"]
        if "data_rails" in cart:
            rails.update(cart["data_rails"])
        return rails

    def get_cartridge_rail_trigger(self, cartridge_id: str) -> str | None:
        """
        Get the trigger mode for a cartridge's default rail.

        Returns:
            "auto", "signal", or "manual". None if no rail defined.
        """
        rail = self.get_rail_schema(cartridge_id)
        if rail is None:
            return None
        return rail.get("trigger", "signal")

    @property
    def access(self) -> str:
        """Access tier: 'guest', 'authed', 'paid', or 'system'."""
        return self._manifest.get("access", "paid")

    @property
    def tier_gate(self) -> str | None:
        """Required subscription tier for paid packs (e.g. 'S1', 'V7')."""
        return self._manifest.get("tier_gate")

    @property
    def enabled(self) -> bool:
        """Whether this pack is enabled. Disabled packs cannot be loaded for sessions."""
        return self._manifest.get("enabled", True)

    @property
    def visibility(self) -> str:
        """Pack visibility: 'user' (default, shows in Browse Packs) or 'internal' (hidden)."""
        return self._manifest.get("visibility", "user")

    def to_public_info(self) -> dict:
        """Return public metadata suitable for API responses."""
        return {
            "pack_id": self.pack_id,
            "name": self.name,
            "access": self.access,
            **({"tier_gate": self.tier_gate} if self.tier_gate else {}),
            **({"enabled": False} if not self.enabled else {}),
            "version": self.version,
            "icon": self.icon,
            "category": self.category,
            "description": self.description,
            "tagline": self.tagline,
            "philosophy": self.philosophy,
            "personality_summary": self.personality.get("tone", ""),
            "identity_name": self.personality.get("identity_name", self.name),
            "visibility": self.visibility,
            "theme": self.theme,
            "cartridge_count": len(self._manifest.get("cartridges", {})),
            "cartridges": [
                {
                    "key": k, "name": v["name"], "description": v.get("description", ""),
                    **({"passive": True} if v.get("passive") else {}),
                }
                for k, v in sorted(
                    self._manifest.get("cartridges", {}).items(),
                    key=lambda kv: kv[1].get("number", 999),
                )
            ],
            "features": self.features,
            "data_rail": self._manifest.get("data_rail"),
            "library": self.library_config,
            "schedule": self.schedule_config,
        }


# ─── Tier System ─────────────────────────────────────────
TIER_ORDER = ["S1", "V7", "T13"]

# Map profiles.tier → manifest tier_gate names
TIER_NAME_MAP = {
    "starter": "S1",
    "pro": "V7",
    "enterprise": "T13",
    "custom": "T13",
}


def tier_meets_minimum(user_tier: str, required_tier: str) -> bool:
    """Check if user's mapped tier meets or exceeds the required tier."""
    mapped = TIER_NAME_MAP.get(user_tier)
    if not mapped:
        return False
    if required_tier not in TIER_ORDER:
        return False
    return TIER_ORDER.index(mapped) >= TIER_ORDER.index(required_tier)


def get_available_packs(
    user_tier: str | None = None,
    authenticated: bool = False,
    user_role: str | None = None,
) -> list[dict]:
    """Return pack info dicts available to this user based on auth, tier, and role."""
    from auth import role_at_least
    is_privileged = bool(user_role and role_at_least(user_role, "admin"))

    results = []
    for manifest_dir in sorted(PACKS_DIR.iterdir()):
        manifest_path = manifest_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            loader = PackLoader(manifest_dir.name)
        except Exception:
            continue
        if not loader.enabled:
            continue
        if loader.visibility == "internal":
            continue
        access = loader.access
        if access == "system":
            continue
        if access == "guest":
            results.append(loader.to_public_info())
        elif access == "authed":
            # Always include in catalog for browsing — access gating
            # happens at session creation via check_tier_access().
            info = loader.to_public_info()
            info["locked"] = not authenticated
            results.append(info)
        elif access == "paid":
            info = loader.to_public_info()
            pack_tier_gate = loader.tier_gate or "S1"
            if is_privileged or (user_tier and tier_meets_minimum(user_tier, pack_tier_gate)):
                info["locked"] = False
            else:
                info["locked"] = True
                info["tier_required"] = pack_tier_gate
            results.append(info)
    return results


# ─── Module-Level Helpers ─────────────────────────────────

def list_available_packs(include_all: bool = False) -> list[str]:
    """
    Scan packs/ and library/ directories and return valid pack IDs.

    By default, filters out template packs (base_*) and legacy packs
    (enterprise). Pass include_all=True to return everything.
    """
    packs = []
    seen = set()

    # 1. Scan protocols/packs/ (deployed packs — take priority)
    if PACKS_DIR.exists():
        for path in sorted(PACKS_DIR.iterdir()):
            if path.is_dir() and (path / "manifest.json").exists():
                if include_all or _is_deployable(path.name):
                    packs.append(path.name)
                    seen.add(path.name)

    # 2. Scan protocols/library/{category}/{pack_id}/
    if LIBRARY_DIR.exists():
        for cat_dir in sorted(LIBRARY_DIR.iterdir()):
            if not cat_dir.is_dir():
                continue
            for pack_dir in sorted(cat_dir.iterdir()):
                if pack_dir.is_dir() and (pack_dir / "manifest.json").exists():
                    pack_id = pack_dir.name
                    if pack_id not in seen:
                        if include_all or _is_deployable(pack_id):
                            packs.append(pack_id)
                            seen.add(pack_id)

    return packs


def _find_manifest_path(pack_id: str) -> Path | None:
    """Find manifest.json for a pack across packs/ and library/ directories."""
    # 1. Check packs/ (deployed — priority)
    p = PACKS_DIR / pack_id / "manifest.json"
    if p.exists():
        return p
    # 2. Check library/{category}/{pack_id}/
    if LIBRARY_DIR.exists():
        for cat_dir in LIBRARY_DIR.iterdir():
            if not cat_dir.is_dir():
                continue
            lib_path = cat_dir / pack_id / "manifest.json"
            if lib_path.exists():
                return lib_path
    return None


def load_pack_info(pack_id: str) -> dict:
    """Load public info for a specific pack without full validation."""
    manifest_path = _find_manifest_path(pack_id)
    if not manifest_path:
        return {"pack_id": pack_id, "error": "manifest not found"}
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            m = json.load(f)

        # Reject packs with unresolved template variables
        if _has_template_vars(m):
            return {"pack_id": pack_id, "error": "unresolved template variables"}

        # Normalize cartridge count for both array and dict formats
        carts = m.get("cartridges", [])
        cart_count = len(carts)

        # Extract cartridge list for both formats
        cart_list = []
        if isinstance(carts, list):
            for i, c in enumerate(carts):
                entry = {
                    "key": c.get("id", f"cart_{i}"),
                    "name": c.get("name", ""),
                    "description": c.get("description", ""),
                }
                if c.get("passive"):
                    entry["passive"] = True
                cart_list.append(entry)
        elif isinstance(carts, dict):
            for k, v in sorted(carts.items(), key=lambda kv: kv[1].get("number", 999)):
                entry = {
                    "key": k,
                    "name": v.get("name", ""),
                    "description": v.get("description", ""),
                }
                if v.get("passive"):
                    entry["passive"] = True
                cart_list.append(entry)

        return {
            "pack_id": pack_id,  # always use directory name
            "name": m.get("name", pack_id),
            "access": m.get("access", "paid"),
            **({"tier_gate": m["tier_gate"]} if "tier_gate" in m else {}),
            **({"enabled": False} if not m.get("enabled", True) else {}),
            "version": m.get("version", "0.0"),
            "icon": m.get("icon", ""),
            "category": m.get("category", ""),
            "description": m.get("description", ""),
            "tagline": m.get("tagline", ""),
            "visibility": m.get("visibility", "user"),
            "theme": m.get("theme", {}),
            "cartridge_count": cart_count,
            "cartridges": cart_list,
            "personality_summary": m.get("personality", {}).get("tone", ""),
            "data_rail": m.get("data_rail"),
            "library": m.get("library", {}),
        }
    except Exception as e:
        return {"pack_id": pack_id, "error": str(e)}


# ─── User Pack Infrastructure ─────────────────────────────
#
# Enables user-created packs stored in Supabase (DB + Storage)
# to be loaded alongside filesystem-based repo packs.
# The output format is identical to PackLoader.to_public_info().

_supabase_client = None
_storage_client = None


def init_user_pack_support(supabase_client, storage_client):
    """Called during app startup to enable user pack loading."""
    global _supabase_client, _storage_client
    _supabase_client = supabase_client
    _storage_client = storage_client
    if supabase_client:
        logger.info("User pack support initialized (Supabase)")
    else:
        logger.debug("User pack support: no Supabase client — user packs disabled")


async def load_user_pack(pack_id: str, user_id: str) -> Optional[dict]:
    """
    Load a user pack from Supabase.

    Returns a dict with manifest and protocol_files matching the structure
    consumed by the assembler, or None if not found.
    """
    if not _supabase_client:
        return None

    try:
        result = (
            _supabase_client.table("user_packs")
            .select("*")
            .eq("owner_id", user_id)
            .eq("pack_id", pack_id)
            .eq("status", "active")
            .maybe_single()
            .execute()
        )

        if not result.data:
            return None

        row = result.data
        manifest = row["manifest"]
        storage_prefix = row["storage_prefix"]
        assembly_mode = row.get("assembly_mode", "assembled")

        # Load protocol files from Supabase Storage
        protocol_files: dict[str, str] = {}

        if assembly_mode == "monolithic":
            compiled_file = manifest.get("protocol_file", "compiled.md")
            try:
                content = await _storage_client.download_user_pack_file(
                    storage_prefix, compiled_file
                )
                protocol_files[compiled_file] = content
            except Exception as e:
                logger.warning(f"User pack {pack_id}: failed to load {compiled_file}: {e}")
        else:
            # Assembled: master + cartridges + system screens
            master_file = manifest.get("master", "master.md")
            try:
                protocol_files[master_file] = await _storage_client.download_user_pack_file(
                    storage_prefix, master_file
                )
            except Exception:
                logger.warning(f"User pack {pack_id}: master.md not found")

            # Cartridges
            cartridges = manifest.get("cartridges", {})
            if isinstance(cartridges, dict):
                cartridge_list = cartridges.values()
            elif isinstance(cartridges, list):
                cartridge_list = cartridges
            else:
                cartridge_list = []

            for cart in cartridge_list:
                filename = cart.get("file") or cart.get("protocol")
                if filename:
                    try:
                        protocol_files[filename] = await _storage_client.download_user_pack_file(
                            storage_prefix, filename
                        )
                    except Exception as e:
                        logger.warning(f"User pack {pack_id}: failed to load {filename}: {e}")

            # System screens (boot, shutdown, etc.)
            system_screens = manifest.get("system_screens", {})
            for screen_name, screen_val in system_screens.items():
                screen_file = screen_val.get("file", "") if isinstance(screen_val, dict) else screen_val
                if screen_file and screen_file not in protocol_files:
                    try:
                        protocol_files[screen_file] = await _storage_client.download_user_pack_file(
                            storage_prefix, screen_file
                        )
                    except Exception:
                        pass  # System screens are optional

        return {
            "manifest": manifest,
            "protocol_files": protocol_files,
            "source": "user",
            "owner_id": user_id,
            "storage_prefix": storage_prefix,
        }

    except Exception as e:
        logger.error(f"Failed to load user pack {pack_id} for {user_id}: {e}")
        return None


async def list_user_packs(user_id: str, status: Optional[str] = None) -> list[dict]:
    """List all packs for a user, optionally filtered by status."""
    if not _supabase_client:
        return []

    try:
        query = (
            _supabase_client.table("user_packs")
            .select(
                "id, pack_id, name, version, description, category, icon, tagline, "
                "status, deployed_as, assembly_mode, created_at, updated_at, published_at"
            )
            .eq("owner_id", user_id)
        )

        if status:
            query = query.eq("status", status)

        result = query.order("updated_at", desc=True).execute()
        return result.data or []

    except Exception as e:
        logger.error(f"Failed to list user packs for {user_id}: {e}")
        return []


async def resolve_pack(pack_id: str, user_id: str = None):
    """
    Resolve a pack by ID. Checks repo packs, library packs, then user packs.

    Returns a PackLoader for repo packs or a dict for user packs,
    or None if not found.
    """
    # 1. Check repo packs (filesystem) — fast path
    pack_dir = PACKS_DIR / pack_id
    if pack_dir.exists() and (pack_dir / "manifest.json").exists():
        try:
            return PackLoader(pack_id)
        except PackValidationError:
            pass  # Fall through

    # 2. Check library packs (protocols/library/{category}/{pack_id}/)
    if LIBRARY_DIR.exists():
        for cat_dir in LIBRARY_DIR.iterdir():
            if not cat_dir.is_dir():
                continue
            lib_pack_dir = cat_dir / pack_id
            if lib_pack_dir.is_dir() and (lib_pack_dir / "manifest.json").exists():
                info = load_pack_info(pack_id)
                if "error" not in info:
                    return info

    # 3. Check user packs (Supabase) — requires user_id
    if user_id:
        user_pack = await load_user_pack(pack_id, user_id)
        if user_pack:
            return user_pack

    return None
