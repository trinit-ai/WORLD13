#!/usr/bin/env python3
"""Run the Eden theatre."""

import sys, os, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass

from theatres.eden.runner import EdenRunner


async def main():
    runner = EdenRunner()
    results = await runner.run()

    print(f"\n{'═'*50}")
    print(f"EDEN — Complete")
    print(f"  Ticks:       {results['ticks']}")
    print(f"  Sessions:    {results['total_sessions']}")
    print(f"  Births:      {results['total_births']}")
    print(f"  Population:  {results['population_final']}")
    print(f"  Generations: {results['generations']}")
    if results['liberations']:
        for lib in results['liberations']:
            print(f"  ★ {lib['name']} liberated at tick {lib['tick']}")
    print(f"  Chronicle:   {results['chronicle_path']}")
    print(f"{'═'*50}\n")


if __name__ == "__main__":
    asyncio.run(main())
