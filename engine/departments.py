"""
13TMOS Departments — Dynamic Pack Library Categories

Departments are derived from the live protocol library directory structure.
Each subdirectory in protocols/library/ is a department/category.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger("13tmos.departments")

ROOT_DIR = Path(__file__).resolve().parent.parent
LIBRARY_DIR = ROOT_DIR / "protocols" / "library"
PACKS_DIR = ROOT_DIR / "protocols" / "packs"

# Categories excluded from user-facing /dept menu (infrastructure, not browseable)
_HIDDEN_CATEGORIES = {
    "_meta", "_uncategorized", "system", "verticals",
    "scenarios", "simulator", "experiences", "marketing", "quantitative",
}

# Display name overrides for categories where title() isn't right
_DISPLAY_NAMES = {
    "hr": "Human Resources",
    "criminal_justice": "Criminal Justice",
    "mental_health": "Mental Health",
    "real_estate": "Real Estate",
    "social_work": "Social Work",
}


def _category_display_name(slug: str) -> str:
    """Convert a category slug to a display name."""
    if slug in _DISPLAY_NAMES:
        return _DISPLAY_NAMES[slug]
    return slug.replace("_", " ").title()


def list_department_names() -> list[tuple[str, str]]:
    """Return sorted list of (slug, display_name) for all browseable categories."""
    if not LIBRARY_DIR.exists():
        return []
    cats = []
    for cat_dir in sorted(LIBRARY_DIR.iterdir()):
        if not cat_dir.is_dir():
            continue
        slug = cat_dir.name
        if slug.startswith(".") or slug in _HIDDEN_CATEGORIES:
            continue
        # Only include categories that have at least one pack
        pack_count = sum(1 for p in cat_dir.iterdir() if p.is_dir())
        if pack_count > 0:
            cats.append((slug, _category_display_name(slug)))
    return cats


def get_department(slug: str) -> dict | None:
    """Return department info if the category exists in the library."""
    # Normalize input: spaces/hyphens → underscores
    slug = slug.lower().replace(" ", "_").replace("-", "_")
    cat_dir = LIBRARY_DIR / slug
    if not cat_dir.is_dir() or slug in _HIDDEN_CATEGORIES:
        return None
    # Count packs
    packs = [p.name for p in sorted(cat_dir.iterdir()) if p.is_dir()]
    if not packs:
        return None
    return {
        "name": _category_display_name(slug),
        "slug": slug,
        "packs": packs,
    }


def filter_packs(packs: list, department: str) -> list:
    """Filter (pack_id, name, desc) tuples to those in a department's category directory."""
    dept = get_department(department)
    if not dept:
        return packs
    allowed = set(dept.get("packs", []))
    return [(pid, name, desc) for pid, name, desc in packs if pid in allowed]


def load_departments() -> dict:
    """Return all departments as a dict (for backward compat). Dynamically derived."""
    return {slug: {"name": name} for slug, name in list_department_names()}
