#!/usr/bin/env python3
"""
theatres/marriage/run.py — CLI entry point for the Marriage Theatre.

Usage:
    python3 theatres/marriage/run.py
    python3 theatres/marriage/run.py --dry-run
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from theatres.marriage.runner import run_marriage_theatre
from theatres.marriage.analyzer import analyze_marriage
from theatres.marriage.reporter import generate_marriage_report


def main():
    parser = argparse.ArgumentParser(description="Run the WORLD13 Marriage Theatre")
    parser.add_argument("--dry-run", action="store_true", help="Validate manifest without running")
    args = parser.parse_args()

    print("\nWORLD13 Theatre: marriage")
    print("=" * 60)

    results = run_marriage_theatre(dry_run=args.dry_run)

    if args.dry_run:
        return

    print(f"\n{'=' * 60}")
    print("Running analysis...")
    analysis = analyze_marriage(results)

    report_dir = "data/theatres/marriage/reports"
    report_path = generate_marriage_report(results, analysis, report_dir)

    couples = results["couples"]
    renewed = [n for n, c in couples.items() if c["is_renewed"]]
    locked = [n for n, c in couples.items() if c["is_pattern_locked"]]
    active = [n for n, c in couples.items() if not c["is_renewed"] and not c["is_pattern_locked"]]

    print(f"\n{'=' * 60}")
    print(f"Theatre complete: {len(couples)} couples, {results['sessions_per_couple']} sessions each")
    print(f"Duration: {results['duration_seconds']:.1f}s")
    print()
    print(f"  RENEWED ({len(renewed)}):")
    for name in renewed:
        c = couples[name]
        print(f"    * {name:24s} K:{c['k_final']:.4f} C:{c['coherence_final']:.3f} session:{c['renewal_session']}")
    print()
    print(f"  PATTERN LOCKED ({len(locked)}):")
    for name in locked:
        c = couples[name]
        print(f"    X {name:24s} K:{c['k_final']:.2f} eff-lambda:{c['effective_lambda_final']:.2f} session:{c['pattern_lock_session']}")
    print()
    print(f"  ACTIVE ({len(active)}):")
    for name in active:
        c = couples[name]
        print(f"    - {name:24s} K:{c['k_final']:.2f} eff-lambda:{c['effective_lambda_final']:.2f} {c['risk_status']}")
    print()

    # Gottman test
    ght = analysis.get("gottman_hypothesis_test", {})
    if "finding" in ght:
        print(f"  Gottman hypothesis: {ght['finding']}")

    print(f"\n  Report: {report_path}")


if __name__ == "__main__":
    main()
