#!/usr/bin/env python3
"""Run the Hormuz theatre."""

import sys, os, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass

from theatres.hormuz.runner import HormuzRunner


async def main():
    runner = HormuzRunner()
    results = await runner.run()

    print(f"\n{'═'*55}")
    print(f"HORMUZ — Complete")
    print(f"  Ticks:          {results['ticks']}")
    print(f"  Sessions:       {results['total_sessions']}")
    print(f"  Final mean K:   {results['mean_k_final']:.2f}")
    print()
    print("  Final escalation pressures:")
    for a in sorted(results["agent_states"], key=lambda x: x["k_current"], reverse=True):
        print(f"  {a['name']:<30} K:{a['k_current']:.2f}")
    print(f"\n  Chronicle: {results['chronicle_path']}")
    print(f"{'═'*55}\n")


if __name__ == "__main__":
    asyncio.run(main())
