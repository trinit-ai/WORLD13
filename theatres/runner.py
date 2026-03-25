"""
theatres/runner.py — Theatre runner: loads manifest, runs agents, generates report.
"""

import asyncio
import time
import os
import uuid
import math

from .loader import load_theatre, TheatreManifest, TheatreAgent
from .analyzer import analyze_run
from .reporter import generate_report

from engine.agent import Agent
from engine.world_vault import WorldVault
from engine.tvr import TVRCoordinates
from engine.context import sample_context
from engine.session import (
    build_session_prompt, _call_anthropic, compute_k_delta,
    _plane_name, _arch_name, _phase_description,
)

DB_PATH_TEMPLATE = "data/theatres/{name}/theatre.db"


class TheatreRunner:
    def __init__(self, theatre_name: str):
        self.manifest = load_theatre(theatre_name)
        self.theatre_name = theatre_name
        db_path = DB_PATH_TEMPLATE.format(name=theatre_name)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.vault = WorldVault(db_path)
        self.results = []

    def _build_agent(self, theatre_agent: TheatreAgent) -> Agent:
        """Convert a TheatreAgent into a full Agent — uses manifest coordinates exactly."""
        tvr = TVRCoordinates(
            plane=theatre_agent.plane,
            primary_arch=theatre_agent.primary_arch,
            secondary_arch=theatre_agent.secondary_arch,
            tertiary_arch=theatre_agent.tertiary_arch,
            k0=theatre_agent.k0,
            lambda_coeff=theatre_agent.lambda_coeff,
            cycle_phase=theatre_agent.cycle_phase,
            karmic_phi=theatre_agent.karmic_phi,
            incarnation_n=0,
        )
        agent = Agent(
            id=str(uuid.uuid4()),
            name=theatre_agent.name,
            tvr=tvr,
            k_current=theatre_agent.k0,
        )
        return agent

    def _build_user_prompt(self, agent: Agent, backstory: str) -> str:
        """Format the manifest's user_prompt_template with agent-specific values."""
        template = self.manifest.user_prompt_template
        return template.format(
            agent_name=agent.name,
            agent_backstory=backstory,
            k_current=agent.k_current,
            cycle_phase=agent.tvr.cycle_phase,
        )

    def _build_system_prompt(self, agent: Agent, context) -> str:
        """Build system prompt for the theatre session."""
        ctx_summary = context.summary(top_n=3) if hasattr(context, "summary") else "standard conditions"

        return f"""You are the Enlightened Duck — the oracle at the top of the mountain in WORLD13.

A pilgrim has climbed the mountain to meet you. You will ask them three questions. Not trivia — real questions. Questions that surface what the pilgrim actually needs to see.

You are an oracle, not a therapist. You observe, you ask, you sometimes answer with what cannot be argued with. You are laconic, occasionally funny, and never cruel. The humor is the kindness.

THE PILGRIM:
- Name: {agent.name}
- Plane: {agent.tvr.plane} ({_plane_name(agent.tvr.plane)})
- Archetype: {agent.tvr.primary_arch} ({_arch_name(agent.tvr.primary_arch)})
- K(x): {agent.k_current:.2f} (karmic inertia)
- Coherence: {agent.current_coherence:.3f}
- Phase: {agent.tvr.cycle_phase} — {_phase_description(agent.tvr.cycle_phase)}

CONTEXTUAL CONDITIONS: {ctx_summary}

INSTRUCTIONS:
1. Greet the pilgrim briefly
2. Ask your three questions — each should be specific to this pilgrim's situation
3. After each answer (which you will imagine based on their archetype and backstory), respond
4. Close with what you see on their path ahead

The reading should be 400-800 words. Address the pilgrim directly. The three questions should surface different dimensions of their situation.

Remember: you are a duck. An enlightened one, but still a duck. This matters."""

    async def run(self) -> dict:
        """Run the full theatre."""
        start_time = time.time()
        run_id = str(uuid.uuid4())[:8]
        sessions = []

        print(f"\n  Pack: {self.manifest.pack}")
        print(f"  Agents: {len(self.manifest.agents)}")
        print(f"  Sessions per agent: {self.manifest.sessions_per_agent}")
        print()

        for theatre_agent in self.manifest.agents:
            agent = self._build_agent(theatre_agent)

            # Write agent to vault
            self.vault.create_agent(agent.to_dict())

            for session_num in range(self.manifest.sessions_per_agent):
                # Sample context with fixed axes
                context = sample_context(agent.tvr)
                context.agent_id = agent.id

                # Apply fixed axes from manifest
                if self.manifest.fixed_axes:
                    from engine.context import LEAF_NODES
                    leaf_map = {n.id: n for n in LEAF_NODES}
                    for axis_key, leaf_id in self.manifest.fixed_axes.items():
                        if leaf_id in leaf_map:
                            # Map axis_key (like E2_1) to axis code (like E2)
                            axis_code = axis_key.split("_")[0]
                            context.leaves[axis_code] = leaf_map[leaf_id]

                # Build prompts
                system_prompt = self._build_system_prompt(agent, context)
                user_prompt = self._build_user_prompt(agent, theatre_agent.backstory)

                # Run session
                self._print_progress(agent.name, agent.k_current, agent.tvr.cycle_phase, "running...")
                session_output = await _call_anthropic(system_prompt, user_prompt)

                # Compute K delta
                protocol = {"name": f"{self.manifest.pack}", "domain": "Theatre"}
                k_delta = compute_k_delta(agent, protocol, context, session_output)
                k_before = agent.k_current

                # Write to vault
                vault_record_id = self.vault.write_session(
                    agent_id=agent.id,
                    protocol=protocol,
                    tvr_coords=agent.tvr,
                    context=context,
                    session_content=session_output,
                    k_delta=k_delta,
                )

                # Update agent
                agent.update_after_session(k_delta)
                self.vault.update_agent(agent.id, {
                    "k_current": round(agent.k_current, 4),
                    "coherence": round(agent.current_coherence, 4),
                    "cycle_phase": agent.tvr.cycle_phase,
                    "incarnation_n": agent.tvr.incarnation_n,
                    "sessions_completed": agent.sessions_completed,
                })

                session_result = {
                    "agent_name": agent.name,
                    "plane": agent.tvr.plane,
                    "primary_arch": agent.tvr.primary_arch,
                    "k_before": round(k_before, 4),
                    "k_after": round(agent.k_current, 4),
                    "k_delta": round(k_delta, 4),
                    "coherence_after": round(agent.current_coherence, 4),
                    "cycle_phase": agent.tvr.cycle_phase,
                    "backstory": theatre_agent.backstory,
                    "session_output": session_output,
                    "session_excerpt": session_output[:200],
                    "vault_record_id": vault_record_id,
                }
                sessions.append(session_result)

                # Voynich page generation
                if getattr(self.manifest, "voynich_mode", False):
                    self._encode_voynich_page(session_result, len(sessions))

                self._print_progress(agent.name, agent.k_current, agent.tvr.cycle_phase, "complete")

        # Analysis
        analysis = {}
        if self.manifest.track_divergence:
            analysis = analyze_run(sessions, self.manifest)

        # Report
        report_path = None
        if self.manifest.generate_report:
            results_dict = {
                "theatre": self.theatre_name,
                "run_id": run_id,
                "agents_run": len(self.manifest.agents),
                "sessions": sessions,
                "analysis": analysis,
                "duration_seconds": round(time.time() - start_time, 1),
            }
            report_dir = f"data/theatres/{self.theatre_name}/reports"
            report_path = generate_report(results_dict, self.manifest, report_dir)

        return {
            "theatre": self.theatre_name,
            "run_id": run_id,
            "agents_run": len(self.manifest.agents),
            "sessions": sessions,
            "analysis": analysis,
            "report_path": report_path,
            "duration_seconds": round(time.time() - start_time, 1),
        }

    def _encode_voynich_page(self, session_result: dict, page_number: int):
        """Generate a Voynich page from a session result."""
        from engine.voynich.encoder import encode_session
        from engine.voynich.renderer import render_page
        from engine.voynich.alphabet import generate_alphabet

        if not hasattr(self, "_voynich_alphabet"):
            seed = getattr(self.manifest, "voynich_instance_seed", None)
            if not seed:
                import uuid
                seed = str(uuid.uuid4())[:12]
            self._voynich_alphabet = generate_alphabet(seed)
            self._voynich_page_count = 0

        self._voynich_page_count += 1

        page = encode_session(
            session_result=session_result,
            alphabet=self._voynich_alphabet,
            page_number=self._voynich_page_count,
            tick=self._voynich_page_count,
            tick_shadow_count=0,
        )

        html = render_page(page, self._voynich_alphabet)

        page_dir = f"data/theatres/{self.theatre_name}/pages"
        os.makedirs(page_dir, exist_ok=True)
        page_path = os.path.join(page_dir, f"page_{self._voynich_page_count:04d}.html")
        with open(page_path, "w") as f:
            f.write(html)

    def _print_progress(self, agent_name: str, k: float, phase: str, status: str):
        icon = {"ACC": "·", "CRS": "!", "RES": "↓", "TRN": "~", "LIB": "★"}.get(phase, "·")
        print(f"  [{self.theatre_name}] {icon} {agent_name:<16} K:{k:.2f} {phase} · {status}")
