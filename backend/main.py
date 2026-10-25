"""FastAPI backend: runs the benchmark, serves live state and saved results, hosts the UI.

Start with:  uvicorn backend.main:app --port 8000
"""
from __future__ import annotations

import asyncio
import json

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config
from .benchmark import Run

app = FastAPI(title="Rubik's Cube Race")
_current: dict = {"run": None, "task": None}


class RunRequest(BaseModel):
    profile: str = "mock"
    seed: int | None = None
    max_calls: int | None = None
    move_limit: int | None = None


@app.get("/api/config")
def get_config():
    return {
        "student": {"name": config.STUDENT_NAME, "roll": config.ROLL_NUMBER},
        "models": config.MODELS,
        "profiles": {k: {"label": v["label"], "live": v["live"], "max_calls": v["max_calls"],
                         "sets": v["sets"]} for k, v in config.PROFILES.items()},
        "move_limit": config.MOVE_LIMIT,
        "api_key_set": bool(config.OPENROUTER_API_KEY),  # never the key itself
    }


@app.post("/api/run")
async def start_run(req: RunRequest):
    if req.profile not in config.PROFILES:
        raise HTTPException(400, f"unknown profile {req.profile}")
    task = _current["task"]
    if task and not task.done():
        raise HTTPException(409, "a run is already in progress")
    run = Run(req.profile, seed=req.seed, max_calls=req.max_calls, move_limit=req.move_limit)
    _current["run"] = run
    _current["task"] = asyncio.create_task(run.execute())
    return {"id": run.data["id"]}


@app.get("/api/run/current")
def current_run():
    run = _current["run"]
    if run is None:
        return {"status": "idle"}
    return run.snapshot()


@app.post("/api/run/stop")
def stop_run():
    run = _current["run"]
    if run:
        run.stop_requested = True
    return {"ok": True}


@app.get("/api/runs")
def list_runs():
    config.RESULTS_DIR.mkdir(exist_ok=True)
    files = sorted(config.RESULTS_DIR.glob("run_*.json"), reverse=True)
    return [f.stem for f in files]


@app.get("/api/runs/{name}")
def get_saved_run(name: str):
    path = (config.RESULTS_DIR / f"{name}.json").resolve()
    if path.parent != config.RESULTS_DIR.resolve() or not path.exists():
        raise HTTPException(404, "not found")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/preflight")
async def preflight():
    """Free check: are the configured model ids in OpenRouter's public catalog? (no paid calls)"""
    found: set[str] = set()
    errors = []
    async with httpx.AsyncClient(timeout=30) as client:
        for q in ("", "?output_modalities=decisions", "?output_modalities=all"):
            try:
                r = await client.get(f"{config.OPENROUTER_BASE_URL}/api/v1/models{q}")
                for m in r.json().get("data", []):
                    found.add(m.get("id"))
                    if m.get("canonical_slug"):
                        found.add(m["canonical_slug"])
            except Exception as e:  # catalog lookup is best-effort
                errors.append(str(e))
    return {
        "api_key_set": bool(config.OPENROUTER_API_KEY),
        "models": [{"name": m["name"], "id": m["id"], "listed": m["id"] in found} for m in config.MODELS],
        "errors": errors,
    }


@app.get("/")
def index():
    return FileResponse(config.FRONTEND_DIR / "index.html")


app.mount("/static", StaticFiles(directory=config.FRONTEND_DIR), name="static")
