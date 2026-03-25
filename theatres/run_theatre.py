#!/usr/bin/env python3
"""
theatres/run_theatre.py — CLI entry point for running a WORLD13 theatre.

Usage:
    python3 theatres/run_theatre.py --theatre enlightened_duck
    python3 theatres/run_theatre.py --theatre enlightened_duck --dry-run
    python3 theatres/run_theatre.py --list
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from theatres.runner import TheatreRunner
from theatres.loader import load_theatre


def list_theatres() -> list[str]:
    """Return names of all available theatres."""
    theatre_dir = os.path.dirname(os.path.abspath(__file__))
    theatres = []
    for d in os.listdir(theatre_dir):
        if d.startswith("_") or d.startswith("."):
            continue
        manifest = os.path.join(theatre_dir, d, "manifest.yaml")
        if os.path.exists(manifest):
            theatres.append(d)
    return sorted(theatres)


async def main():
    parser = argparse.ArgumentParser(description="Run a WORLD13 simulation theatre")
    parser.add_argument("--theatre", type=str, help="Theatre name to run")
    parser.add_argument("--list", action="store_true", help="List available theatres")
    parser.add_argument("--dry-run", action="store_true", help="Validate manifest without running sessions")
    args = parser.parse_args()

    if args.list:
        theatres = list_theatres()
        print(f"\nAvailable theatres ({len(theatres)}):")
        for t in theatres:
            print(f"  {t}")
        return

    if not args.theatre:
        parser.print_help()
        return

    print(f"\nWORLD13 Theatre: {args.theatre}")
    print("=" * 60)

    if args.dry_run:
        manifest = load_theatre(args.theatre)
        print(f"  Manifest loaded. {len(manifest.agents)} agents defined.")
        print(f"  Pack: {manifest.pack}")
        print(f"  Sessions per agent: {manifest.sessions_per_agent}")
        print(f"  Agents:")
        for a in manifest.agents:
            print(f"    {a.name:16s} P{a.plane} {a.primary_arch} K₀:{a.k0:.1f} λ:{a.lambda_coeff:.1f} {a.cycle_phase}")
        print(f"  Dry run complete — no sessions executed.")
        return

    runner = TheatreRunner(args.theatre)
    results = await runner.run()

    print(f"\n{'=' * 60}")
    print(f"Theatre complete: {results['agents_run']} agents, {results['duration_seconds']:.1f}s")
    if results.get("report_path"):
        print(f"Report: {results['report_path']}")


if __name__ == "__main__":
    asyncio.run(main())
