"""
engine/mode.py
WORLD13 mode detection and routing.
WORLD13_MODE=pure (default) | WORLD13_MODE=shadow
"""

import os

PURE = "pure"
SHADOW = "shadow"


def get_mode() -> str:
    return os.environ.get("WORLD13_MODE", PURE).lower()


def is_shadow() -> bool:
    return get_mode() == SHADOW


def is_pure() -> bool:
    return get_mode() == PURE


WORLD = "world"


def is_world() -> bool:
    """World mode: autonomous persistent civilization. No research outputs."""
    return get_mode() == WORLD
