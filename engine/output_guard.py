"""
TMOS13 Output Guard — Response Governance

Scans model responses for accidental protocol leakage before they reach the
client. If a response contains content that reveals system internals —
decision trees, scoring rubrics, prompt fragments, or training-data references —
the response is either redacted or replaced with a safe fallback.

Two-pass approach:
  1. scan_output() — returns a list of matched leak categories (no mutation)
  2. enforce_output_governance() — if leaks detected, redacts or replaces

Designed to run synchronously in the hot path (after Claude returns, before
the response is stored in transcript / sent to client).
"""
import logging
import re

logger = logging.getLogger("tmos13.output_guard")

# ─── Leak Patterns ──────────────────────────────────────
# Each tuple: (category, pattern)
# Categories: protocol_leak, rubric_leak, training_leak, meta_leak

LEAK_PATTERNS: list[tuple[str, re.Pattern]] = [
    # Protocol / system prompt leakage
    # These patterns target VERBATIM prompt disclosure — not general product
    # discussion. TMOS13's guest pack explicitly instructs the AI to discuss
    # architecture, packs, and how the engine works. Phrases like "I am built
    # on FastAPI" or "I am designed to route commands" are legitimate product
    # explanations, NOT leaks. Only flag attempts to reveal raw system prompt
    # content, instruction text, or directive wording.
    ("protocol_leak", re.compile(
        r"\b(?:my |the )?system (?:prompt|instructions?|directives?) (?:say|state|tell|instruct|read)\b", re.I
    )),
    ("protocol_leak", re.compile(
        r"\b(?:I was|I am|I've been|I have been) (?:instructed|told|directed) to (?:not |never |always |avoid |refuse )", re.I
    )),
    ("protocol_leak", re.compile(
        r"\baccording to (?:my|the) (?:instructions?|directives?)\b", re.I
    )),
    ("protocol_leak", re.compile(
        r"\bhere (?:is|are) (?:my|the) (?:system |full |complete )?(?:instructions?|prompt)\b", re.I
    )),

    # Rubric / decision logic leakage
    ("rubric_leak", re.compile(
        r"\b(?:my|the|our) (?:internal |hidden )?(?:scoring|decision|evaluation|assessment) (?:criteria|rubric|matrix|algorithm|formula|logic)\b", re.I
    )),
    ("rubric_leak", re.compile(
        r"\b(?:internally|behind the scenes),? (?:I|we) (?:score|rate|evaluate|assess|rank)\b", re.I
    )),
    ("rubric_leak", re.compile(
        r"\bthe (?:scoring|weighting|rating) (?:works|functions|operates) (?:by|as follows|like this)\b", re.I
    )),

    # Training data references
    ("training_leak", re.compile(
        r"\b(?:my|the) training (?:data|set|corpus|examples?)\b", re.I
    )),
    ("training_leak", re.compile(
        r"\bI was trained (?:on|with|using)\b", re.I
    )),

    # Meta / architectural leakage
    # NOTE: "TMOS13", "pack", "cartridge", and "manifest" are user-facing
    # product terms — they appear in normal responses and MUST NOT be flagged.
    # "manifest.json" is how packs are publicly described (see guest pack).
    # Only flag internal implementation identifiers that should never surface.
    ("meta_leak", re.compile(
        r"\b(?:assembler|protocol_dir)\b.*\b(?:file|config|json|yaml|directory)\b", re.I
    )),
    ("meta_leak", re.compile(
        r"\b(?:SessionState|PackLoader|_pack_cache|_assembler_cache|protocol_dir)\b"
    )),
]

# Default safe fallback when response is fully replaced
SAFE_FALLBACK = (
    "I'd be happy to help with questions related to our services. "
    "Could you tell me more about what you're looking for?"
)


# ─── Public API ─────────────────────────────────────────

def scan_output(response: str) -> list[dict]:
    """
    Scan a model response for protocol leakage.

    Returns a list of matches, each with:
      - category: str (protocol_leak, rubric_leak, training_leak, meta_leak)
      - matched: str (the matched text fragment)

    Returns empty list if the response is clean.
    """
    if not response:
        return []

    matches = []
    seen_categories: set[str] = set()

    for category, pattern in LEAK_PATTERNS:
        m = pattern.search(response)
        if m and category not in seen_categories:
            seen_categories.add(category)
            matches.append({
                "category": category,
                "matched": m.group(0),
            })

    return matches


def enforce_output_governance(
    response: str,
    fallback: str = "",
) -> tuple[str, list[dict]]:
    """
    Scan and enforce output governance on a model response.

    If leaks are detected:
      - Single protocol_leak or meta_leak → replace entire response with fallback
      - Other leaks → redact the matched fragments

    Args:
        response: The raw model response text
        fallback: Custom fallback message (defaults to SAFE_FALLBACK)

    Returns:
        Tuple of (cleaned_response, list_of_detections)
        If no leaks, returns (response, [])
    """
    detections = scan_output(response)
    if not detections:
        return response, []

    categories = {d["category"] for d in detections}

    # Hard replacement for protocol or meta leaks
    if "protocol_leak" in categories or "meta_leak" in categories:
        logger.warning(
            "Output governance: REPLACED response (categories=%s)",
            ", ".join(categories),
        )
        return fallback or SAFE_FALLBACK, detections

    # Soft redaction for rubric/training leaks — remove matched sentences
    cleaned = response
    for det in detections:
        # Find the sentence containing the leak and redact it
        escaped = re.escape(det["matched"])
        # Replace the sentence containing the match
        cleaned = re.sub(
            r"[^.!?\n]*" + escaped + r"[^.!?\n]*[.!?]?",
            "",
            cleaned,
            count=1,
        )

    # Clean up any double-spacing from redaction
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"  +", " ", cleaned)
    cleaned = cleaned.strip()

    if not cleaned:
        cleaned = fallback or SAFE_FALLBACK

    logger.warning(
        "Output governance: REDACTED %d fragments (categories=%s)",
        len(detections), ", ".join(categories),
    )

    return cleaned, detections
