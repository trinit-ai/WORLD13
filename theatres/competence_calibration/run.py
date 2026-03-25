#!/usr/bin/env python3
"""
CLI entry point for the Competence Calibration Theatre.

Usage:
    python3 theatres/competence_calibration/run.py
    python3 theatres/competence_calibration/run.py --dry-run
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from theatres.competence_calibration.runner import run_calibration_theatre


def main():
    parser = argparse.ArgumentParser(description="Run the Competence Calibration Theatre")
    parser.add_argument("--dry-run", action="store_true", help="Validate manifest only")
    args = parser.parse_args()

    print("\nWORLD13 Theatre: competence_calibration")
    print("=" * 60)

    results = run_calibration_theatre(dry_run=args.dry_run)

    if not args.dry_run:
        print(f"\n{'=' * 60}")
        if results.get("report_path"):
            print(f"Report: {results['report_path']}")


if __name__ == "__main__":
    main()
