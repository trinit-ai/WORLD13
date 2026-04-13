"""
theatres/eden/chronicle.py

Live chronicle writer for the Eden theatre.

Writes to both the terminal and a dated file simultaneously.
The file is the book. The terminal is the window into the book being written.

Format: no headers, no tables, no markdown structure.
Just the tick number, then the prose, one passage after another.
The way you'd read a novel.
"""

import os
from datetime import datetime


class EdenChronicle:
    def __init__(self, output_dir: str = "data/eden"):
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.filepath = os.path.join(output_dir, f"eden_{timestamp}.md")
        self._file = open(self.filepath, "w", buffering=1)

        self._file.write("# Eden\n\n")
        self._file.write(f"*Started: {datetime.now().strftime('%B %d, %Y — %H:%M')}*\n\n")
        self._file.write("---\n\n")

        print(f"\nEDEN — The world begins.")
        print(f"Chronicle: {self.filepath}\n")

    def write_tick(self, tick: int, sessions: list, births: list,
                   population: list) -> None:
        """Write one tick to the chronicle and terminal."""

        print(f"── Tick {tick} ─────────────────────────────────────────")

        self._file.write(f"\n\n*Tick {tick}*\n\n")

        for s in sessions:
            content = s.get("content", "").strip()
            name = s.get("agent_name", "?")
            partner = s.get("partner_name", "?")
            k_after = s.get("k_after", 0)
            delta = s.get("k_delta", 0)

            excerpt = content.split(".")[0].strip() if content else ""
            if len(excerpt) > 100:
                excerpt = excerpt[:100] + "..."
            delta_str = f"Δ:{delta:+.3f}"
            print(f"\n  {name} & {partner}  (K:{k_after:.2f}  {delta_str})")
            if excerpt:
                print(f"  {excerpt}.")

            self._file.write(f"{content}\n\n")

        for child in births:
            birth_line = (
                f"*{child.name} was born.*"
                f"  (Generation {child.generation}  ·  "
                f"K:{child.k_current:.2f}  ·  λ:{child.lambda_coeff:.2f})"
            )
            print(f"\n  ✦ {child.name} enters the world.  "
                  f"(Gen {child.generation}  K:{child.k_current:.2f})")
            self._file.write(f"{birth_line}\n\n")

        living = [a for a in population if a.is_alive]
        if living:
            mean_k = sum(a.k_current for a in living) / len(living)
            print(f"\n  ── {len(living)} living  ·  mean K:{mean_k:.2f}")

    def write_closing(self, tick: int, population: list) -> None:
        """Write the closing entry."""
        living = [a for a in population if a.is_alive]
        generations = set(a.generation for a in living)

        self._file.write("---\n\n")
        self._file.write(f"*The chronicle ends at tick {tick}.*\n\n")
        self._file.write(f"*{len(living)} people remain.*\n")
        if len(generations) > 1:
            self._file.write(f"*{len(generations)} generations.*\n")

        self._file.write("\n")
        for agent in sorted(living, key=lambda a: a.generation):
            self._file.write(
                f"*{agent.name}  ·  Generation {agent.generation}  ·  "
                f"K:{agent.k_current:.2f}  ·  {agent.sessions_completed} sessions*\n"
            )

        self._file.close()
        print(f"\nChronicle saved: {self.filepath}")

    def close(self):
        if self._file and not self._file.closed:
            self._file.close()
