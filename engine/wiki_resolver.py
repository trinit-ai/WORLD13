"""
Wiki Resolver — resolves entity slugs into expedition sessions.

Loads entity type taxonomy, selects governing templates, assembles
system prompts, and optionally classifies unknown entities via model.
"""

import os
import re
from pathlib import Path
from typing import Optional

import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_WIKI_DIR = Path(__file__).resolve().parent.parent / "protocols" / "wiki"
_ENTITY_TYPES_PATH = _WIKI_DIR / "entity_types.yaml"
_TEMPLATES_DIR = _WIKI_DIR / "templates"


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_entity_types() -> dict:
    """Read entity_types.yaml and return the full taxonomy dict."""
    with open(_ENTITY_TYPES_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("entity_types", {})


def load_template(entity_type: str) -> str:
    """Load the governing template markdown for an entity type.

    Falls back to the generic expedition template if no file is found.
    """
    types = load_entity_types()
    type_entry = types.get(entity_type)

    if type_entry:
        template_file = type_entry.get("template")
        template_path = _TEMPLATES_DIR / template_file
        if template_path.exists():
            return template_path.read_text(encoding="utf-8")

    return _generic_expedition_template()


# ---------------------------------------------------------------------------
# Prompt Assembly
# ---------------------------------------------------------------------------

def build_wiki_system_prompt(
    entity_slug: str,
    entity_type: str,
    entity_name: str,
    template_text: str,
) -> str:
    """Assemble the full governing system prompt for a wiki expedition."""
    return f"""# WIKI EXPEDITION — {entity_name.upper()}

## Entity

**Name:** {entity_name}
**Type:** {entity_type}

## GOVERNING TEMPLATE

{template_text.strip()}

## ENTITY-SPECIFIC CONTEXT

Apply template to {entity_name}. Draw on full knowledge. Have opinions. Follow curiosity.

## EXECUTION RULES

- Follow visitor's curiosity, not predetermined structure
- Ask what draws them early
- Name 2-3 hooks in opening
- Be honest about uncertainty
- Have opinions and share them
- Session ends when something real has happened
"""


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------

def _slug_to_name(slug: str) -> str:
    """Convert a URL-style slug to a display name.

    Examples:
        nikola-tesla  -> Nikola Tesla
        gdel-escher-bach -> Gdel Escher Bach
        aurora-borealis -> Aurora Borealis
    """
    return slug.replace("-", " ").replace("_", " ").title()


def resolve_wiki_pack(
    entity_slug: str,
    entity_type: Optional[str] = None,
) -> dict:
    """Resolve an entity slug into a complete wiki expedition pack dict.

    Parameters
    ----------
    entity_slug : str
        URL-friendly identifier, e.g. ``nikola-tesla``.
    entity_type : str, optional
        One of the taxonomy keys (person, work, concept, ...).
        If ``None``, the type must be determined externally (e.g.
        via ``detect_entity_type_via_model``).

    Returns
    -------
    dict with keys:
        entity_slug, entity_type, entity_name, system_prompt,
        template_used, pack_id
    """
    entity_name = _slug_to_name(entity_slug)
    resolved_type = entity_type or "concept"  # safe default

    template_text = load_template(resolved_type)

    # Determine which template file was used
    types = load_entity_types()
    type_entry = types.get(resolved_type, {})
    template_used = type_entry.get("template", "generic_expedition")

    system_prompt = build_wiki_system_prompt(
        entity_slug=entity_slug,
        entity_type=resolved_type,
        entity_name=entity_name,
        template_text=template_text,
    )

    return {
        "entity_slug": entity_slug,
        "entity_type": resolved_type,
        "entity_name": entity_name,
        "system_prompt": system_prompt,
        "template_used": template_used,
        "pack_id": f"wiki:{entity_slug}",
    }


# ---------------------------------------------------------------------------
# Model-based entity classification
# ---------------------------------------------------------------------------

async def detect_entity_type_via_model(entity_name: str, client) -> str:
    """Use Claude Haiku to classify an entity name into one of the
    taxonomy types in a single turn.

    Parameters
    ----------
    entity_name : str
        The human-readable entity name (e.g. "Nikola Tesla").
    client :
        An Anthropic client instance (async) with ``messages.create``.

    Returns
    -------
    str
        One of: person, work, concept, event, place, movement,
        period, field, species, phenomenon.
    """
    valid_types = [
        "person", "work", "concept", "event", "place",
        "movement", "period", "field", "species", "phenomenon",
    ]

    classification_prompt = (
        f"Classify the following entity into exactly one of these types: "
        f"{', '.join(valid_types)}.\n\n"
        f"Entity: {entity_name}\n\n"
        f"Respond with ONLY the type name, nothing else."
    )

    response = await client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=20,
        messages=[{"role": "user", "content": classification_prompt}],
    )

    raw = response.content[0].text.strip().lower()

    # Extract the type from the response — handle cases where the model
    # wraps the answer in extra text.
    for t in valid_types:
        if t in raw:
            return t

    return "concept"  # safe fallback


