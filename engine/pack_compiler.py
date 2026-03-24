#!/usr/bin/env python3
"""
Pack Compiler — Converts library behavioral manifests into launchable runtime packs.

Reads header.yaml + MANIFEST.md from protocols/library/{category}/{pack_id}/
and generates manifest.json + master.md in place, making the pack launchable
from the console.

Usage:
    python engine/pack_compiler.py                          # compile all active library packs
    python engine/pack_compiler.py --pack construction_intake  # compile one pack
    python engine/pack_compiler.py --category architecture     # compile one category
    python engine/pack_compiler.py --dry-run                   # preview without writing
"""
import argparse
import json
import logging
import re
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
LIBRARY_DIR = ROOT_DIR / "protocols" / "library"

log = logging.getLogger("pack_compiler")
logging.basicConfig(level=logging.INFO, format="%(message)s")


# ─── Header Parsing ──────────────────────────────────────────

def load_header(pack_dir: Path) -> dict:
    """Load and validate header.yaml."""
    header_path = pack_dir / "header.yaml"
    if not header_path.exists():
        return {}
    return yaml.safe_load(header_path.read_text()) or {}


def load_manifest_md(pack_dir: Path) -> str:
    """Load MANIFEST.md content."""
    manifest_path = pack_dir / "MANIFEST.md"
    if not manifest_path.exists():
        return ""
    return manifest_path.read_text()


# ─── Voice Extraction ────────────────────────────────────────

def extract_voice(manifest_md: str) -> dict:
    """Extract personality parameters from the Voice section of MANIFEST.md."""
    voice_match = re.search(r"## Voice\n\n(.+?)(?=\n## |\n---|\Z)", manifest_md, re.DOTALL)
    if not voice_match:
        return {
            "tone": "professional, direct",
            "warmth": 0.5,
            "humor": 0.0,
            "formality": 0.7,
        }

    voice_text = voice_match.group(1).lower()

    # Infer warmth
    warmth = 0.5
    if any(w in voice_text for w in ["warm", "empathetic", "reassuring", "unhurried"]):
        warmth = 0.7
    elif any(w in voice_text for w in ["serious", "technically precise", "appropriately serious"]):
        warmth = 0.3

    # Infer formality
    formality = 0.7
    if any(w in voice_text for w in ["conversational", "casual", "plain"]):
        formality = 0.5
    elif any(w in voice_text for w in ["formal", "technical", "precise"]):
        formality = 0.8

    # Extract tone description from first paragraph
    first_para = voice_match.group(1).split("\n\n")[0].strip()
    # Pull tone keywords
    tone_words = []
    for word in ["professional", "direct", "warm", "serious", "knowledgeable",
                 "precise", "grounded", "practical", "literate", "strategic"]:
        if word in voice_text:
            tone_words.append(word)
    tone = ", ".join(tone_words[:3]) if tone_words else "professional, direct"

    return {
        "tone": tone,
        "warmth": warmth,
        "humor": 0.0,
        "formality": formality,
    }


# ─── Deliverable Extraction ──────────────────────────────────

def extract_deliverable(header: dict, manifest_md: str) -> dict | None:
    """Extract deliverable spec from MANIFEST.md Deliverable section."""
    deliv_match = re.search(r"## Deliverable\n\n(.+?)(?=\n## |\n---|\Z)", manifest_md, re.DOTALL)
    if not deliv_match:
        return None

    deliv_text = deliv_match.group(1)

    # Extract type
    type_match = re.search(r"\*\*Type:\*\*\s*(.+)", deliv_text)
    deliv_type = type_match.group(1).strip() if type_match else header.get("deliverable", "session_profile")

    # Extract format
    fmt_match = re.search(r"\*\*Format:\*\*\s*(.+)", deliv_text)
    deliv_format = fmt_match.group(1).strip() if fmt_match else "both (markdown + json)"

    return {
        "enabled": True,
        "types": [{
            "id": deliv_type,
            "name": deliv_type.replace("_", " ").title(),
            "description": f"Generated {deliv_type.replace('_', ' ')} from intake session data.",
            "trigger": {
                "min_turns": 4,
                "contact_required": False,
            },
            "channels": ["download"],
            "include_transcript": True,
            "include_state_snapshot": True,
        }],
    }


