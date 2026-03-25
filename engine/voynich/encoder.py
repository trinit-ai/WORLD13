"""
engine/voynich/encoder.py

Converts session output and simulation state into a Voynich page.
No session content, agent names, K values, or protocol names ever appear
in the output. The encoder is a one-way function.
"""

import random
import hashlib
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from .alphabet import VoynichAlphabet, Glyph, SEMANTIC_CLUSTERS


@dataclass
class GlyphSequence:
    glyphs: List[str]
    has_space_before: bool
    indent_level: int


@dataclass
class Illustration:
    event_type: str
    svg_pattern: str
    position: str
    size: str


@dataclass
class VoynichPage:
    tick: int
    page_number: int
    sequences: List[GlyphSequence]
    illustrations: List[Illustration]
    density: float
    dominant_register: str
    instance_seed: str


ILLUSTRATION_PATTERNS = {
    "liberation": (
        '<circle cx="50" cy="50" r="5" fill="none" stroke="currentColor" stroke-width="1"/>'
        '<circle cx="50" cy="50" r="15" fill="none" stroke="currentColor" stroke-width="0.8" stroke-dasharray="3,2"/>'
        '<circle cx="50" cy="50" r="28" fill="none" stroke="currentColor" stroke-width="0.6" stroke-dasharray="2,3"/>'
        '<circle cx="50" cy="50" r="42" fill="none" stroke="currentColor" stroke-width="0.4" stroke-dasharray="1,4"/>'
        '<line x1="50" y1="8" x2="50" y2="92" stroke="currentColor" stroke-width="0.3" stroke-dasharray="1,5"/>'
        '<line x1="8" y1="50" x2="92" y2="50" stroke="currentColor" stroke-width="0.3" stroke-dasharray="1,5"/>'
    ),
    "intervention_window": (
        '<rect x="20" y="20" width="60" height="60" fill="none" stroke="currentColor" stroke-width="1.5"/>'
        '<rect x="28" y="28" width="44" height="44" fill="none" stroke="currentColor" stroke-width="0.8"/>'
        '<line x1="50" y1="20" x2="50" y2="10" stroke="currentColor" stroke-width="1"/>'
        '<line x1="44" y1="13" x2="50" y2="10" stroke="currentColor" stroke-width="1"/>'
        '<line x1="56" y1="13" x2="50" y2="10" stroke="currentColor" stroke-width="1"/>'
    ),
    "shadow_session": (
        '<path d="M20,80 L50,20 L80,80 Z" fill="none" stroke="currentColor" stroke-width="1"/>'
        '<path d="M30,80 L50,35 L70,80 Z" fill="none" stroke="currentColor" stroke-width="0.8"/>'
        '<path d="M40,80 L50,50 L60,80 Z" fill="none" stroke="currentColor" stroke-width="0.6"/>'
        '<line x1="20" y1="80" x2="80" y2="80" stroke="currentColor" stroke-width="0.5"/>'
    ),
    "contagion": (
        '<circle cx="50" cy="50" r="4" fill="currentColor" opacity="0.6"/>'
        '<line x1="50" y1="50" x2="30" y2="30" stroke="currentColor" stroke-width="0.8"/>'
        '<circle cx="30" cy="30" r="3" fill="none" stroke="currentColor" stroke-width="0.8"/>'
        '<line x1="50" y1="50" x2="70" y2="35" stroke="currentColor" stroke-width="0.8"/>'
        '<circle cx="70" cy="35" r="3" fill="none" stroke="currentColor" stroke-width="0.8"/>'
        '<line x1="50" y1="50" x2="65" y2="70" stroke="currentColor" stroke-width="0.8"/>'
        '<circle cx="65" cy="70" r="3" fill="none" stroke="currentColor" stroke-width="0.8"/>'
        '<line x1="50" y1="50" x2="25" y2="65" stroke="currentColor" stroke-width="0.6"/>'
        '<circle cx="25" cy="65" r="2" fill="none" stroke="currentColor" stroke-width="0.6"/>'
    ),
    "crisis_phase": (
        '<path d="M10,50 Q20,10 30,50 Q40,90 50,50 Q60,10 70,50 Q80,90 90,50" '
        'fill="none" stroke="currentColor" stroke-width="1.2"/>'
        '<path d="M10,60 Q20,30 30,60 Q40,90 50,60 Q60,30 70,60 Q80,90 90,60" '
        'fill="none" stroke="currentColor" stroke-width="0.6" opacity="0.5"/>'
    ),
}


