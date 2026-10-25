"""Benchmark statistics, plus a Markdown report that answers the assignment questions."""
from __future__ import annotations

from statistics import mean, median

DONE = {"solved", "limit", "budget", "error", "stopped"}


def _r(x, n=3):
    return None if x is None else round(x, n)


def summarize(run: dict) -> dict:
    puzzles = {p["id"]: p for p in run["puzzles"]}
    models = []
    for m in run["models"]:
        ts = [t for t in run["trials"] if t["model_key"] == m["key"]]
        done = [t for t in ts if t["status"] in DONE and t["turns"] > 0]
        lat = [s["latency_s"] for t in ts for s in t["steps"]]
        solved = [t for t in done if t["status"] == "solved"]
        gaps = [len(t["moves"]) - puzzles[t["puzzle_id"]]["optimal"]
                for t in solved if puzzles[t["puzzle_id"]]["optimal"] is not None]
        # Progress = exact distance to solved at the start minus at the end (positive = got closer).
        # final_distance is filled in when the run is saved; None means "further than 8 moves".
        measured = [t for t in done if "final_distance" in t and puzzles[t["puzzle_id"]]["optimal"] is not None]
        progress = [puzzles[t["puzzle_id"]]["optimal"] - t["final_distance"]
                    for t in measured if t["final_distance"] is not None]
        final_known = [t["final_distance"] for t in measured if t["final_distance"] is not None]
        models.append({
            "key": m["key"],
            "name": m["name"],
            "category": m["category"],
            "trials": len(done),
            "solved": len(solved),
            "success_rate": _r(100 * len(solved) / len(done), 1) if done else None,
            "avg_latency_s": _r(mean(lat)) if lat else None,
            "median_latency_s": _r(median(lat)) if lat else None,
            "avg_total_time_s": _r(mean(t["total_time_s"] for t in done)) if done else None,
            "sum_total_time_s": _r(sum(t["total_time_s"] for t in done)),
            "total_moves": sum(len(t["moves"]) for t in done),
            "avg_moves": _r(mean(len(t["moves"]) for t in done), 2) if done else None,
            "avg_moves_solved": _r(mean(len(t["moves"]) for t in solved), 2) if solved else None,
            "avg_gap": _r(mean(gaps), 2) if gaps else None,
            "zero_gap_solves": sum(1 for g in gaps if g == 0),
            "gaps": gaps,
            "avg_final_distance": _r(mean(final_known), 2) if final_known else None,
            "final_beyond_8": sum(1 for t in measured if t["final_distance"] is None),
            "avg_progress": _r(mean(progress), 2) if progress else None,
            "invalid": sum(t["invalid"] for t in ts),
            "retries": sum(t["retries"] for t in ts),
            "calls": len(lat),
            "cost_usd": _r(sum(t["cost_usd"] for t in ts), 5),
        })
    per_puzzle = []
    for p in run["puzzles"]:
        row = {"id": p["id"], "set": p["set"], "scramble": " ".join(p["scramble"]),
               "optimal": p["optimal"], "results": {}}
        for t in run["trials"]:
            if t["puzzle_id"] == p["id"]:
                gap = (len(t["moves"]) - p["optimal"]) if t["status"] == "solved" and p["optimal"] is not None else None
                row["results"][t["model_key"]] = {"status": t["status"], "moves": len(t["moves"]),
                                                  "turns": t["turns"], "gap": gap,
                                                  "final_distance": t.get("final_distance", "n/a")}
        per_puzzle.append(row)
    return {"models": models, "puzzles": per_puzzle, "answers": answers(models)}


def _best(models, field, low=True):
    vals = [m for m in models if m[field] is not None]
    if not vals:
        return []
    target = (min if low else max)(m[field] for m in vals)
    return [m for m in vals if m[field] == target]


def _names(ms, total=None):
    if total and total > 1 and len(ms) == total:
        return f"all {total} models (tied)"
    return " and ".join(m["name"] for m in ms) or "n/a"


def answers(models: list[dict]) -> dict:
    fastest = _best(models, "avg_latency_s", low=True)
    top_solve = _best(models, "success_rate", low=False)
    shortest = _best(models, "avg_gap", low=True)
    closest = _best(models, "avg_progress", low=False)
    any_solved = any(m["solved"] for m in models)
    a = {}
    if not fastest:
        return {q: "No data yet." for q in ("q1", "q2", "q3", "q4", "q5")}
    f = fastest[0]
    a["q1"] = f"{_names(fastest)} was fastest, averaging {f['avg_latency_s']} s per move decision."
    if len(models) == 1:
        a["q1"] += " (Only one model in this run.)"

    if any_solved:
        s = top_solve[0]
        a["q2"] = (f"{_names(top_solve)} had the highest solve rate: {s['success_rate']}% "
                   f"({s['solved']}/{s['trials']} puzzles).")
    else:
        a["q2"] = ("No model solved a puzzle within its turn limit ("
                   + (f"0% for all {len(models)} models)." if len(models) > 1 else "0%)."))

    if shortest:
        g = shortest[0]
        a["q3"] = (f"{_names(shortest)} found the shortest solutions: average optimality gap "
                   f"{g['avg_gap']} moves over {len(g['gaps'])} solved puzzles "
                   f"({g['zero_gap_solves']} solved in the exact optimum).")
    else:
        a["q3"] = "No model solved a puzzle, so no optimality gap can be computed."
        if closest:
            c = closest[0]
            a["q3"] += (f" Measured instead as progress (start distance minus final distance to solved): "
                        f"{_names(closest, len(models))} did best with {c['avg_progress']:+} moves on average "
                        f"(negative means the cube ended further from solved).")

    if len(models) == 1:
        a["q4"] = "Not applicable - only one model in this run."
    elif any_solved:
        quality = shortest or top_solve
        same = bool({m["key"] for m in fastest} & {m["key"] for m in quality})
        a["q4"] = ("Yes - the fastest model also had the best solution quality." if same else
                   f"No - {_names(fastest)} was fastest, but the best solution quality came from {_names(quality)}.")
    else:
        a["q4"] = (f"Speed did not translate into quality: {_names(fastest)} was fastest, but no model solved a puzzle"
                   + (f"; by progress toward solved the best was {_names(closest, len(models))}." if closest else "."))
    a["q5"] = _recommendation(models, fastest, top_solve, any_solved)
    return a


