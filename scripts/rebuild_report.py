"""Recompute statistics and the Markdown report for a saved run (offline, no API calls).

    python -m scripts.rebuild_report results/run_<id>.json [--effort low]

--effort records the LLM thinking effort for runs saved before it was logged.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.benchmark import add_final_distances
from backend.stats import make_report, summarize


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path)
    ap.add_argument("--effort")
    a = ap.parse_args()
    run = json.loads(a.path.read_text(encoding="utf-8"))
    if a.effort and "llm_reasoning_effort" not in run["policy"]:
        run["policy"]["llm_reasoning_effort"] = a.effort
    add_final_distances(run)
    run["summary"] = summarize(run)
    a.path.write_text(json.dumps(run, indent=1), encoding="utf-8")
    a.path.with_suffix(".md").write_text(make_report(run), encoding="utf-8")
    print(make_report(run))


if __name__ == "__main__":
    main()
