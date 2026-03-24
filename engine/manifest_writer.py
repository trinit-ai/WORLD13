"""
13TMOS Manifest Writer — Deterministic Pack Manifest Generator

Takes the completed field dict from a Pack Builder session and writes:
  - {pack_id}/MANIFEST.md — full behavioral manifest
  - {pack_id}/header.yaml — lightweight header for progressive disclosure

Same inputs, same output. No model creativity in the manifest format.
"""
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("13tmos.manifest_writer")

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "output"
LIBRARY_DIR = ROOT_DIR / "protocols" / "library"
INDEX_PATH = LIBRARY_DIR / "index.yaml"


def _format_list(items: list, prefix: str = "") -> str:
    """Format a list as markdown bullet points with optional prefix."""
    if not items:
        return "- (none)\n"
    lines = []
    for item in items:
        text = str(item).strip()
        if prefix and not text.lower().startswith(prefix.lower()):
            text = f"{prefix}{text}"
        lines.append(f"- {text}")
    return "\n".join(lines) + "\n"


def _format_intake_table(fields: list) -> str:
    """Format intake fields as a markdown table."""
    if not fields:
        return "| (none) | | |\n"
    lines = [
        "| Field | Type | Required |",
        "|-------|------|----------|",
    ]
    for field in fields:
        if isinstance(field, dict):
            name = field.get("name", field.get("field", ""))
            ftype = field.get("type", "string")
            req = field.get("required", True)
            req_str = "required" if req else "optional"
        elif isinstance(field, str):
            # Parse "field_name (type, required)" format
            name = field
            ftype = "string"
            req_str = "required"
        else:
            continue
        lines.append(f"| {name} | {ftype} | {req_str} |")
    return "\n".join(lines) + "\n"


def _safe_str(value) -> str:
    """Convert a value to a safe string representation."""
    if value is None:
        return "(none)"
    if isinstance(value, list):
        if not value:
            return "(none)"
        return ", ".join(str(v) for v in value)
    return str(value)


def write_manifest(fields: dict, output_dir: str = None) -> tuple[str, str]:
    """Write MANIFEST.md and header.yaml from completed Pack Builder fields.

    Args:
        fields: Dict of all captured fields from the Pack Builder session.
        output_dir: Directory to write to. Defaults to output/.

    Returns:
        Tuple of (manifest_path, header_path) as strings.
    """
    out_base = Path(output_dir) if output_dir else OUTPUT_DIR
    pack_id = fields.get("pack_id", "unknown_pack")
    pack_dir = out_base / pack_id
    pack_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    # ── Build MANIFEST.md ────────────────────────────────────
    manifest_lines = [
        f"# {fields.get('pack_name', pack_id)}",
        "",
        f"**Pack ID:** {pack_id}",
        f"**Category:** {fields.get('category', 'unknown')}",
        f"**Version:** 1.0",
        f"**Author:** {fields.get('domain_expert', 'unknown')}",
        f"**Status:** development",
        f"**Created:** {date_str}",
        "",
        "## Purpose",
        "",
        fields.get("purpose", "(no purpose statement)"),
        "",
        "## Authorization",
        "",
        "### Authorized Actions",
        _format_list(fields.get("authorized_actions", []),
                     prefix="The session is authorized to "),
        "",
        "### Prohibited Actions",
        _format_list(fields.get("prohibited_actions", []),
                     prefix="The session must not "),
        "",
        "### Authorized Questions",
        _format_list(fields.get("authorized_questions", []),
                     prefix="The session is authorized to ask "),
        "",
        "## Session Structure",
        "",
        "### Intake Fields",
        _format_intake_table(fields.get("intake_fields", [])),
        "",
        "### Routing Rules",
        _format_list(fields.get("routing_rules", [])),
        "",
        "### Completion Criteria",
        _format_list(fields.get("completion_criteria", [])),
        "",
        f"### Estimated Turns",
        fields.get("estimated_turns", "unknown"),
        "",
        "## Deliverable",
        "",
        f"**Type:** {fields.get('deliverable_type', 'unknown')}",
        f"**Format:** {fields.get('deliverable_format', 'both')}",
        "",
        "### Required Fields",
        _format_list(fields.get("deliverable_fields", [])),
        "",
        "## Pack Web",
        "",
        "### Upstream Packs",
        _safe_str(fields.get("upstream_packs")),
        "",
        "### Downstream Packs",
        _safe_str(fields.get("downstream_packs")),
        "",
        "### Vault Reads",
        _safe_str(fields.get("vault_reads")),
        "",
        "### Vault Writes",
        _safe_str(fields.get("vault_writes")),
        "",
        "---",
        f"*Generated by Pack Builder Pack v1.0 — {date_str}*",
        f"*13TMOS local runtime — Robert C. Ventura, TMOS13, LLC*",
    ]

    manifest_path = pack_dir / "MANIFEST.md"
    manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    # ── Build header.yaml ────────────────────────────────────
    # Construct purpose as a single-line description
    purpose = fields.get("purpose", "")
    if len(purpose) > 80:
        purpose = purpose[:77] + "..."

    header_lines = [
        f"id: {pack_id}",
        f"name: {fields.get('pack_name', pack_id)}",
        f"category: {fields.get('category', 'unknown')}",
        f"status: development",
        f"description: >",
        f"  {fields.get('purpose', '(no purpose statement)')}",
        f"deliverable: {fields.get('deliverable_type', 'unknown')}",
        f"estimated_turns: {fields.get('estimated_turns', 'unknown')}",
        f"version: \"1.0\"",
        f"author: {fields.get('domain_expert', 'unknown')}",
    ]

    header_path = pack_dir / "header.yaml"
    header_path.write_text("\n".join(header_lines) + "\n", encoding="utf-8")

    logger.info("Manifest written: %s", pack_dir)
    return str(manifest_path), str(header_path)