def _recommendation(models, fastest, top_solve, any_solved) -> str:
    f = fastest[0]
    if len(models) == 1:
        return "Not applicable for a single-model run - see the main four-model run."
    if not any_solved:
        return ("Draft: neither model type alone. No model solved a 4-move puzzle: the decision models answered "
                f"quickly ({f['name']} {f['avg_latency_s']} s/move) but with near-random choices and back-and-forth "
                "moves, and the LLM was slower without planning better. For a real application I would use a hybrid "
                "agent: a fast model for cheap, reversible steps, backed by an explicit search or verifier (like the "
                "BFS solver in this app) for multi-step planning. Edit this in your own words before submitting.")
    s = top_solve[0]
    if f["key"] == s["key"]:
        return (f"Draft: use {f['name']} - it was both the fastest ({f['avg_latency_s']} s/move) and "
                f"the most reliable ({f['success_rate']}% solved). Edit this in your own words before submitting.")
    ratio = (s["avg_latency_s"] / f["avg_latency_s"]) if f["avg_latency_s"] else None
    ratio_txt = f"~{ratio:.0f}x slower per move" if ratio else "slower per move"
    return (f"Draft: a hybrid agent. {s['name']} solved {s['success_rate']}% of puzzles but was {ratio_txt} "
            f"than {f['name']} ({s['avg_latency_s']} s vs {f['avg_latency_s']} s), which solved "
            f"{f['success_rate']}%. Use the fast decision model for cheap, low-stakes or easily reversible "
            f"steps and hand off to the slower LLM (or a verifier/search) when progress stalls or "
            f"mistakes are costly. Edit this in your own words before submitting.")


def _fmt(x, suffix=""):
    return "-" if x is None else f"{x}{suffix}"


def make_report(run: dict) -> str:
    s = run.get("summary") or summarize(run)
    pol = run["policy"]
    lines = [
        f"# Rubik's Cube Race - benchmark report ({run['id']})",
        "",
        f"Student: **{run['student']['name']}** - Roll No: **{run['student']['roll']}**",
        "",
        f"Profile: {run['profile_label']} - {'LIVE OpenRouter calls' if run['live'] else 'MOCK (simulated models, no API calls)'}",
        f"Status: {run['status']} - API calls used: {run['calls_used']}"
        + (f" / {pol['max_calls']}" if pol["max_calls"] else ""),
        f"Policy: move limit {pol['move_limit']}, timeout {pol['timeout_s']} s, retries {pol['retries']}, "
        f"history {pol['history_len']} moves, LLM thinking effort {pol.get('llm_reasoning_effort', '-')}, metric {pol['metric']}, seed {pol['seed']}. {pol['invalid_policy']}.",
        "",
        "## Statistical benchmark",
        "",
        "| Model | Category | Avg latency / move | Avg total time / puzzle | Total moves | Success rate | Avg optimality gap | Avg progress | Invalid | Calls | Cost (USD) |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for m in s["models"]:
        lines.append(
            f"| {m['name']} | {m['category']} | {_fmt(m['avg_latency_s'], ' s')} | {_fmt(m['avg_total_time_s'], ' s')} | "
            f"{m['total_moves']} | {_fmt(m['success_rate'], '%')} ({m['solved']}/{m['trials']}) | {_fmt(m['avg_gap'])} | "
            f"{_fmt(m.get('avg_progress'))} | {m['invalid']} | {m['calls']} | {_fmt(m['cost_usd'])} |")
    lines += ["", "Optimality gap = model moves - exact shortest moves (BFS, HTM), solved puzzles only. "
              "Progress = exact distance to solved at the start minus at the end (positive = closer; "
              "trials ending more than 8 moves away are excluded).", "",
              "## Per puzzle", "",
              "| Puzzle | Set | Scramble | Optimal | " + " | ".join(m["name"] for m in run["models"]) + " |",
              "|---|---|---|---|" + "---|" * len(run["models"])]
    for p in s["puzzles"]:
        cells = []
        for m in run["models"]:
            r = p["results"].get(m["key"])
            if not r:
                cells.append("-")
            elif r["status"] == "solved":
                cells.append(f"solved in {r['moves']} (gap {_fmt(r['gap'])})")
            else:
                fd = r.get("final_distance", "n/a")
                fd_txt = "" if fd == "n/a" else f", ends {'>8' if fd is None else fd} from solved"
                cells.append(f"{r['status']} after {r['turns']} turns{fd_txt}")
        lines.append(f"| {p['id']} | {p['set']} | `{p['scramble']}` | {_fmt(p['optimal'])} | " + " | ".join(cells) + " |")
    a = s["answers"]
    lines += ["", "## Answers", "",
              f"1. **Which model is fastest at making decisions?** {a['q1']}",
              f"2. **Which model achieved the highest solve rate?** {a['q2']}",
              f"3. **Which model found the shortest solutions?** {a['q3']}",
              f"4. **Did the fastest model also achieve the best solution quality?** {a['q4']}",
              f"5. **Fast model, frontier LLM, or hybrid?** {a['q5']}", ""]
    return "\n".join(lines)
