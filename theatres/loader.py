"""
theatres/loader.py — Load theatre manifests into typed Python objects.
"""

import os
import yaml
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class TheatreAgent:
    name: str
    plane: int
    primary_arch: str
    secondary_arch: str
    tertiary_arch: str
    k0: float
    lambda_coeff: float
    cycle_phase: str
    karmic_phi: float
    backstory: str


@dataclass
class TheatreManifest:
    name: str
    version: str
    description: str
    author: str
    created: str
    # Protocol
    pack: str
    pack_password: Optional[str]
    session_mode: str
    sessions_per_agent: int
    max_tokens: int
    user_prompt_template: str
    # Population
    agents: List[TheatreAgent]
    # Context
    context_sampling: str
    fixed_axes: dict
    k_bias_scale: float
    # Simulation
    omega: float
    tick_interval_seconds: int
    output_mode: str
    # Output
    vault_prefix: str
    generate_report: bool
    report_format: str
    track_divergence: bool
    analysis: List[str]


def load_theatre(theatre_name: str) -> TheatreManifest:
    """
    Load a theatre manifest from theatres/{theatre_name}/manifest.yaml.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    manifest_path = os.path.join(base_dir, theatre_name, "manifest.yaml")

    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Theatre '{theatre_name}' not found at {manifest_path}")

    with open(manifest_path, "r") as f:
        raw = yaml.safe_load(f)

    if not raw:
        raise ValueError(f"Empty manifest: {manifest_path}")

    # Parse agents
    agents = []
    for a in raw.get("population", {}).get("agents", []):
        agents.append(TheatreAgent(
            name=a["name"],
            plane=a["plane"],
            primary_arch=a["primary_arch"],
            secondary_arch=a["secondary_arch"],
            tertiary_arch=a["tertiary_arch"],
            k0=float(a["k0"]),
            lambda_coeff=float(a["lambda_coeff"]),
            cycle_phase=a["cycle_phase"],
            karmic_phi=float(a["karmic_phi"]),
            backstory=a.get("backstory", "").strip(),
        ))

    proto = raw.get("protocol", {})
    ctx = raw.get("context", {})
    sim = raw.get("simulation", {})
    out = raw.get("output", {})

    return TheatreManifest(
        name=raw.get("name", theatre_name),
        version=raw.get("version", "0.1.0"),
        description=raw.get("description", ""),
        author=raw.get("author", ""),
        created=raw.get("created", ""),
        pack=proto.get("pack", ""),
        pack_password=proto.get("pack_password"),
        session_mode=proto.get("session_mode", "single"),
        sessions_per_agent=proto.get("sessions_per_agent", 1),
        max_tokens=proto.get("max_tokens", 1000),
        user_prompt_template=proto.get("user_prompt_template", ""),
        agents=agents,
        context_sampling=ctx.get("sampling", "tvr_weighted"),
        fixed_axes=ctx.get("fixed_axes", {}),
        k_bias_scale=float(ctx.get("k_bias_scale", 0.5)),
        omega=float(sim.get("omega", 0.015)),
        tick_interval_seconds=int(sim.get("tick_interval_seconds", 5)),
        output_mode=sim.get("output_mode", "full"),
        vault_prefix=out.get("vault_prefix", ""),
        generate_report=out.get("generate_report", True),
        report_format=out.get("report_format", "markdown"),
        track_divergence=out.get("track_divergence", False),
        analysis=out.get("analysis", []),
    )
