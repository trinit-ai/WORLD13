"""
pack_drafter.py — Batch pack draft generator.

Reads all stub packs from protocols/library/, calls Claude API to draft
MANIFEST.md + manifest.json for each, writes output as status: draft.

Usage:
  python engine/pack_drafter.py                    # draft all stubs
  python engine/pack_drafter.py --category sales   # one category
  python engine/pack_drafter.py --pack discovery_call  # one pack
  python engine/pack_drafter.py --tier 1           # one priority tier
  python engine/pack_drafter.py --dry-run          # log plan, no API calls
  python engine/pack_drafter.py --resume           # skip already-drafted
"""

import argparse
import json
import logging
import os
import time
from datetime import date
from pathlib import Path

import yaml
from dotenv import load_dotenv

# --- Paths ---

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

from anthropic import Anthropic  # noqa: E402 — must load env first
LIBRARY_DIR = BASE_DIR / "protocols" / "library"
PACKS_DIR = BASE_DIR / "protocols" / "packs"
PROGRESS_FILE = BASE_DIR / "output" / "draft_progress.json"

# --- Model ---

MODEL = os.getenv("TMOS13_MODEL", "claude-sonnet-4-6")
client = Anthropic()

# --- Logging ---

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pack_drafter")

# --- Template Map ---

TEMPLATE_MAP = {
    "sales": "lead_qualification",
    "marketing": "campaign_builder",
    "consulting": "manda_negotiation",
    "legal": "legal_intake",
    "criminal_justice": "legal_intake",
    "insurance": "legal_intake",
    "medical": "clinical_decision",
    "mental_health": "clinical_decision",
    "social_work": "clinical_decision",
    "hr": "candidate_screener",
    "education": "classroom",
    "finance": "business_case",
    "real_estate": "real_estate",
    "quantitative": "business_case",
    "research": "manda_negotiation",
    "engineering": "business_case",
    "architecture": "business_case",
    "government": "legal_intake",
    "diplomatic": "manda_negotiation",
    "agriculture": "manda_negotiation",
    "hospitality": "customer_support",
    "sports": "lead_qualification",
    "media": "campaign_builder",
    "games": "enlightened_duck",
    "scenarios": "manda_negotiation",
    "experiences": "rituals",
    "simulator": "manda_negotiation",
    "personal": "rituals",
    "creative": "rituals",
    "_default": "desk",
}

SENSITIVE_CATEGORIES = {
    "medical",
    "mental_health",
    "criminal_justice",
    "social_work",
    "legal",
    "insurance",
}

PRIORITY_TIERS = [
    ["sales", "hr", "finance", "marketing", "consulting"],
    [
        "education",
        "real_estate",
        "engineering",
        "research",
        "hospitality",
        "media",
        "sports",
        "architecture",
    ],
    [
        "legal",
        "medical",
        "mental_health",
        "criminal_justice",
        "social_work",
        "insurance",
        "government",
        "diplomatic",
        "agriculture",
    ],
    ["games", "scenarios", "experiences", "simulator", "personal", "creative"],
]

# --- Helpers ---


def load_stub(pack_dir: Path) -> dict | None:
    """Load a stub header.yaml. Returns None if not a stub."""
    header_path = pack_dir / "header.yaml"
    if not header_path.exists():
        return None
    with open(header_path) as f:
        data = yaml.safe_load(f)
    if not data or data.get("status") != "stub":
        return None  # only process stubs
    return data


def load_template(pack_id: str) -> str:
    """Load master.md from an active pack as a structural reference."""
    master = PACKS_DIR / pack_id / "master.md"
    if master.exists():
        return master.read_text()[:4000]
    manifest = PACKS_DIR / pack_id / "manifest.json"
    if manifest.exists():
        return json.dumps(json.loads(manifest.read_text()), indent=2)[:4000]
    return ""


def get_template_pack(category: str) -> str:
    return TEMPLATE_MAP.get(category, TEMPLATE_MAP["_default"])


def is_sensitive(category: str) -> bool:
    return category in SENSITIVE_CATEGORIES


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {"drafted": [], "failed": [], "skipped": []}


def save_progress(progress: dict):
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2))


def collect_stubs(category_filter=None, pack_filter=None) -> list[dict]:
    """Walk library dir, collect all stub packs."""
    stubs = []
    for cat_dir in sorted(LIBRARY_DIR.iterdir()):
        if not cat_dir.is_dir() or cat_dir.name.startswith("."):
            continue
        cat = cat_dir.name
        if category_filter and cat != category_filter:
            continue
        for pack_dir in sorted(cat_dir.iterdir()):
            if not pack_dir.is_dir():
                continue
            data = load_stub(pack_dir)
            if data:
                data["_path"] = str(pack_dir)
                data["_category"] = cat
                pack_id = data.get("pack_id", data.get("id", pack_dir.name))
                data["pack_id"] = pack_id
                if not pack_filter or pack_id == pack_filter:
                    stubs.append(data)
    return stubs


