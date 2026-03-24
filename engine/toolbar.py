"""
TMOS13 Contextual Toolbar — Manifest-Driven Action Bar

Provides dynamic toolbar buttons based on cartridge context. Buttons
can trigger data rails, navigation, commands, or custom actions.

Toolbar config comes from two levels:
  1. Pack manifest `toolbar` section — pack-wide defaults
  2. Cartridge-level `toolbar` section — per-cartridge overrides

When a user enters a cartridge, the toolbar is resolved:
  cartridge.toolbar > pack.toolbar > empty toolbar

Action types:
  rail       — Trigger a data rail (opens secure form)
  navigate   — Navigate to another cartridge
  command    — Execute a session command (RESET, MENU, etc.)
  link       — Open an external URL
  custom     — Custom action dispatched to the client
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("tmos13.toolbar")


# ─── Data Types ─────────────────────────────────────────────

@dataclass
class ToolbarButtonDef:
    """A single toolbar button definition."""

    id: str
    label: str
    action_type: str  # rail | navigate | command | link | custom
    action_target: str
    icon: Optional[str] = None
    variant: str = "secondary"  # primary | secondary | ghost
    confirm: Optional[str] = None  # confirmation prompt before action
    disabled_until: Optional[str] = None  # condition to enable

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "label": self.label,
            "action_type": self.action_type,
            "action_target": self.action_target,
            "variant": self.variant,
        }
        if self.icon:
            d["icon"] = self.icon
        if self.confirm:
            d["confirm"] = self.confirm
        if self.disabled_until:
            d["disabled_until"] = self.disabled_until
        return d


@dataclass
class ToolbarConfig:
    """Toolbar configuration."""

    buttons: list[ToolbarButtonDef] = field(default_factory=list)
    position: str = "above_input"  # above_input | below_input
    visible_when: Optional[str] = None  # condition string

    def to_dict(self) -> dict:
        return {
            "buttons": [b.to_dict() for b in self.buttons],
            "position": self.position,
            "visible_when": self.visible_when,
        }


@dataclass
class ToolbarAction:
    """A dispatched toolbar action."""

    button_id: str
    action_type: str
    action_target: str
    session_id: str


VALID_ACTION_TYPES = {"rail", "navigate", "command", "link", "custom"}
VALID_VARIANTS = {"primary", "secondary", "ghost"}
VALID_POSITIONS = {"above_input", "below_input"}


# ─── Toolbar Resolver ──────────────────────────────────────

class ToolbarResolver:
    """
    Resolves toolbar config for a session based on pack manifest
    and current cartridge.
    """

    def __init__(self):
        self._stats = {
            "total_resolves": 0,
            "actions_dispatched": 0,
            "by_action_type": {},
        }

    def resolve(self, manifest: dict, cartridge_id: Optional[str] = None) -> ToolbarConfig:
        """
        Resolve toolbar config for the current context.

        Priority: cartridge-level toolbar > pack-level toolbar > empty.
        """
        self._stats["total_resolves"] += 1

        # Try cartridge-level toolbar first
        if cartridge_id:
            cartridges = manifest.get("cartridges", [])
            if isinstance(cartridges, list):
                for c in cartridges:
                    if c.get("id") == cartridge_id and "toolbar" in c:
                        return self._parse_config(c["toolbar"])
            elif isinstance(cartridges, dict):
                cart = cartridges.get(cartridge_id, {})
                if "toolbar" in cart:
                    return self._parse_config(cart["toolbar"])

        # Fall back to pack-level toolbar
        if "toolbar" in manifest:
            return self._parse_config(manifest["toolbar"])

        return ToolbarConfig()

    def validate_action(self, action: ToolbarAction, config: ToolbarConfig) -> bool:
        """Validate that a toolbar action is allowed by the current config."""
        for button in config.buttons:
            if button.id == action.button_id:
                if button.action_type == action.action_type:
                    self._stats["actions_dispatched"] += 1
                    self._stats["by_action_type"][action.action_type] = (
                        self._stats["by_action_type"].get(action.action_type, 0) + 1
                    )
                    return True
        return False

    def _parse_config(self, raw: dict) -> ToolbarConfig:
        """Parse a toolbar config dict into a ToolbarConfig."""
        buttons = []
        for b in raw.get("buttons", []):
            action_type = b.get("action_type", "custom")
            if action_type not in VALID_ACTION_TYPES:
                logger.warning("Invalid toolbar action_type: %s", action_type)
                continue

            variant = b.get("variant", "secondary")
            if variant not in VALID_VARIANTS:
                variant = "secondary"

            buttons.append(ToolbarButtonDef(
                id=b.get("id", ""),
                label=b.get("label", ""),
                action_type=action_type,
                action_target=b.get("action_target", ""),
                icon=b.get("icon"),
                variant=variant,
                confirm=b.get("confirm"),
                disabled_until=b.get("disabled_until"),
            ))

        position = raw.get("position", "above_input")
        if position not in VALID_POSITIONS:
            position = "above_input"

        return ToolbarConfig(
            buttons=buttons,
            position=position,
            visible_when=raw.get("visible_when"),
        )

    @property
    def stats(self) -> dict:
        return dict(self._stats)


def get_toolbar_config_from_manifest(
    manifest: dict,
    cartridge_id: Optional[str] = None,
) -> ToolbarConfig:
    """Convenience: resolve toolbar config from a manifest."""
    resolver = ToolbarResolver()
    return resolver.resolve(manifest, cartridge_id)


# Module-level singleton
_resolver = ToolbarResolver()


def get_toolbar_resolver() -> ToolbarResolver:
    """Get the singleton toolbar resolver."""
    return _resolver
