#!/usr/bin/env python3
"""
13TMOS Vault CLI — Query the Dimensional Memory

Eight independent retrieval angles. Burial is architecturally impossible.

Usage:
    python engine/vault_cli.py list
    python engine/vault_cli.py list --pack legal_intake
    python engine/vault_cli.py get --session abc123
    python engine/vault_cli.py query --pack legal_intake
    python engine/vault_cli.py query --user local --type case_file
    python engine/vault_cli.py query --fields matter_type=personal_injury
    python engine/vault_cli.py query --content "car accident"
    python engine/vault_cli.py inherit --session abc123 --for conflict_check
"""
import argparse
import json
import sys
from pathlib import Path

# Add engine to path
ENGINE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE_DIR))

from local_vault import LocalVault

LINE = "─" * 53


def cmd_list(args, vault: LocalVault):
    """List all vault records."""
    summaries = vault.list_sessions(
        pack_id=args.pack,
        user_id=args.user,
    )

    if args.json:
        print(json.dumps(summaries, indent=2))
        return

    if not summaries:
        print("\nVAULT — empty")
        print(LINE)
        print("No records found.")
        print()
        return

    print(f"\nVAULT — {len(summaries)} record{'s' if len(summaries) != 1 else ''}")
    print(LINE)
    print(f"{'session':<12} {'pack':<20} {'user':<8} {'date':<12} {'type'}")
    for s in summaries:
        sid = s["session"][:8] if len(s["session"]) > 8 else s["session"]
        print(f"{sid:<12} {s['pack']:<20} {s['user']:<8} {s['date']:<12} {s['type']}")
    print()


def cmd_get(args, vault: LocalVault):
    """Get a single vault record by session ID."""
    if not args.session:
        print("Error: --session required")
        sys.exit(1)

    record = vault.get(args.session)
    if not record:
        print(f"No record found for session: {args.session}")
        sys.exit(1)

    if args.json:
        print(json.dumps(record, indent=2, default=str))
        return

    print(f"\nVAULT RECORD — {args.session[:8]}")
    print(LINE)
    print(f"  pack:     {record.get('pack', '?')}")
    print(f"  user:     {record.get('user', '?')}")
    print(f"  date:     {record.get('date', '?')}")
    print(f"  type:     {record.get('type', '?')}")
    print(f"  manifest: {record.get('manifest', '?')}")
    print()

    fields = record.get("fields", {})
    if fields:
        print("  Fields:")
        for k, v in fields.items():
            print(f"    {k}: {v}")
        print()

    content = record.get("content", {})
    if isinstance(content, dict):
        summary = content.get("summary", "")
        if summary:
            print(f"  Summary: {summary}")
        transcript = content.get("transcript", [])
        if transcript:
            print(f"  Transcript: {len(transcript)} exchanges")
    elif isinstance(content, str):
        preview = content[:200] + "..." if len(content) > 200 else content
        print(f"  Content: {preview}")
    print()


def cmd_query(args, vault: LocalVault):
    """Query vault by dimensions."""
    dimensions = {}
    if args.pack:
        dimensions["pack"] = args.pack
    if args.user:
        dimensions["user"] = args.user
    if args.date:
        dimensions["date"] = args.date
    if args.type:
        dimensions["type"] = args.type
    if args.session:
        dimensions["session"] = args.session
    if args.manifest:
        dimensions["manifest"] = args.manifest
    if args.content:
        dimensions["content"] = args.content
    if args.fields:
        field_dict = {}
        for pair in args.fields:
            if "=" in pair:
                k, v = pair.split("=", 1)
                field_dict[k.strip()] = v.strip()
        if field_dict:
            dimensions["fields"] = field_dict

    if not dimensions:
        print("Error: provide at least one dimension filter")
        print("  --pack, --user, --date, --type, --session, --manifest, --content, --fields")
        sys.exit(1)

    results = vault.query(dimensions)

    if args.json:
        print(json.dumps(results, indent=2, default=str))
        return

    # Build label from provided dimensions
    dim_label = ", ".join(f"{k}: {v}" for k, v in dimensions.items()
                          if k != "fields")
    if "fields" in dimensions:
        for fk, fv in dimensions["fields"].items():
            dim_label += f", {fk}={fv}"

    print(f"\nVAULT QUERY — {dim_label}")
    print(LINE)

    if not results:
        print("0 records found")
        print()
        return

    print(f"{len(results)} record{'s' if len(results) != 1 else ''} found")
    print()

    for i, record in enumerate(results, 1):
        sid = record.get("session", "?")
        sid_short = sid[:8] if len(sid) > 8 else sid
        print(f"[{i}] session: {sid_short} | date: {record.get('date', '?')} | type: {record.get('type', '?')}")

        fields = record.get("fields", {})
        if fields:
            for k, v in fields.items():
                print(f"    {k}: {v}")
        print()