def collect_stubs_by_tier(tier_num: int) -> list[dict]:
    cats = PRIORITY_TIERS[tier_num - 1]
    stubs = []
    for cat in cats:
        stubs.extend(collect_stubs(category_filter=cat))
    return stubs


# --- Draft Generation ---

MANIFEST_SYSTEM = """You are a pack protocol author for the 13TMOS platform.

Your job is to write a MANIFEST.md — the governing protocol for an AI session pack.
A pack governs a specific professional or creative use case. The manifest defines:
- Identity and persona of the AI in this session
- Voice calibration (tone, rules, things never to do)
- Conversation flow (phases, turn structure, pacing)
- Formatting rules (what UI components to use or avoid)
- Domain boundaries (what the AI can and cannot do in this role)
- Session intelligence (what structured output to produce at the end)

You are given:
1. The pack's name, category, and one-line description
2. A reference manifest from the closest active pack in the same category

Write a complete, ready-to-review MANIFEST.md for the new pack.
Match the structural depth of the reference manifest.
Adapt voice, flow, and domain rules to the specific pack's purpose.

CRITICAL RULES:
- Never invent specific company names, prices, or real-world entities
- Use [Variable] placeholders for anything operator-configurable
- Write in second person: "You are the [role]."
- Every section must reflect the specific pack's domain, not generic AI behavior
- Formatting rules section must always specify which UI components are enabled/disabled
- Domain boundaries section must always exist

If this is a SENSITIVE category (medical, mental_health, criminal_justice,
social_work, legal, insurance), add this block at the top after the title:

---
WARNING: SENSITIVE CATEGORY — DRAFT REQUIRES REVIEW
This draft was auto-generated. Before deploying this pack, the full protocol
must be reviewed and validated by a licensed [DOMAIN] professional.
Do not deploy this pack without domain expert sign-off.
---

Output ONLY the MANIFEST.md content. No preamble. No explanation. No markdown fences."""

MANIFEST_JSON_SYSTEM = """You are a pack configuration author for the 13TMOS platform.

Generate a manifest.json for a pack given its name, category, description,
and a reference manifest.json from a similar active pack.

The manifest.json is the machine-readable spec. It defines:
- Pack metadata (id, name, version, category, description, tagline)
- Personality parameters (tone, warmth, humor, formality, identity)
- Cartridges (the conversational modules within the pack)
- Commands (session reset, status, navigation triggers)
- Features (which platform capabilities are enabled)
- State schema (fields tracked across the session)
- Privacy settings
- Library metadata

RULES:
- version: always "1.0.0" for new packs
- status: always "draft" (not active)
- estimated_turns: realistic for this pack type (6-12 for intake, 8-18 for complex, 3-6 for simple)
- Cartridges: 2-5 is normal. Name them for the actual phases of this session type.
- State schema: define the fields this specific session would track
- Features: enable only what makes sense for this pack (not all features for all packs)
- DO NOT include data_rail tabs — those are operator-configured at deploy time
- theme: omit (operator-configured)
- schedule: omit (operator-configured)

Output ONLY valid JSON. No preamble. No explanation. No markdown fences."""


def draft_manifest(stub: dict, template_text: str, sensitive: bool) -> str:
    """Call Claude API to draft MANIFEST.md."""
    sensitive_note = (
        " (SENSITIVE CATEGORY — structural skeleton only)" if sensitive else ""
    )

    prompt = f"""Pack to author{sensitive_note}:

Name: {stub.get('name', stub.get('pack_id'))}
Pack ID: {stub.get('pack_id')}
Category: {stub.get('_category', stub.get('category'))}
Description: {stub.get('description', 'No description provided')}

Reference manifest from closest active pack ({get_template_pack(stub.get('_category', 'default'))}):

{template_text}

Write the MANIFEST.md for this pack."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=MANIFEST_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def draft_manifest_json(stub: dict, ref_json: str) -> dict:
    """Call Claude API to draft manifest.json."""
    prompt = f"""Pack to configure:

Name: {stub.get('name', stub.get('pack_id'))}
Pack ID: {stub.get('pack_id')}
Category: {stub.get('_category', stub.get('category'))}
Description: {stub.get('description', 'No description provided')}

Reference manifest.json:
{ref_json[:3000]}

Generate the manifest.json for this pack."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        system=MANIFEST_JSON_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def write_draft(stub: dict, manifest_md: str, manifest_json: dict):
    """Write draft files to library directory."""
    pack_id = stub["pack_id"]
    category = stub.get("_category", stub.get("category"))
    pack_dir = LIBRARY_DIR / category / pack_id
    pack_dir.mkdir(parents=True, exist_ok=True)

    # Write MANIFEST.md (overwrites placeholder)
    (pack_dir / "MANIFEST.md").write_text(manifest_md)

    # Write manifest.json
    (pack_dir / "manifest.json").write_text(json.dumps(manifest_json, indent=2))

    # Update header.yaml — status: draft
    header = {
        "pack_id": pack_id,
        "name": stub.get("name"),
        "category": category,
        "status": "draft",
        "description": stub.get("description", ""),
        "estimated_turns": str(manifest_json.get("estimated_turns", "TBD")),
        "version": manifest_json.get("version", "1.0.0"),
        "drafted_by": "pack_drafter.py",
        "draft_date": date.today().isoformat(),
        "requires_review": category in SENSITIVE_CATEGORIES,
    }
    with open(pack_dir / "header.yaml", "w") as f:
        yaml.dump(header, f, default_flow_style=False, allow_unicode=True)