# ─── Manifest JSON Generation ────────────────────────────────

def generate_manifest_json(header: dict, manifest_md: str) -> dict:
    """Generate a runtime manifest.json from header.yaml + MANIFEST.md."""
    pack_id = header.get("id", "unknown")
    name = header.get("name", pack_id.replace("_", " ").title())
    category = header.get("category", "general")
    description = header.get("description", "")
    est_turns = header.get("estimated_turns", "10-14")
    version = str(header.get("version", "1.0.0"))
    if version.count(".") == 1:
        version += ".0"

    # Parse estimated turns for session policy
    try:
        if isinstance(est_turns, str) and "-" in est_turns:
            max_turns = int(est_turns.split("-")[1])
        else:
            max_turns = int(est_turns)
    except (ValueError, IndexError):
        max_turns = 14

    personality = extract_voice(manifest_md)
    deliverables = extract_deliverable(header, manifest_md)

    manifest = {
        "id": pack_id,
        "name": name,
        "version": version,
        "status": "active",
        "access": "public",
        "category": category,
        "description": description,
        "base": "library_intake",

        "personality": personality,

        "cartridges": [],

        "commands": {
            "session": {
                "reset": {
                    "pattern": "^(reset|start over|restart|new session|clear)$",
                    "action": "reset_session",
                },
                "status": {
                    "pattern": "^(status|progress|where am i|summary)$",
                    "action": "show_status",
                },
            },
        },

        "features": {
            "session_intelligence": True,
            "contact_collection": True,
            "deliverables_pipeline": bool(deliverables),
            "session_journal": True,
            "depth_tracking": True,
        },

        "session_policy": {
            "type": "metered",
            "free_turns": max_turns + 4,
            "estimated_turns": est_turns,
        },

        "privacy": {
            "disclosure": "A summary of this session will be available for review.",
            "data_tier": "standard_intake",
            "transcript_available": True,
        },
    }

    if deliverables:
        manifest["deliverables"] = deliverables

    return manifest


# ─── Master.md Generation ────────────────────────────────────

def generate_master_md(header: dict, manifest_md: str) -> str:
    """Transform MANIFEST.md into a master.md protocol file.

    The MANIFEST.md is already rich behavioral specification. We add a
    protocol preamble and lightly reframe it as direct instructions.
    """
    pack_id = header.get("id", "unknown")
    name = header.get("name", pack_id.replace("_", " ").title())
    deliverable = header.get("deliverable", "session_profile")
    est_turns = header.get("estimated_turns", "10-14")

    # Extract key sections from MANIFEST.md
    purpose = _extract_section(manifest_md, "Purpose") or ""
    authorization = _extract_section(manifest_md, "Authorization") or ""
    session_structure = _extract_section(manifest_md, "Session Structure") or ""
    deliverable_section = _extract_section(manifest_md, "Deliverable") or ""
    voice = _extract_section(manifest_md, "Voice") or ""
    formatting = _extract_section(manifest_md, "Formatting Rules") or ""
    web = _extract_section(manifest_md, "Web Potential") or ""

    # Build master.md
    parts = []

    # Protocol header
    parts.append(f"# {name.upper()} — MASTER PROTOCOL\n")
    parts.append(f"**Pack:** {pack_id}")
    parts.append(f"**Deliverable:** {deliverable}")
    parts.append(f"**Estimated turns:** {est_turns}\n")

    # Identity — derived from Purpose + Voice
    parts.append("## Identity\n")
    parts.append(f"You are the {name} session. {purpose.split(chr(10))[0] if purpose else ''}\n")

    # Authorization
    if authorization:
        parts.append("## Authorization\n")
        # Convert third person to second person
        auth_text = authorization
        auth_text = auth_text.replace("The session is authorized to:", "You are authorized to:")
        auth_text = auth_text.replace("The session must not:", "You must not:")
        auth_text = auth_text.replace("The session is authorized to ask:", "You are authorized to ask:")
        auth_text = auth_text.replace("The session", "You")
        parts.append(auth_text + "\n")

    # Session Structure (intake fields, routing rules, completion criteria)
    if session_structure:
        parts.append("## Session Structure\n")
        parts.append(session_structure + "\n")

    # Deliverable
    if deliverable_section:
        parts.append("## Deliverable\n")
        parts.append(deliverable_section + "\n")

    # Voice
    if voice:
        parts.append("## Voice\n")
        voice_text = voice
        voice_text = voice_text.replace("The session's job", "Your job")
        voice_text = voice_text.replace("the session", "you")
        parts.append(voice_text + "\n")

    # Formatting
    if formatting:
        parts.append("## Formatting Rules\n")
        parts.append(formatting + "\n")

    # Web potential (for vault reads/writes context)
    if web:
        parts.append("## Web Potential\n")
        parts.append(web + "\n")

    return "\n".join(parts)