def cmd_inherit(args, vault: LocalVault):
    """Show inheritance context for a session transition."""
    if not args.session:
        print("Error: --session required")
        sys.exit(1)

    target = getattr(args, "for_pack", None) or "unknown"

    result = vault.inherit(args.session, target)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return

    print(f"\nVAULT INHERITANCE — {args.session[:8]} → {target}")
    print(LINE)
    print(f"  user:            {result['user_id']}")
    print(f"  prior sessions:  {len(result['prior_sessions'])}")
    print()

    if result["prior_sessions"]:
        print("  Session History:")
        for ps in result["prior_sessions"]:
            sid = ps.get("session_id", "?")
            sid_short = sid[:8] if len(sid) > 8 else sid
            print(f"    [{ps.get('date', '?')}] {ps.get('pack', '?')} ({sid_short}) — {ps.get('type', '?')}")
        print()

    if result["field_index"]:
        print("  Field Index (merged, last-write wins):")
        for k, v in result["field_index"].items():
            print(f"    {k}: {v}")
    else:
        print("  Field Index: (empty)")
    print()


def cmd_audit(args, vault: LocalVault):
    """Run compliance audit."""
    from auditor import SessionAuditor
    from manifest_archive import ManifestArchive

    archive = ManifestArchive()
    auditor = SessionAuditor(vault, manifest_archive=archive)

    # Determine scope
    if args.session:
        verdicts = [auditor.audit_session(args.session)]
        scope_desc = f"session {args.session[:8]}"
    else:
        verdicts = auditor.audit_range(
            start_date=args.start,
            end_date=args.end,
            pack_id=args.pack,
            user_id=args.user,
        )
        parts = []
        if args.start:
            parts.append(f"from {args.start}")
        if args.end:
            parts.append(f"to {args.end}")
        if args.pack:
            parts.append(f"pack: {args.pack}")
        if args.user:
            parts.append(f"user: {args.user}")
        scope_desc = ", ".join(parts) if parts else "all sessions"

    if args.json:
        print(json.dumps(verdicts, indent=2, default=str))
        return

    scope = {"description": scope_desc}
    report_text, report_id, vault_hash = auditor.generate_report(
        verdicts, scope, auditor="CLI"
    )

    # Write report
    path = auditor.write_report(report_text, report_id)

    print()
    print(report_text)
    print()
    print(f"Report written: {path}")
    print()


def cmd_verify(args, vault: LocalVault):
    """Verify vault hash for tamper check."""
    from auditor import SessionAuditor

    auditor = SessionAuditor(vault)

    # Get all sessions in range
    sessions = vault.list_sessions()

    if args.start or args.end:
        sessions = [s for s in sessions
                    if (not args.start or s.get("date", "") >= args.start)
                    and (not args.end or s.get("date", "") <= args.end)]

    session_ids = [s["session"] for s in sessions]
    computed = auditor.compute_vault_hash(session_ids)

    expected = args.hash

    print(f"\nVAULT INTEGRITY CHECK")
    print(LINE)
    print(f"Sessions: {len(session_ids)}")
    print(f"Computed: {computed}")
    print(f"Expected: {expected}")
    print()

    if computed == expected:
        print("MATCH — vault records unmodified since audit.")
    else:
        print("MISMATCH — vault records have been modified since audit.")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="13TMOS Vault CLI — dimensional memory query",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON")

    sub = parser.add_subparsers(dest="command")

    # list
    p_list = sub.add_parser("list", help="List all vault records")
    p_list.add_argument("--pack", help="Filter by pack ID")
    p_list.add_argument("--user", help="Filter by user ID")

    # get
    p_get = sub.add_parser("get", help="Get a single record by session ID")
    p_get.add_argument("--session", "-s", required=True, help="Session ID")

    # query
    p_query = sub.add_parser("query", help="Query by dimensions")
    p_query.add_argument("--pack", help="Pack ID (exact)")
    p_query.add_argument("--user", help="User ID (exact)")
    p_query.add_argument("--date", help="Date (exact, YYYY-MM-DD)")
    p_query.add_argument("--type", help="Deliverable type (exact)")
    p_query.add_argument("--session", "-s", help="Session ID (exact)")
    p_query.add_argument("--manifest", help="Manifest version (exact)")
    p_query.add_argument("--content", help="Content substring (case-insensitive)")
    p_query.add_argument("--fields", nargs="+", help="Field filters: key=value ...")

    # inherit
    p_inherit = sub.add_parser("inherit", help="Show inheritance context for session transition")
    p_inherit.add_argument("--session", "-s", required=True, help="Source session ID")
    p_inherit.add_argument("--for", dest="for_pack", required=True, help="Target pack ID")

    # audit
    p_audit = sub.add_parser("audit", help="Run compliance audit")
    p_audit.add_argument("--start", help="Start date (YYYY-MM-DD)")
    p_audit.add_argument("--end", help="End date (YYYY-MM-DD)")
    p_audit.add_argument("--pack", help="Filter by pack ID")
    p_audit.add_argument("--user", help="Filter by user ID")
    p_audit.add_argument("--session", "-s", help="Audit a specific session")

    # verify
    p_verify = sub.add_parser("verify", help="Verify vault hash (tamper check)")
    p_verify.add_argument("--start", help="Start date (YYYY-MM-DD)")
    p_verify.add_argument("--end", help="End date (YYYY-MM-DD)")
    p_verify.add_argument("--hash", required=True, help="Expected vault hash")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    vault = LocalVault()

    if args.command == "list":
        cmd_list(args, vault)
    elif args.command == "get":
        cmd_get(args, vault)
    elif args.command == "query":
        cmd_query(args, vault)
    elif args.command == "inherit":
        cmd_inherit(args, vault)
    elif args.command == "audit":
        cmd_audit(args, vault)
    elif args.command == "verify":
        cmd_verify(args, vault)


if __name__ == "__main__":
    main()
