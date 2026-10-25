"""Headless benchmark run (same engine and policy as the web UI).

    python -m scripts.run_cli mock               # offline, 0 API calls
    python -m scripts.run_cli budget             # live, hard cap MAX_CALLS (default 64)
    python -m scripts.run_cli budget --max-calls 40 --seed 7
"""
from __future__ import annotations

import argparse
import asyncio

from backend import config
from backend.benchmark import Run
from backend.stats import make_report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("profile", choices=list(config.PROFILES))
    ap.add_argument("--seed", type=int)
    ap.add_argument("--max-calls", type=int)
    ap.add_argument("--move-limit", type=int)
    a = ap.parse_args()
    run = Run(a.profile, seed=a.seed, max_calls=a.max_calls, move_limit=a.move_limit)
    data = asyncio.run(run.execute())
    print(make_report(data))
    print(f"\nSaved results/run_{data['id']}.json and .md")


if __name__ == "__main__":
    main()
