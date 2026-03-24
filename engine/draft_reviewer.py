"""
draft_reviewer.py — Review drafted packs and promote to active.

Usage:
  python engine/draft_reviewer.py list              # list all drafts
  python engine/draft_reviewer.py show {pack_id}    # print MANIFEST.md
  python engine/draft_reviewer.py promote {pack_id} # move to protocols/packs/
  python engine/draft_reviewer.py report            # summary stats
"""

import json
import shutil
import sys
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
LIBRARY_DIR = BASE_DIR / "protocols" / "library"
PACKS_DIR = BASE_DIR / "protocols" / "packs"


def list_drafts() -> list[dict]:
    drafts = []
    for cat_dir in sorted(LIBRARY_DIR.iterdir()):
        if not cat_dir.is_dir():
            continue
        for pack_dir in sorted(cat_dir.iterdir()):
            if not pack_dir.is_dir():
                continue
            h = pack_dir / "header.yaml"
            if h.exists():
                data = yaml.safe_load(h.read_text())
                if data and data.get("status") == "draft":
                    drafts.append(data)
    return drafts


def show_draft(pack_id: str):
    for cat_dir in LIBRARY_DIR.iterdir():
        if not cat_dir.is_dir():
            continue
        pack_dir = cat_dir / pack_id
        if pack_dir.is_dir():
            m = pack_dir / "MANIFEST.md"
            if m.exists():
                print(m.read_text())
                return
    print(f"Draft not found: {pack_id}")


def promote_draft(pack_id: str):
    for cat_dir in LIBRARY_DIR.iterdir():
        if not cat_dir.is_dir():
            continue
        pack_dir = cat_dir / pack_id
        if pack_dir.is_dir():
            h = pack_dir / "header.yaml"
            if h.exists():
                data = yaml.safe_load(h.read_text())
                if not data or data.get("status") != "draft":
                    print(f"{pack_id} is not a draft (status: {data.get('status') if data else 'unknown'})")
                    return
                # Update status to active
                data["status"] = "active"
                data.pop("drafted_by", None)
                data.pop("draft_date", None)
                data.pop("requires_review", None)
                # Copy to protocols/packs/
                dest = PACKS_DIR / pack_id
                shutil.copytree(pack_dir, dest)
                with open(dest / "header.yaml", "w") as f:
                    yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
                # Update manifest.json status
                mj = dest / "manifest.json"
                if mj.exists():
                    mdata = json.loads(mj.read_text())
                    mdata["status"] = "active"
                    mj.write_text(json.dumps(mdata, indent=2))
                print(f"Promoted: {pack_id} -> protocols/packs/{pack_id}/")
                return
    print(f"Draft not found: {pack_id}")


def report():
    drafts = list_drafts()
    by_cat: dict[str, int] = {}
    requires_review = []
    for d in drafts:
        cat = d.get("category", "unknown")
        by_cat[cat] = by_cat.get(cat, 0) + 1
        if d.get("requires_review"):
            requires_review.append(d.get("pack_id", "unknown"))
    print(f"\nDraft Pack Report — {len(drafts)} total drafts\n")
    print(f"{'Category':<22} {'Drafts':>6}")
    print("---" * 10)
    for cat, count in sorted(by_cat.items()):
        print(f"  {cat:<20} {count:>6}")
    if requires_review:
        print(
            f"\n[WARNING] Requires domain review before promotion ({len(requires_review)}):"
        )
        for p in requires_review:
            print(f"  - {p}")
    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
    elif sys.argv[1] == "list":
        for d in list_drafts():
            flag = " [!]" if d.get("requires_review") else ""
            print(
                f"  {d.get('pack_id', 'unknown'):<35} {d.get('category', ''):<20}{flag}"
            )
    elif sys.argv[1] == "show" and len(sys.argv) > 2:
        show_draft(sys.argv[2])
    elif sys.argv[1] == "promote" and len(sys.argv) > 2:
        promote_draft(sys.argv[2])
    elif sys.argv[1] == "report":
        report()
    else:
        print(__doc__)