def classify_session(session_result: dict) -> List[str]:
    """Classify a session into semantic clusters. No raw content escapes."""
    clusters = []

    k_delta = session_result.get("k_delta", 0)
    coherence = session_result.get("coherence_after", session_result.get("coherence", 0.5))
    phase = session_result.get("cycle_phase", "ACC")
    plane = session_result.get("plane", 4)
    arch = session_result.get("primary_arch", "WIT")
    output = session_result.get("session_output", session_result.get("session_excerpt", ""))
    session_len = len(output)

    if k_delta > 0.1:
        clusters.append("accumulation")
    elif k_delta < -0.1:
        clusters.append("resolution")

    if phase == "CRS":
        clusters.append("crisis")
    elif phase in ("TRN", "LIB"):
        clusters.append("transition")

    if session_result.get("is_liberated"):
        clusters.append("liberation")
    if session_result.get("is_shadow_session"):
        clusters.append("shadow")
    if session_result.get("contagion_events"):
        clusters.append("contagion")
    if session_result.get("intervention_window"):
        clusters.append("window")

    if coherence > 0.7:
        clusters.append("coherence_high")
    elif coherence < 0.3:
        clusters.append("coherence_low")

    if plane <= 2:
        clusters.append("plane_material")
    elif plane <= 4:
        clusters.append("plane_psychic")
    else:
        clusters.append("plane_transpersonal")

    if arch in {"HLR", "TCH", "WIT", "MYS"}:
        clusters.append("archetype_light")
    elif arch in {"WAR", "JDG", "TRK"}:
        clusters.append("archetype_shadow")
    elif arch in {"SKR", "LVR", "TRN"}:
        clusters.append("archetype_seeker")

    if session_len < 200:
        clusters.append("session_short")
    elif session_len > 400:
        clusters.append("session_long")

    return list(set(clusters))


def encode_session(
    session_result: dict,
    alphabet: VoynichAlphabet,
    page_number: int,
    tick: int,
    tick_shadow_count: int = 0,
) -> VoynichPage:
    """Convert a session result into a VoynichPage. No session content escapes."""
    session_id = session_result.get("vault_record_id", f"{tick}_{page_number}")
    page_seed = int(hashlib.sha256(
        f"{alphabet.instance_seed}:{session_id}".encode()
    ).hexdigest()[:16], 16)
    rng = random.Random(page_seed)

    clusters = classify_session(session_result)

    if tick_shadow_count >= 2:
        clusters.append("tick_active")
    else:
        clusters.append("tick_quiet")

    # Dominant register
    if "liberation" in clusters:
        register = "liberation"
    elif "shadow" in clusters or "accumulation" in clusters:
        register = "shadow"
    elif "transition" in clusters or "resolution" in clusters:
        register = "transition"
    else:
        register = "light"

    # Density
    density_ranges = {
        "shadow": (0.7, 1.0),
        "liberation": (0.3, 0.6),
        "transition": (0.5, 0.8),
        "light": (0.4, 0.8),
    }
    lo, hi = density_ranges.get(register, (0.4, 0.8))
    density = rng.uniform(lo, hi)

    # Build glyph sequences
    n_lines = int(density * 12) + rng.randint(2, 4)
    sequences = []
    min_line, max_line = alphabet.line_length_range
    glyph_map = {g.id: g for g in alphabet.glyphs}

    for _ in range(n_lines):
        line_clusters = rng.choices(clusters, k=rng.randint(1, 3)) if clusters else ["tick_quiet"]
        line_glyphs = []
        n_glyphs = rng.randint(min_line, max_line)

        for _ in range(n_glyphs):
            cluster = rng.choice(line_clusters)
            available = alphabet.cluster_to_glyphs.get(cluster, [])
            if not available:
                available = [g.id for g in alphabet.glyphs]

            weights = [glyph_map[gid].frequency_weight if gid in glyph_map else 0.1 for gid in available]
            chosen_id = rng.choices(available, weights=weights, k=1)[0]
            line_glyphs.append(chosen_id)

            if rng.random() < alphabet.space_probability:
                line_glyphs.append("SPACE")

        sequences.append(GlyphSequence(
            glyphs=line_glyphs,
            has_space_before=rng.random() < 0.3,
            indent_level=rng.choices([0, 1, 2], weights=[0.7, 0.2, 0.1])[0],
        ))

    # Illustrations
    illustrations = []
    event_map = {
        "liberation": "liberation",
        "window": "intervention_window",
        "shadow": "shadow_session",
        "contagion": "contagion",
        "crisis": "crisis_phase",
    }

    for cluster, event_type in event_map.items():
        if cluster in clusters and rng.random() < 0.7:
            positions = ["margin_left", "margin_right", "footer", "center"]
            sizes = ["small", "medium", "large"]
            size_w = [0.1, 0.4, 0.5] if event_type == "liberation" else [0.5, 0.35, 0.15]

            illustrations.append(Illustration(
                event_type=event_type,
                svg_pattern=ILLUSTRATION_PATTERNS.get(event_type, ""),
                position=rng.choice(positions),
                size=rng.choices(sizes, weights=size_w)[0],
            ))

    return VoynichPage(
        tick=tick,
        page_number=page_number,
        sequences=sequences,
        illustrations=illustrations,
        density=round(density, 2),
        dominant_register=register,
        instance_seed=alphabet.instance_seed,
    )
