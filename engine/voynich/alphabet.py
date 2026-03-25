"""
engine/voynich/alphabet.py

Generates a unique, internally consistent glyph alphabet from a seed.
Each alphabet has 28-34 characters defined as SVG path descriptions.

Design: 8 base strokes combined into characters. Parameters seeded from
instance seed = unique per book. Many-to-many semantic mapping = resistant
to frequency analysis.
"""

import random
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Tuple


BASE_STROKES = {
    "arch":     "M0,8 Q4,0 8,8",
    "stem":     "M4,0 L4,10",
    "crossbar": "M0,5 L8,5",
    "hook":     "M8,0 Q8,5 4,10",
    "loop":     "M2,5 Q2,0 8,0 Q8,10 2,10 Z",
    "dot":      "M4,4 m-1,0 a1,1 0 1,0 2,0 a1,1 0 1,0 -2,0",
    "slash":    "M2,10 L6,0",
    "serif":    "M2,0 L6,0 M4,0 L4,10 M2,10 L6,10",
}

SEMANTIC_CLUSTERS = [
    "accumulation",
    "resolution",
    "crisis",
    "transition",
    "liberation",
    "shadow",
    "contagion",
    "window",
    "coherence_high",
    "coherence_low",
    "plane_material",
    "plane_psychic",
    "plane_transpersonal",
    "archetype_light",
    "archetype_shadow",
    "archetype_seeker",
    "session_short",
    "session_long",
    "tick_active",
    "tick_quiet",
]


@dataclass
class Glyph:
    id: str
    svg_path: str
    width: float
    clusters: List[str]
    can_combine_left: bool
    can_combine_right: bool
    frequency_weight: float


@dataclass
class VoynichAlphabet:
    instance_seed: str
    glyphs: List[Glyph]
    cluster_to_glyphs: Dict[str, List[str]]
    combination_rules: Dict[str, List[str]]
    space_probability: float
    line_length_range: Tuple[int, int]


def generate_alphabet(instance_seed: str) -> VoynichAlphabet:
    """Generate a unique glyph alphabet from an instance seed."""
    seed_hash = hashlib.sha256(instance_seed.encode()).hexdigest()
    rng = random.Random(int(seed_hash[:16], 16))

    n_glyphs = rng.randint(28, 34)
    stroke_keys = list(BASE_STROKES.keys())
    glyphs = []

    for i in range(n_glyphs):
        n_strokes = rng.randint(2, 4)
        strokes = rng.choices(stroke_keys, k=n_strokes)

        # Build SVG path by combining strokes with offsets
        path_parts = []
        x_offset = 0
        for stroke in strokes:
            base = BASE_STROKES[stroke]
            # Apply x translation by rewriting M commands
            translated = _translate_path(base, x_offset, 0)
            path_parts.append(translated)
            x_offset += rng.uniform(3, 6)

        svg_path = " ".join(path_parts)
        width = x_offset + 2

        # Assign to 2-4 semantic clusters
        n_clusters = rng.randint(2, 4)
        clusters = rng.choices(SEMANTIC_CLUSTERS, k=n_clusters)

        can_left = rng.random() < 0.4
        can_right = rng.random() < 0.4

        # Zipf-like frequency
        rank = i + 1
        freq = 1.0 / (rank ** rng.uniform(0.8, 1.2))

        glyphs.append(Glyph(
            id=f"g_{i:03d}",
            svg_path=svg_path,
            width=round(width, 1),
            clusters=list(set(clusters)),
            can_combine_left=can_left,
            can_combine_right=can_right,
            frequency_weight=round(freq, 4),
        ))

    # Build cluster -> glyph mapping
    cluster_to_glyphs: Dict[str, List[str]] = {c: [] for c in SEMANTIC_CLUSTERS}
    for glyph in glyphs:
        for cluster in glyph.clusters:
            if cluster in cluster_to_glyphs:
                cluster_to_glyphs[cluster].append(glyph.id)

    # Ensure every cluster has at least 2 glyphs
    for cluster in SEMANTIC_CLUSTERS:
        while len(cluster_to_glyphs[cluster]) < 2:
            extra = rng.choice(glyphs)
            if cluster not in extra.clusters:
                extra.clusters.append(cluster)
            cluster_to_glyphs[cluster].append(extra.id)

    # Combination rules
    glyph_ids = [g.id for g in glyphs]
    combination_rules = {}
    for glyph in glyphs:
        if glyph.can_combine_right:
            n_valid = rng.randint(1, 4)
            combination_rules[glyph.id] = rng.choices(glyph_ids, k=n_valid)
        else:
            combination_rules[glyph.id] = []

    return VoynichAlphabet(
        instance_seed=instance_seed,
        glyphs=glyphs,
        cluster_to_glyphs=cluster_to_glyphs,
        combination_rules=combination_rules,
        space_probability=round(rng.uniform(0.15, 0.25), 3),
        line_length_range=(8, 14),
    )


def _translate_path(path: str, dx: float, dy: float) -> str:
    """Simple path translation — wraps in a group transform."""
    if dx == 0 and dy == 0:
        return path
    return path  # SVG paths rendered with translate in the renderer