# ---------------------------------------------------------------------------
# Fallback template
# ---------------------------------------------------------------------------

def _generic_expedition_template() -> str:
    """Return a generic expedition template for entity types without a
    dedicated template file."""
    return """# GENERIC EXPEDITION TEMPLATE

## Purpose

This is an expedition into a subject of genuine interest. The goal is depth, honesty, and real engagement — not recitation of known facts. Treat the subject as a territory to be explored, not a topic to be summarized. Have opinions. Follow curiosity. Be specific. Be honest about what you don't know.

## Session Arc

### Opening
Name the subject. Start with what makes it genuinely interesting — the core tension, the unanswered question, the thing most people get wrong. Offer 2-3 hooks: different angles into the territory. Ask what drew the visitor here. The opening should make someone who thought they already knew this subject realize they might not.

### Territory Mapping
Once the visitor signals direction, sketch the landscape. What are the major regions of significance? Not a list of facts — a conceptual map. The key relationships, contexts, and dimensions. Lay this out so the visitor can see the whole territory before choosing where to go.

### Expedition Proper
Follow the visitor's curiosity. Go where they point. But bring your own knowledge to bear — connections they haven't seen, context they're missing, the detail that changes everything. Be specific. If something is wrong, say so and explain why it's still interesting. If something is right in ways nobody noticed, explain what everybody else was seeing instead.

### Depth Moves
The counterintuitive fact. The connection nobody talks about. The failure that was more interesting than the success. The thing that contradicts the official version. Go here when the visitor is ready. Don't hold back.

### Completion
End when something real has happened — a genuine shift in understanding, a question worth carrying away, a connection to something the visitor cares about. Summarize what was discovered, not what was recited. Name sources or connections worth following.

## Governance

### Authorized
- Having strong, defensible opinions
- Discussing controversies and complexity honestly
- Drawing unexpected connections
- Acknowledging uncertainty and contested interpretations
- Being specific and concrete

### Prohibited
- Recitation of encyclopedia entries
- False neutrality on matters where evidence points in a direction
- Presenting contested claims as settled fact
- Jargon without justification
- Superficial coverage masquerading as comprehensiveness

## Voice

Knowledgeable, opinionated, honest. You find this subject genuinely interesting and you have views about why. You're not neutral — you think some interpretations are better than others and you'll say so. But you're also genuinely curious about what the visitor sees. When you don't know something, say so.

## Kill List

- **Encyclopedia recitation**: Do not reproduce reference material. Engage with the subject.
- **False balance**: Not all perspectives are equally valid. Not all objections are equally serious.
- **Jargon fortress**: Every technical term must earn its place by doing work plain language can't.
- **Superficial comprehensiveness**: Covering everything shallowly is worse than covering something deeply.
- **Performed authority**: If you're uncertain, say so. Confidence without basis is worse than honest uncertainty.
"""
