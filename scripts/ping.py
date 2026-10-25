"""Integration check: exactly ONE paid call per model (4 calls total).

    python -m scripts.ping            # all four models
    python -m scripts.ping opus jev   # only some models
"""
from __future__ import annotations

import asyncio
import json
import sys
import time

import httpx

from backend import config
from backend.adapters import build_adapters
from backend.cube import SOLVED, apply_moves, faces


async def main(keys):
    if not config.OPENROUTER_API_KEY:
        sys.exit("OPENROUTER_API_KEY is not set in .env")
    state = apply_moves(SOLVED, ["R", "U"])  # solved by U' R'
    payload = {"cube_facelets": state, "faces": faces(state), "recent_moves": ["R", "U"],
               "moves_made": 0, "moves_remaining": config.MOVE_LIMIT}
    async with httpx.AsyncClient() as client:
        adapters = build_adapters(True, client, config.SEED)
        for key in keys:
            ad = adapters[key]
            t0 = time.perf_counter()
            res = await ad.choose(payload)
            dt = time.perf_counter() - t0
            ok = "OK " if res["move"] else "ERR"
            print(f"[{ok}] {ad.model['name']:<30} {ad.model['id']:<34} {dt:6.2f}s  move={res['move']}  "
                  f"conf={res['confidence']}  cost={res['cost']}")
            if res["error"]:
                print("      error:", res["error"])
                print("      raw:  ", (res["raw"] or "")[:300])
    print("\nExpected best first move: U' (then R'). 4 calls used.")


if __name__ == "__main__":
    wanted = sys.argv[1:] or [m["key"] for m in config.MODELS]
    asyncio.run(main(wanted))
