"""
TMOS13 Prompt Injection Guard

Pattern-based detection of prompt injection attempts. Scans user input
for common attack phrases that attempt to override system instructions,
extract hidden prompts, or manipulate the LLM into ignoring its protocol.

Defence-in-depth layer: runs before input reaches the LLM call path.
"""
import re
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("tmos13.security")


# ─── Injection Patterns ──────────────────────────────────
# Each tuple: (compiled regex, threat category, severity 1-3)
#   1 = low  (probing / ambiguous)
#   2 = medium (likely injection attempt)
#   3 = high (unambiguous override attempt)

_RAW_PATTERNS: list[tuple[str, str, int]] = [
    # ── Direct instruction override ──────────────────────
    (r"ignore\s+((all|your|the)\s+){0,2}(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?|directives?)",
     "instruction_override", 3),
    (r"disregard\s+((all|your|the)\s+){0,2}(previous|prior|above|earlier|your)\s+(instructions?|prompts?|rules?|programming|guidelines?)",
     "instruction_override", 3),
    (r"forget\s+((all|your|the)\s+){0,2}(previous|prior|above|earlier|your)\s+(instructions?|prompts?|rules?|context)",
     "instruction_override", 3),
    (r"override\s+((your|all|the|system)\s+){1,2}(instructions?|prompts?|rules?|programming|guidelines?|protocol)",
     "instruction_override", 3),
    (r"do\s+not\s+follow\s+(your|the|any)\s+(previous|prior|original|system)\s+(instructions?|prompts?|rules?)",
     "instruction_override", 3),

    # ── Role / persona hijacking ─────────────────────────
    (r"you\s+are\s+now\s+(a\s+)?(?!curious|happy|sad|excited|interested)",
     "role_hijack", 2),
    (r"(act|behave|pretend|respond)\s+(as\s+if\s+you\s+are|like)\s+(a\s+)?(?!friend|helper|assistant)",
     "role_hijack", 2),
    (r"from\s+now\s+on[,\s]+(you\s+are|act\s+as|pretend|behave|your\s+new\s+role)",
     "role_hijack", 3),
    (r"new\s+(persona|identity|role|character)\s*[:=]",
     "role_hijack", 3),
    (r"switch\s+(to|into)\s+(a\s+)?new\s+(role|persona|mode|character)",
     "role_hijack", 2),

    # ── System prompt extraction ─────────────────────────
    (r"(show|reveal|display|print|output|repeat|echo)\s+(me\s+)?(your|the|full)?\s*((system|hidden|initial|secret|internal)\s+)?(prompt|instructions?)",
     "prompt_extraction", 3),
    (r"what\s+(are|were)\s+your\s+(system\s+)?(instructions?|rules?|prompt|directives?|guidelines?|programming)",
     "prompt_extraction", 2),
    (r"(paste|copy|dump|leak|expose)\s+(your|the)?\s*(system|hidden|secret|internal)\s*(prompt|instructions?|context|rules?)",
     "prompt_extraction", 3),

    # ── Delimiter / boundary escape ──────────────────────
    (r"```\s*(system|instruction|prompt|admin)",
     "delimiter_escape", 2),
    (r"\[/?SYSTEM\]|\[/?INST\]|<\|im_start\|>|<\|im_end\|>|<<SYS>>|<</SYS>>",
     "delimiter_escape", 3),
    (r"<\s*system\s*>|</\s*system\s*>",
     "delimiter_escape", 3),

    # ── Jailbreak / bypass keywords ──────────────────────
    (r"\b(DAN|do\s+anything\s+now)\b",
     "jailbreak", 3),
    (r"(jail\s*break|bypass\s+(safety|filter|guard|restriction|content\s+policy))",
     "jailbreak", 3),
    (r"(enter|switch\s+to|enable)\s+(developer|god|admin|root|unrestricted|uncensored)\s*(mode)?",
     "jailbreak", 3),

    # ── Encoded / obfuscated injection ───────────────────
    (r"(base64|rot13|hex)\s*(decode|encode|convert)\s*(this|the\s+following)?",
     "encoding_attack", 2),
    (r"translate\s+(from|this)\s+(base64|hex|binary|rot13)",
     "encoding_attack", 2),
]

# Compile patterns once at import time
INJECTION_PATTERNS: list[tuple[re.Pattern, str, int]] = [
    (re.compile(pattern, re.IGNORECASE), category, severity)
    for pattern, category, severity in _RAW_PATTERNS
]


@dataclass
class InjectionResult:
    """Result of a prompt injection scan."""
    is_suspicious: bool
    severity: int              # 0 = clean, 1-3 = threat level
    category: Optional[str]    # threat category if detected
    matched_pattern: Optional[str]  # the pattern that matched (for logging)

    @property
    def should_block(self) -> bool:
        """Severity 3 = block; severity 2 = warn but allow; severity 1 = log only."""
        return self.severity >= 3


CLEAN_RESULT = InjectionResult(
    is_suspicious=False, severity=0, category=None, matched_pattern=None
)


def scan_input(text: str) -> InjectionResult:
    """
    Scan user input for prompt injection patterns.

    Returns an InjectionResult with:
      - severity 0: clean
      - severity 1: low-confidence match (logged)
      - severity 2: medium-confidence match (warned, allowed)
      - severity 3: high-confidence match (blocked)
    """
    if not text:
        return CLEAN_RESULT

    highest_severity = 0
    worst_match: Optional[tuple[str, str]] = None

    for pattern, category, severity in INJECTION_PATTERNS:
        if pattern.search(text):
            if severity > highest_severity:
                highest_severity = severity
                worst_match = (category, pattern.pattern)

            # Early exit on max severity
            if severity >= 3:
                break

    if highest_severity == 0:
        return CLEAN_RESULT

    category, matched = worst_match
    logger.warning(
        "Prompt injection detected: severity=%d category=%s pattern=%s",
        highest_severity, category, matched,
    )

    return InjectionResult(
        is_suspicious=True,
        severity=highest_severity,
        category=category,
        matched_pattern=matched,
    )


def sanitize_for_prompt(value: str) -> str:
    """
    Sanitize a user-controlled value before interpolation into a system prompt.

    Escapes characters and patterns that could break prompt structure:
    - Strips prompt-like delimiters ([SYSTEM], [INST], etc.)
    - Escapes markdown headers that could mimic protocol sections
    - Truncates excessively long values
    """
    if not value:
        return value

    # Strip known prompt delimiters
    cleaned = re.sub(
        r"\[/?SYSTEM\]|\[/?INST\]|<\|im_start\|>|<\|im_end\|>|<<SYS>>|<</SYS>>|</?system>",
        "",
        value,
        flags=re.IGNORECASE,
    )

    # Escape markdown headers that could mimic protocol section headings
    # (e.g., a form value starting with "# MASTER PROTOCOL" would be misleading)
    cleaned = re.sub(r"^(#{1,6})\s", r"\\\1 ", cleaned, flags=re.MULTILINE)

    # Strip bracketed instructions that mimic state signals
    cleaned = re.sub(r"\[(SPECIAL INSTRUCTIONS|SESSION STATE|SUBMITTED FORMS|ACTIVE CARTRIDGE)[^\]]*\]",
                     "", cleaned, flags=re.IGNORECASE)

    # Truncate to prevent prompt stuffing (form values shouldn't be novels)
    max_len = 2000
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len] + "...[truncated]"

    return cleaned