def promote_to_library(pack_id: str, category: str) -> bool:
    """Copy a generated pack from output/ to protocols/library/{category}/{pack_id}/.

    Sets status to 'development' — human reviews and changes to 'active'
    before promote() copies to protocols/packs/.

    Also updates library/index.yaml with the new entry.

    Args:
        pack_id: The pack identifier.
        category: The library category to place it in.

    Returns:
        True on success, False on failure.
    """
    source = OUTPUT_DIR / pack_id
    if not source.exists():
        logger.error("promote_to_library: source not found: %s", source)
        return False

    if not (source / "MANIFEST.md").exists():
        logger.error("promote_to_library: no MANIFEST.md in %s", source)
        return False

    dest = LIBRARY_DIR / category / pack_id
    if dest.exists():
        # Overwrite existing (might be a stub being replaced)
        shutil.rmtree(dest)

    shutil.copytree(source, dest)
    logger.info("Promoted to library: %s → %s", source, dest)

    # Update index.yaml
    _update_index(pack_id, category, status="development")

    return True


def _update_index(pack_id: str, category: str, status: str = "development"):
    """Update library/index.yaml with a new or changed pack entry.

    Reads the current index, finds the category section, adds or updates
    the pack entry, recalculates counts, and writes back.
    """
    if not INDEX_PATH.exists():
        logger.warning("index.yaml not found, skipping index update")
        return

    lines = INDEX_PATH.read_text().splitlines()
    new_lines = []
    in_target_category = False
    in_packs_section = False
    pack_exists = False
    category_found = False
    i = 0

    while i < len(lines):
        line = lines[i]

        # Detect category header
        if line.strip().startswith(f"{category}:") and not line.strip().startswith("categories:"):
            in_target_category = True
            category_found = True
            new_lines.append(line)
            i += 1
            continue

        # Detect another category starting (end of our target)
        if in_target_category and not line.startswith("    ") and not line.startswith("  ") and line.strip() and not line.startswith("#"):
            if line.strip().endswith(":") and not line.strip().startswith("-"):
                # Add pack entry before leaving category if not found
                if not pack_exists and in_packs_section:
                    new_lines.append(f"    - id: {pack_id}")
                    new_lines.append(f"      status: {status}")
                    new_lines.append(f"      description: ")
                in_target_category = False
                in_packs_section = False

        # Detect packs: section within our category
        if in_target_category and line.strip() == "packs:":
            in_packs_section = True

        # Check if this pack already exists in the list
        if in_packs_section and f"id: {pack_id}" in line:
            pack_exists = True
            new_lines.append(line)
            i += 1
            # Update the status line
            if i < len(lines) and "status:" in lines[i]:
                new_lines.append(f"      status: {status}")
                i += 1
            continue

        new_lines.append(line)
        i += 1

    # If we reached end of file while still in category, add pack
    if in_target_category and not pack_exists and in_packs_section:
        new_lines.append(f"    - id: {pack_id}")
        new_lines.append(f"      status: {status}")
        new_lines.append(f"      description: ")

    INDEX_PATH.write_text("\n".join(new_lines) + "\n")

    # Recalculate header counts
    _refresh_index_counts()


def _refresh_index_counts():
    """Recalculate the total/active/stubs counts in index.yaml header."""
    if not LIBRARY_DIR.exists():
        return

    active = 0
    stubs = 0
    for cat_dir in LIBRARY_DIR.iterdir():
        if not cat_dir.is_dir():
            continue
        for pack_dir in cat_dir.iterdir():
            if not pack_dir.is_dir():
                continue
            if (pack_dir / "manifest.json").exists():
                active += 1
            elif (pack_dir / "header.yaml").exists() or (pack_dir / "MANIFEST.md").exists():
                stubs += 1

    if not INDEX_PATH.exists():
        return

    lines = INDEX_PATH.read_text().splitlines()
    new_lines = []
    for line in lines:
        if line.startswith("# Total packs:"):
            new_lines.append(f"# Total packs: {active + stubs}")
        elif line.startswith("# Active:"):
            new_lines.append(f"# Active: {active}")
        elif line.startswith("# Stubs:"):
            new_lines.append(f"# Stubs: {stubs}")
        else:
            new_lines.append(line)
    INDEX_PATH.write_text("\n".join(new_lines) + "\n")
