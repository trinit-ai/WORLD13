"""
13TMOS Local Intelligence Layer — Synaptic awareness for the CLI.

Reads the local filesystem vault and synthesizes cross-session intelligence:
- Engagement index (which packs, how often, how deep)
- User memory (patterns synthesized from session content via LLM)
- Interest signals (domain engagement levels)
- Desk context block (injected into system prompt)

Local equivalent of the production engine's three-tier memory system
(session_journals -> memory_consolidations -> user_identity_models)
built on the filesystem vault, not Supabase.
"""
from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("13tmos.intelligence")

INTEL_DIR = Path(__file__).resolve().parent.parent / "vault" / "intelligence"
CACHE_FILE = INTEL_DIR / "cache.json"

MIN_SESSIONS_FOR_SYNTHESIS = 3

DOMAIN_LABELS = {
    "legal": "Legal", "medical": "Medical", "mental_health": "Mental Health",
    "finance": "Finance", "hr": "HR", "real_estate": "Real Estate",
    "research": "Research", "engineering": "Engineering",
    "education": "Education", "criminal_justice": "Criminal Justice",
    "consulting": "Consulting", "creative": "Creative",
    "games": "Games", "platform": "Platform", "simulations": "Simulations",
    "agriculture": "Agriculture", "architecture": "Architecture",
    "hospitality": "Hospitality", "insurance": "Insurance",
    "media": "Media", "personal": "Personal", "sales": "Sales",
    "social_work": "Social Work", "sports": "Sports",
}

# Domain adjacency for suggestions
DOMAIN_ADJACENCY = {
    "legal": ["compliance_audit", "contract_review", "ip_assessment"],
    "medical": ["mental_health_intake", "clinical_triage", "patient_navigation"],
    "finance": ["business_case", "real_estate", "insurance_intake"],
    "hr": ["candidate_screener", "performance_review", "engagement_scoping"],
    "research": ["market_analysis", "literature_review", "survey_design"],
}


