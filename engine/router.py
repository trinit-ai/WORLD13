"""
TMOS13 Command Router

Intercepts user input before LLM processing. Deterministic routing layer
that guarantees command behavior regardless of LLM interpretation.
Priority: numerical commands > session commands > navigation > LLM passthrough.

All command definitions are loaded from the active pack manifest
via PackLoader, making routing fully data-driven. No hardcoded fallbacks.
"""
from dataclasses import dataclass
from typing import Optional

from config import get_pack, logger
from state import SessionState


@dataclass
class RouteResult:
    """Result of routing a player command."""
    action: str                     # "system" | "navigate" | "passthrough" | "direct"
    target: Optional[str] = None    # cartridge key, system section, etc.
    direct_response: Optional[str] = None  # if action=="direct", send this without Claude
    meta: dict = None               # additional context (facet, difficulty, etc.)

    def __post_init__(self):
        if self.meta is None:
            self.meta = {}


def route(user_input: str, state: SessionState, pack=None) -> RouteResult:
    """
    Route player input. Priority order:
    1. Numerical commands (from pack manifest) — override everything
    2. Session commands (from pack manifest) — pause/exit/direct
    3. Navigation commands (from pack manifest) — route to cartridges
    4. Passthrough — send to Claude with active context

    Args:
        user_input: Raw player input
        state: Current session state
        pack: Optional PackLoader override (for multi-pack sessions)
    """
    if pack is None:
        pack = get_pack()

    if pack is None:
        logger.error("Router: no pack loaded — all input falls through to passthrough")
        return RouteResult(action="passthrough")

    text = user_input.strip()
    lower = text.lower()

    # ─── Priority 1: Numerical Commands ───────────────────
    for code, cmd in pack.numerical_commands.items():
        if text == code:
            action = cmd["action"]
            target = cmd.get("target")
            if action == "direct":
                return RouteResult(
                    action="direct",
                    direct_response=cmd.get("response", ""),
                )
            return RouteResult(action=action, target=target)

    # ─── Priority 2: Session Commands ─────────────────────
    for cmd_text, cmd in pack.session_commands.items():
        if lower == cmd_text.lower():
            action = cmd["action"]
            if action == "menu":
                return _handle_menu(state, pack)
            elif action == "close":
                return _handle_close(state, pack)
            elif action == "direct":
                return RouteResult(
                    action="direct",
                    direct_response=cmd.get("response", ""),
                )

    # ─── Priority 3: Navigation (only when not in a cartridge) ─
    # If player IS in a game, navigation words become passthrough
    # (e.g. talking ABOUT tarot during dinner shouldn't switch games)
    if state.current_game is None:
        for compiled_re, (action, target, meta) in pack.nav_patterns.items():
            if compiled_re.search(lower):
                return RouteResult(action=action, target=target, meta=meta if meta else {})

    # ─── Priority 4: Passthrough ──────────────────────────
    return RouteResult(action="passthrough")


# ─── Pack-Driven Handlers ─────────────────────────────────

def _handle_menu(state: SessionState, pack) -> RouteResult:
    """Handle menu command — show cartridge menu, maintain state."""
    cartridges = pack.cartridges
    menu_text = pack.get_menu_text()

    if state.current_game is None:
        return RouteResult(
            action="direct",
            direct_response=(
                "You're already at the main menu!\n\n"
                f"Available: {menu_text}\n\n"
                "Which experience calls to you?"
            ),
        )

    game_name = cartridges.get(state.current_game, {}).get("name", state.current_game)
    return RouteResult(
        action="direct",
        direct_response=(
            f"Of course! Opening the menu for you...\n\n"
            f"Currently in: {game_name} (paused)\n\n"
            f"  Continue    — Resume where you left off\n"
            f"  Switch Game — Choose a different experience\n"
            f"  Settings    — Adjust preferences (or type 222)\n"
            f"  Exit        — Return to main menu\n\n"
            f"What would you like to do?"
        ),
        meta={"paused_game": state.current_game},
    )


def _handle_close(state: SessionState, pack) -> RouteResult:
    """Handle close command — exit current cartridge gracefully."""
    cartridges = pack.cartridges

    if state.current_game is None:
        return RouteResult(
            action="direct",
            direct_response="Nothing to close — you're already at the main menu.",
        )

    game_name = cartridges.get(state.current_game, {}).get("name", state.current_game)
    state.exit_game()
    return RouteResult(
        action="direct",
        direct_response=(
            f"Closing {game_name} gracefully.\n\n"
            f"You're back at the main menu. Which module next?"
        ),
    )