def _extract_section(md: str, heading: str) -> str | None:
    """Extract content under a ## heading from markdown."""
    pattern = rf"## {re.escape(heading)}\s*\n(.*?)(?=\n## |\n---|\Z)"
    match = re.search(pattern, md, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


# ─── Compilation ──────────────────────────────────────────────

def compile_pack(pack_dir: Path, dry_run: bool = False) -> bool:
    """Compile a single library pack into launchable runtime files."""
    header = load_header(pack_dir)
    if not header or header.get("status") != "active":
        return False

    manifest_md = load_manifest_md(pack_dir)
    if not manifest_md:
        log.warning(f"  SKIP {pack_dir.name} — no MANIFEST.md")
        return False

    # Skip if already compiled and MANIFEST.md hasn't changed
    manifest_json_path = pack_dir / "manifest.json"
    master_md_path = pack_dir / "master.md"
    manifest_md_path = pack_dir / "MANIFEST.md"

    if (manifest_json_path.exists() and master_md_path.exists()
            and manifest_json_path.stat().st_mtime > manifest_md_path.stat().st_mtime):
        log.info(f"  SKIP {pack_dir.name} — already compiled (up to date)")
        return False

    # Generate
    manifest_json = generate_manifest_json(header, manifest_md)
    master_md = generate_master_md(header, manifest_md)

    if dry_run:
        log.info(f"  DRY  {pack_dir.name}")
        log.info(f"       manifest.json: {len(json.dumps(manifest_json))} bytes")
        log.info(f"       master.md: {len(master_md)} bytes")
        return True

    # Write
    manifest_json_path.write_text(json.dumps(manifest_json, indent=2) + "\n")
    master_md_path.write_text(master_md)

    log.info(f"  OK   {pack_dir.name}")
    return True


def compile_all(category_filter: str = None, pack_filter: str = None, dry_run: bool = False):
    """Compile all active library packs (or filtered subset)."""
    if not LIBRARY_DIR.exists():
        log.error(f"Library directory not found: {LIBRARY_DIR}")
        return

    compiled = skipped = 0

    for cat_dir in sorted(LIBRARY_DIR.iterdir()):
        if not cat_dir.is_dir():
            continue
        if category_filter and cat_dir.name != category_filter:
            continue

        for pack_dir in sorted(cat_dir.iterdir()):
            if not pack_dir.is_dir():
                continue
            if pack_filter and pack_dir.name != pack_filter:
                continue

            if compile_pack(pack_dir, dry_run=dry_run):
                compiled += 1
            else:
                skipped += 1

    log.info(f"\n{'DRY RUN — ' if dry_run else ''}Compiled: {compiled}, Skipped: {skipped}")


# ─── CLI ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Compile library manifests into launchable packs")
    parser.add_argument("--pack", "-p", default=None, help="Compile a single pack by ID")
    parser.add_argument("--category", "-c", default=None, help="Compile all packs in a category")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Preview without writing")
    parser.add_argument("--force", "-f", action="store_true", help="Recompile even if up to date")
    args = parser.parse_args()

    log.info("Pack Compiler — library → runtime\n")

    compile_all(
        category_filter=args.category,
        pack_filter=args.pack,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
