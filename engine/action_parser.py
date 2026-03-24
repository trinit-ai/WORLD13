"""
Action token parser.

Scans LLM output for action tokens (→ [label](target)),
strips them from the message body, and returns them as
structured action objects on the response payload.

Action types:
  → [Label](datarail:name)   → type: "datarail"  (in-session, no navigation)
  → [Label](/packs/...)       → type: "navigate"  (in-app, same tab)
  → [Label](/{pack-slug})    → type: "navigate"  (pack demo, same tab)
  → [Label](/product)        → type: "site"      (site page, new tab)
  → [Label](https://...)     → type: "external"  (external link, new tab)
"""

import re
from dataclasses import dataclass

ACTION_PATTERN = re.compile(
    r"^\s*→\s*\[([^\]]+)\]\(([^)]+)\)\s*$",
    re.MULTILINE,
)

# Paths that stay in-app (same tab) — pack library and pack demos
_PACK_SLUGS = {
    "customer-support", "candidate-screener", "legal-intake", "lead-qualification",
    "clinical-decision", "classroom", "manda-negotiation", "real-estate",
    "business-case", "gaming", "rituals", "campaign-builder", "pack-builder",
    "feed-portal",
}


def _classify_path(target: str) -> str:
    """Classify an internal path as 'navigate' (in-app) or 'site' (new tab)."""
    if target == "/packs" or target.startswith("/packs/"):
        return "navigate"
    # /{slug} — check if it's a known pack slug
    slug = target.lstrip("/").split("/")[0] if target.startswith("/") else ""
    if slug in _PACK_SLUGS:
        return "navigate"
    # Everything else is a site page — open in new tab
    return "site"


@dataclass
class ResponseAction:
    type: str  # "navigate" | "datarail" | "external" | "site"
    target: str  # "/packs" | "datarail:contact" | "https://..." | "/product"
    label: str  # "See Pricing"

    def to_dict(self) -> dict:
        return {"type": self.type, "target": self.target, "label": self.label}


def parse_actions(text: str) -> tuple[str, list[ResponseAction]]:
    """
    Parse action tokens from LLM output.

    Returns:
        (cleaned_text, actions) — text with action lines removed,
        and a list of structured actions.

    If no action tokens found, returns original text and empty list.
    """
    actions: list[ResponseAction] = []

    for match in ACTION_PATTERN.finditer(text):
        label = match.group(1).strip()
        target = match.group(2).strip()

        if target.startswith("datarail:"):
            action_type = "datarail"
        elif target.startswith("http"):
            action_type = "external"
        else:
            action_type = _classify_path(target)

        actions.append(ResponseAction(type=action_type, target=target, label=label))

    if not actions:
        return text, []

    # Strip action lines from the message text
    cleaned = ACTION_PATTERN.sub("", text).strip()
    # Clean up any resulting triple+ newlines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned, actions
