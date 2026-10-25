"""Benchmark runner: same puzzles, same rules, same budget policy for every model.

Scheduling is round-based: in each round every unfinished trial makes exactly one
move (in parallel). Before a round starts the runner checks the call budget; if
it cannot pay for one call per unfinished trial, the run stops there, so every
unfinished trial has had exactly the same number of turns (fair under a budget).
Round 1 probes each model with one call before the rest, so a wrong model id or
schema costs one call instead of one per puzzle.
"""
from __future__ import annotations

import asyncio
import json
import random
import time
from datetime import datetime

import httpx

from . import config
from .adapters import build_adapters
from .cube import SOLVED, apply_move, apply_moves, faces, is_solved, random_scramble
from .solver import shortest_solution
from .stats import make_report, summarize

EXTENSION_SEARCH_DEPTH = 8


def make_puzzles(sets, seed: int) -> list[dict]:
    rng = random.Random(seed)
    puzzles = []
    for set_name, count, lo, hi in sets:
        for _ in range(count):
            length = rng.randint(lo, hi)
            for _attempt in range(200):
                scramble = random_scramble(length, rng)
                state = apply_moves(SOLVED, scramble)
                if set_name == "extension":
                    sol = shortest_solution(state, EXTENSION_SEARCH_DEPTH)
                    break
                sol = shortest_solution(state, hi + 1)
                if sol is not None and len(sol) == length:  # true distance equals scramble length
                    break
            puzzles.append({
                "id": f"P{len(puzzles) + 1}",
                "set": set_name,
                "scramble": scramble,
                "state": state,
                "optimal": None if sol is None else len(sol),
                "optimal_solution": sol,
                "upper_bound": len(scramble),
            })
    return puzzles


class Budget:
    def __init__(self, limit):
        self.limit = limit
        self.used = 0

    @property
    def remaining(self):
        return float("inf") if self.limit is None else self.limit - self.used

    def take(self) -> bool:
        if self.remaining < 1:
            return False
        self.used += 1
        return True