# --- Main Loop ---


def process_stub(stub: dict, dry_run: bool = False) -> str:
    """Draft one pack. Returns: drafted | skipped | failed."""
    pack_id = stub.get("pack_id", "unknown")
    category = stub.get("_category", stub.get("category", "unknown"))
    template_pack = get_template_pack(category)
    sensitive = is_sensitive(category)

    log.info(
        "  %s (%s) -> template: %s%s",
        pack_id,
        category,
        template_pack,
        " [SENSITIVE]" if sensitive else "",
    )

    if dry_run:
        return "skipped"

    try:
        template_text = load_template(template_pack)

        # Load reference manifest.json for json drafting
        ref_json_path = PACKS_DIR / template_pack / "manifest.json"
        ref_json = ref_json_path.read_text() if ref_json_path.exists() else "{}"

        # Draft MANIFEST.md
        manifest_md = draft_manifest(stub, template_text, sensitive)

        # Pause between API calls to avoid 529 overload
        time.sleep(2)

        # Draft manifest.json
        try:
            manifest_json = draft_manifest_json(stub, ref_json)
        except (json.JSONDecodeError, Exception) as e:
            log.warning(
                "  manifest.json parse failed for %s, using skeleton: %s", pack_id, e
            )
            manifest_json = {
                "id": pack_id,
                "name": stub.get("name"),
                "version": "1.0.0",
                "status": "draft",
                "category": category,
                "description": stub.get("description", ""),
                "estimated_turns": "8-12",
                "requires_review": sensitive,
            }

        write_draft(stub, manifest_md, manifest_json)
        log.info("  ✓ %s drafted", pack_id)
        return "drafted"

    except Exception as e:
        log.error("  ✗ %s failed: %s", pack_id, e)
        return "failed"


def run(args):
    progress = (
        load_progress()
        if args.resume
        else {"drafted": [], "failed": [], "skipped": []}
    )

    # Collect stubs
    if args.pack:
        stubs = collect_stubs(pack_filter=args.pack)
    elif args.category:
        stubs = collect_stubs(category_filter=args.category)
    elif args.tier:
        stubs = collect_stubs_by_tier(args.tier)
    else:
        # All stubs, in priority tier order
        stubs = []
        seen_cats = set()
        for tier in PRIORITY_TIERS:
            for cat in tier:
                stubs.extend(collect_stubs(category_filter=cat))
                seen_cats.add(cat)
        # Catch any categories not in priority tiers
        for cat_dir in sorted(LIBRARY_DIR.iterdir()):
            if cat_dir.is_dir() and cat_dir.name not in seen_cats:
                stubs.extend(collect_stubs(category_filter=cat_dir.name))

    # Skip already processed if resuming (retry failures)
    if args.resume:
        already = set(progress["drafted"] + progress["skipped"])
        stubs = [s for s in stubs if s["pack_id"] not in already]
        progress["failed"] = []  # clear failures for retry

    total = len(stubs)
    log.info("Pack Drafter — %d stubs to process", total)
    log.info("Model: %s | Dry run: %s", MODEL, args.dry_run)
    log.info("---" * 20)

    drafted = failed = 0
    for i, stub in enumerate(stubs, 1):
        log.info("[%d/%d] %s", i, total, stub["pack_id"])
        result = process_stub(stub, dry_run=args.dry_run)
        if result == "drafted":
            drafted += 1
            progress["drafted"].append(stub["pack_id"])
        elif result == "failed":
            failed += 1
            progress["failed"].append(stub["pack_id"])
        else:
            progress["skipped"].append(stub["pack_id"])
        save_progress(progress)
        time.sleep(3)  # courtesy pause — avoid 529 overload

    log.info("---" * 20)
    log.info(
        "Done. Drafted: %d | Failed: %d | Skipped: %d",
        drafted,
        failed,
        total - drafted - failed,
    )
    log.info("Progress saved to %s", PROGRESS_FILE)


# --- CLI ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch pack draft generator")
    parser.add_argument("--category", help="Draft one category only")
    parser.add_argument("--pack", help="Draft one pack only")
    parser.add_argument(
        "--tier", type=int, choices=[1, 2, 3, 4], help="Draft one priority tier"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Log plan, no API calls"
    )
    parser.add_argument(
        "--resume", action="store_true", help="Skip already-drafted packs"
    )
    args = parser.parse_args()
    run(args)