class LocalIntelligence:
    """Synaptic intelligence layer for the local 13TMOS CLI."""

    def __init__(self, vault_dir: Path, api_key: str = None):
        self.vault_dir = vault_dir
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        INTEL_DIR.mkdir(parents=True, exist_ok=True)
        self._cache: dict = self._load_cache()

    # ── Public API ─────────────────────────────────────────────────────

    def get_desk_context(self, force_refresh: bool = False) -> str:
        """Get the synaptic context block for injection into system prompts."""
        sessions = self._scan_vault()
        if not sessions:
            return ""

        cached_count = self._cache.get("session_count", 0)
        if force_refresh or len(sessions) > cached_count:
            self._refresh(sessions)

        engagement = self._cache.get("engagement", {})
        memory = self._cache.get("user_memory", "")
        top_domains = self._cache.get("top_domains", [])

        if not engagement and not memory:
            return ""

        lines = ["[SYSTEM INTELLIGENCE — Cross-session awareness]"]
        lines.append(f"Sessions logged: {len(sessions)}")

        if top_domains:
            lines.append(f"Most active domains: {', '.join(top_domains[:5])}")

        if engagement:
            top_packs = sorted(
                engagement.items(), key=lambda x: x[1]["count"], reverse=True
            )[:5]
            pack_str = ", ".join(f"{p} ({d['count']}x)" for p, d in top_packs)
            lines.append(f"Top packs: {pack_str}")

        if memory:
            lines.append("")
            lines.append("User patterns (synthesized from session history):")
            lines.append(memory)

        lines.append("[/SYSTEM INTELLIGENCE]")
        return "\n".join(lines)

    def get_pack_context(self, pack_id: str) -> str:
        """Get session history context for a specific pack."""
        engagement = self.get_engagement_summary()
        pack_data = engagement.get(pack_id)
        if not pack_data or pack_data["count"] == 0:
            return ""
        return (
            f"[SESSION HISTORY — This pack]\n"
            f"Prior sessions: {pack_data['count']} | "
            f"Avg turns: {pack_data['avg_turns']}\n"
            f"[/SESSION HISTORY]"
        )

    def get_engagement_summary(self) -> dict:
        """Return engagement index: pack_id -> {count, total_turns, avg_turns, last_run, category}."""
        sessions = self._scan_vault()
        engagement = defaultdict(lambda: {
            "count": 0, "total_turns": 0, "last_run": "", "category": ""
        })

        for session in sessions:
            pack = session.get("pack", "unknown")
            turns = self._count_turns(session)
            date = session.get("date", "")
            category = self._infer_category(pack)

            engagement[pack]["count"] += 1
            engagement[pack]["total_turns"] += turns
            engagement[pack]["category"] = category
            if date > engagement[pack]["last_run"]:
                engagement[pack]["last_run"] = date

        for data in engagement.values():
            count = data["count"]
            data["avg_turns"] = round(data["total_turns"] / count, 1) if count else 0

        return dict(engagement)

    def get_domain_interests(self) -> list[tuple[str, int]]:
        """Return domain interest ranking as (domain, count) pairs."""
        engagement = self.get_engagement_summary()
        domain_counts = defaultdict(int)

        for pack, data in engagement.items():
            cat = data.get("category") or self._infer_category(pack)
            if cat:
                domain_counts[cat] += data["count"]

        return sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)

    def format_pulse(self) -> str:
        """Format the /pulse display — engagement profile for CLI."""
        sessions = self._scan_vault()
        engagement = self.get_engagement_summary()
        domain_interests = self.get_domain_interests()
        memory = self._cache.get("user_memory", "")

        lines = []
        lines.append(f"\n  Pulse")
        lines.append(f"  {'─' * 50}")
        lines.append(f"  Sessions logged:  {len(sessions)}")

        if not sessions:
            lines.append("  No sessions yet. Run a pack to build your profile.")
            lines.append("")
            return "\n".join(lines)

        if domain_interests:
            lines.append("")
            lines.append("  Domain engagement")
            max_count = domain_interests[0][1] if domain_interests else 1
            for domain, count in domain_interests[:8]:
                label = DOMAIN_LABELS.get(domain, domain.replace("_", " ").title())
                bar_len = int((count / max_count) * 20)
                bar = "#" * bar_len + "." * (20 - bar_len)
                lines.append(f"  {label:<20}  {bar}  {count}")

        if engagement:
            lines.append("")
            lines.append("  Pack activity")
            top_packs = sorted(
                engagement.items(), key=lambda x: x[1]["count"], reverse=True
            )[:8]
            for pack, data in top_packs:
                count = data["count"]
                avg_t = data["avg_turns"]
                last = data["last_run"][:10] if data["last_run"] else "—"
                lines.append(
                    f"  {pack:<30}  {count:>3}x  avg {avg_t:>4} turns  last: {last}"
                )

        if memory:
            lines.append("")
            lines.append("  Synthesized patterns")
            for line in memory.split("\n"):
                if line.strip():
                    lines.append(f"  {line.strip()}")

        unstarted = self._get_unstarted_suggestions(engagement)
        if unstarted:
            lines.append("")
            lines.append("  Suggested next")
            for pack in unstarted[:4]:
                lines.append(f"  ·  {pack}")

        lines.append(f"\n  {'─' * 50}\n")
        return "\n".join(lines)

    async def synthesize_memory(self, sessions: list[dict]) -> str:
        """Use Claude (Haiku) to synthesize user patterns from session records."""
        if len(sessions) < MIN_SESSIONS_FOR_SYNTHESIS or not self.api_key:
            return ""

        session_lines = []
        for s in sessions[-20:]:
            pack = s.get("pack", "unknown")
            date = s.get("date", "")
            content = s.get("content", {})
            summary = ""
            if isinstance(content, dict):
                summary = content.get("summary", "")
            turns = self._count_turns(s)
            line = f"- [{pack}, {turns} turns, {date}]"
            if summary:
                line += f" {summary[:100]}"
            session_lines.append(line)

        if not session_lines:
            return ""

        prompt = (
            f"A user has run {len(sessions)} sessions. Recent sessions:\n\n"
            + "\n".join(session_lines)
            + "\n\nSynthesize 3-5 sentences describing their patterns: "
            "what domains they care about, how they use the platform, "
            "what they seem to be building or working on. "
            "Be specific. No pleasantries."
        )

        try:
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 300,
                        "system": (
                            "You are a memory synthesis engine. "
                            "Produce a concise, specific pattern summary. "
                            "No pleasantries. Just the patterns."
                        ),
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                data = resp.json()
                return data.get("content", [{}])[0].get("text", "").strip()
        except Exception as e:
            logger.warning("Memory synthesis failed: %s", e)
            return ""

    # ── Internal ───────────────────────────────────────────────────────

    def _scan_vault(self) -> list[dict]:
        """Scan the local vault and return all session records."""
        sessions = []
        if not self.vault_dir.exists():
            return sessions

        for json_file in self.vault_dir.rglob("*.json"):
            # Skip intelligence cache files
            if "intelligence" in json_file.parts:
                continue
            try:
                data = json.loads(json_file.read_text())
                if isinstance(data, dict) and data.get("pack"):
                    sessions.append(data)
            except Exception:
                continue

        return sorted(sessions, key=lambda s: s.get("date", ""), reverse=True)

    def _count_turns(self, session: dict) -> int:
        """Extract turn count from a vault record."""
        content = session.get("content", {})
        if isinstance(content, dict):
            transcript = content.get("transcript", [])
            if isinstance(transcript, list):
                return sum(1 for t in transcript if t.get("role") == "user")
            summary = content.get("summary", "")
            if summary:
                import re
                m = re.search(r"(\d+)\s*turns?", summary)
                if m:
                    return int(m.group(1))
        return 0

    def _refresh(self, sessions: list[dict]):
        """Refresh the intelligence cache from current vault state."""
        engagement = self.get_engagement_summary()
        top_domains = [
            DOMAIN_LABELS.get(d, d) for d, _ in self.get_domain_interests()[:5]
        ]

        self._cache.update({
            "session_count": len(sessions),
            "engagement": engagement,
            "top_domains": top_domains,
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
        })
        self._save_cache()

    async def refresh_with_synthesis(self, sessions: list[dict]):
        """Refresh cache including LLM memory synthesis."""
        self._refresh(sessions)
        memory = await self.synthesize_memory(sessions)
        if memory:
            self._cache["user_memory"] = memory
            self._save_cache()

    def _load_cache(self) -> dict:
        try:
            if CACHE_FILE.exists():
                return json.loads(CACHE_FILE.read_text())
        except Exception:
            pass
        return {}

    def _save_cache(self):
        try:
            CACHE_FILE.write_text(json.dumps(self._cache, indent=2))
        except Exception as e:
            logger.warning("Failed to save intelligence cache: %s", e)

    def _infer_category(self, pack_id: str) -> str:
        """Infer domain category from pack ID."""
        for domain in DOMAIN_LABELS:
            if domain in pack_id:
                return domain
        return ""

    def _get_unstarted_suggestions(self, engagement: dict) -> list[str]:
        """Suggest packs adjacent to the user's most active domains."""
        ran = set(engagement.keys())
        top_domains = [d for d, _ in self.get_domain_interests()[:3]]
        suggestions = []

        for domain in top_domains:
            for suggestion in DOMAIN_ADJACENCY.get(domain, []):
                if suggestion not in ran:
                    suggestions.append(suggestion)

        return suggestions[:4]


# ── Singleton ──────────────────────────────────────────────────────────

_intel = None


def init_local_intelligence(vault_dir: Path, api_key: str = None) -> LocalIntelligence:
    global _intel
    _intel = LocalIntelligence(vault_dir, api_key)
    return _intel


def get_local_intelligence():
    return _intel