class Run:
    def __init__(self, profile: str, seed: int | None = None, max_calls: int | None = None,
                 move_limit: int | None = None):
        prof = config.PROFILES[profile]
        self.live = prof["live"]
        self.seed = config.SEED if seed is None else seed
        self.move_limit = move_limit or config.MOVE_LIMIT
        self.budget = Budget(max_calls if max_calls is not None else prof["max_calls"])
        self.stop_requested = False
        self.disabled: dict[str, str] = {}
        self.t0 = None
        self.sem = asyncio.Semaphore(config.CONCURRENCY)
        puzzles = make_puzzles(prof["sets"], self.seed)
        self.data = {
            "id": datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{profile}",
            "profile": profile,
            "profile_label": prof["label"],
            "live": self.live,
            "status": "running",
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "finished_at": None,
            "student": {"name": config.STUDENT_NAME, "roll": config.ROLL_NUMBER},
            "policy": {
                "move_limit": self.move_limit,
                "max_calls": self.budget.limit,
                "timeout_s": config.REQUEST_TIMEOUT,
                "retries": config.RETRIES,
                "history_len": config.HISTORY_LEN,
                "metric": "HTM (18 moves)",
                "seed": self.seed,
                "invalid_policy": "invalid or failed response = wasted turn (counts toward move limit, cube unchanged)",
            },
            "calls_used": 0,
            "round": 0,
            "models": [{k: m[k] for k in ("key", "name", "category", "id", "api")} for m in config.MODELS],
            "puzzles": puzzles,
            "trials": [],
            "log": [],
            "error": None,
            "summary": None,
        }
        for p in puzzles:
            for m in config.MODELS:
                self.data["trials"].append({
                    "id": f"{p['id']}-{m['key']}",
                    "puzzle_id": p["id"],
                    "model_key": m["key"],
                    "status": "playing",
                    "state": p["state"],
                    "moves": [],
                    "turns": 0,
                    "invalid": 0,
                    "retries": 0,
                    "steps": [],
                    "model_time_s": 0.0,
                    "engine_time_s": 0.0,
                    "total_time_s": 0.0,
                    "cost_usd": 0.0,
                    "current_move": None,
                })

    # ------------------------------------------------------------------ helpers
    def _log(self, msg: str):
        stamp = round(time.perf_counter() - self.t0, 2) if self.t0 else 0
        self.data["log"].append(f"[{stamp:>7}s] {msg}")
        self.data["log"] = self.data["log"][-300:]

    def _state_payload(self, t: dict) -> dict:
        return {
            "cube_facelets": t["state"],
            "faces": faces(t["state"]),
            "recent_moves": t["moves"][-config.HISTORY_LEN:],
            "moves_made": t["turns"],
            "moves_remaining": self.move_limit - t["turns"],
        }

    def _finish(self, t: dict, status: str):
        t["status"] = status
        t["current_move"] = None

    # ------------------------------------------------------------------ one turn
    async def _step(self, t: dict, adapter):
        key = t["model_key"]
        if key in self.disabled:
            self._finish(t, "error")
            return
        payload = self._state_payload(t)
        res, latency, attempts = None, 0.0, 0
        call_start = time.perf_counter() - self.t0
        for attempt in range(1 + config.RETRIES):
            if not self.budget.take():
                break
            attempts += 1
            async with self.sem:
                c0 = time.perf_counter()
                res = await adapter.choose(payload)
                latency += time.perf_counter() - c0
            self.data["calls_used"] = self.budget.used
            if res["error_kind"] != "transient":
                break
        if res is None:  # budget ran out before the call could be made
            self._finish(t, "budget")
            return
        t["retries"] += attempts - 1

        e0 = time.perf_counter()
        t["turns"] += 1
        valid = res["move"] is not None
        if valid:
            t["state"] = apply_move(t["state"], res["move"])
            t["moves"].append(res["move"])
            t["current_move"] = res["move"]
        else:
            t["invalid"] += 1
            t["current_move"] = "INVALID"
            self._log(f"{t['id']}: invalid/failed response ({res['error']})")
        solved = is_solved(t["state"])
        engine = time.perf_counter() - e0

        t["model_time_s"] += latency
        t["engine_time_s"] += engine
        t["total_time_s"] = t["model_time_s"] + t["engine_time_s"]
        t["cost_usd"] += res["cost"] or 0.0
        t["steps"].append({
            "turn": t["turns"],
            "move": res["move"],
            "valid": valid,
            "latency_s": round(latency, 4),
            "engine_s": round(engine, 6),
            "t_start": round(call_start, 3),
            "t_end": round(time.perf_counter() - self.t0, 3),
            "attempts": attempts,
            "confidence": res["confidence"],
            "probabilities": res["probabilities"],
            "error": res["error"],
            "raw": res["raw"],
            "state_after": t["state"],
        })

        if res["error_kind"] == "fatal_run":
            self.data["error"] = res["error"]
            self.stop_requested = True
            self._log(f"FATAL: {res['error']} - stopping run")
        elif res["error_kind"] == "fatal_model":
            self.disabled[key] = res["error"]
            self._log(f"model {key} disabled: {res['error']}")

        if solved:
            self._finish(t, "solved")
        elif t["turns"] >= self.move_limit:
            self._finish(t, "limit")
        elif key in self.disabled:
            self._finish(t, "error")

    # ------------------------------------------------------------------ main loop
    async def execute(self):
        self.t0 = time.perf_counter()
        trials = self.data["trials"]
        if self.live and not config.OPENROUTER_API_KEY:
            self.data["error"] = "OPENROUTER_API_KEY is not set in .env"
            self.data["status"] = "aborted"
            return self.save()
        self._log(f"run {self.data['id']}: {len(self.data['puzzles'])} puzzles x {len(config.MODELS)} models, "
                  f"budget={self.budget.limit}, move_limit={self.move_limit}")
        client = httpx.AsyncClient() if self.live else None
        adapters = build_adapters(self.live, client, self.seed)
        try:
            while not self.stop_requested:
                active = [t for t in trials if t["status"] == "playing"]
                if not active:
                    break
                if self.budget.remaining < len(active):
                    self._log(f"budget left ({self.budget.remaining}) < active trials ({len(active)}): stopping")
                    for t in active:
                        self._finish(t, "budget")
                    break
                self.data["round"] += 1
                if self.data["round"] == 1:
                    probes, seen = [], set()
                    for t in active:
                        if t["model_key"] not in seen:
                            seen.add(t["model_key"])
                            probes.append(t)
                    await asyncio.gather(*(self._step(t, adapters[t["model_key"]]) for t in probes))
                    probe_ids = {t["id"] for t in probes}
                    active = [t for t in active if t["id"] not in probe_ids and t["status"] == "playing"]
                    if self.stop_requested:
                        break
                await asyncio.gather(*(self._step(t, adapters[t["model_key"]]) for t in active))
        except asyncio.CancelledError:
            self.stop_requested = True
        finally:
            if client is not None:
                await client.aclose()
        for t in trials:
            if t["status"] == "playing":
                self._finish(t, "stopped" if not self.data["error"] else "error")
        self.data["status"] = "aborted" if self.data["error"] else (
            "stopped" if self.stop_requested else "finished")
        self._log(f"run {self.data['status']}: {self.budget.used} API calls used")
        return self.save()

    def snapshot(self) -> dict:
        self.data["summary"] = summarize(self.data)
        return self.data

    def save(self) -> dict:
        self.data["finished_at"] = datetime.now().isoformat(timespec="seconds")
        self.data["calls_used"] = self.budget.used
        self.data["summary"] = summarize(self.data)
        config.RESULTS_DIR.mkdir(exist_ok=True)
        base = config.RESULTS_DIR / f"run_{self.data['id']}"
        base.with_suffix(".json").write_text(json.dumps(self.data, indent=1), encoding="utf-8")
        base.with_suffix(".md").write_text(make_report(self.data), encoding="utf-8")
        return self.data
