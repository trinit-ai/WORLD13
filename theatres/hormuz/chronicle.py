"""
theatres/hormuz/chronicle.py

Live chronicle writer for the Hormuz theatre.

Same structure as Eden's chronicle.
No tables. No metadata in the file.
Just the prose, one passage after another.
The way you'd read dispatches from inside a war.

The terminal shows K(x) data.
The file shows only what was written.
"""

import os
from datetime import datetime


class HormuzChronicle:
    def __init__(self, output_dir: str = "data/hormuz"):
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.filepath = os.path.join(output_dir, f"hormuz_{timestamp}.md")
        self._file = open(self.filepath, "w", buffering=1)

        self._file.write("# Hormuz\n\n")
        self._file.write(
            f"*Day 45 of the US-Iran war. April 13, 2026.*\n\n"
            f"*The blockade began this morning.*\n\n"
        )
        self._file.write("---\n\n")

        print(f"\nHORMUZ — Day 45. The blockade is live.")
        print(f"Chronicle: {self.filepath}\n")

    def write_tick(self, tick: int, sessions: list, all_agents: list) -> None:
        print(f"── Tick {tick} ─────────────────────────────────────────")

        self._file.write(f"\n\n*Tick {tick}*\n\n")

        for s in sessions:
            content = s.get("content", "").strip()
            name = s.get("agent_name", "?")
            partner = s.get("partner_name", "?")
            k_after = s.get("k_after", 0)
            delta = s.get("k_delta", 0)

            excerpt = content.split(".")[0].strip() if content else ""
            if len(excerpt) > 110:
                excerpt = excerpt[:110] + "..."

            direction = "↑" if delta > 0.05 else ("↓" if delta < -0.05 else "·")
            print(f"\n  {direction} {name} / {partner}  (K:{k_after:.2f}  Δ:{delta:+.3f})")
            if excerpt:
                print(f"  {excerpt}.")

            self._file.write(f"{content}\n\n")

        # Global K pulse — terminal only
        active = [a for a in all_agents if a.is_active]
        if active:
            mean_k = sum(a.k_current for a in active) / len(active)
            highest = max(active, key=lambda a: a.k_current)
            lowest = min(active, key=lambda a: a.k_current)

            bar_chars = int(mean_k * 5)
            bar = "█" * bar_chars + "░" * (50 - bar_chars)

            print(f"\n  ── Global K: {mean_k:.2f}  [{bar}]")
            print(f"     Highest: {highest.name} ({highest.k_current:.2f})")
            print(f"     Lowest:  {lowest.name} ({lowest.k_current:.2f})")

    def write_closing(self, tick: int, all_agents: list) -> None:
        active = [a for a in all_agents if a.is_active]
        mean_k = sum(a.k_current for a in active) / len(active) if active else 0

        self._file.write("---\n\n")
        self._file.write(f"*The chronicle ends at tick {tick}.*\n\n")

        if mean_k < 4.0:
            self._file.write("*Something shifted. The room quieted.*\n\n")
        elif mean_k > 8.5:
            self._file.write("*The blockade held. Nothing resolved.*\n\n")
        else:
            self._file.write("*The situation continued. Unresolved.*\n\n")

        self._file.write("**Final escalation pressures:**\n\n")
        for agent in sorted(all_agents, key=lambda a: a.k_current, reverse=True):
            self._file.write(
                f"*{agent.name}  ·  K:{agent.k_current:.2f}  ·  "
                f"{agent.sessions_completed} sessions*\n"
            )

        self._file.close()
        print(f"\nChronicle saved: {self.filepath}")

    def close(self):
        if self._file and not self._file.closed:
            self._file.close()
