# Rubik's Cube Race — fast decision models vs. a frontier LLM

**Question:** is a model that decides in milliseconds more useful than a frontier LLM that plans longer,
if the slower model solves the task in fewer moves?

**Results of the submitted runs, answers to the five questions, and deviations from the brief: see [RESULTS.md](RESULTS.md).**

This app benchmarks four OpenRouter models on the same scrambled 3×3 cubes:

| Model | Category | OpenRouter id | Interface |
|---|---|---|---|
| Jev 1.13 | System-1 decision model | `typesafe/jev-1.13` | Decisions API |
| OpenAI GPT-6 Luna Decisions | System-1 decision model | `openai/gpt-6-luna-decisions` | Decisions API |
| Cloudflare Clef | System-1 decision model | `cloudflare/clef` | Decisions API |
| Claude Opus 5.5 | Frontier LLM | `anthropic/claude-opus-5.5` | Chat completions (JSON schema) |

> **Budget substitution in the submitted run:** the recorded run uses **Claude Haiku 5.5** (`anthropic/claude-haiku-5.5`,
> low thinking effort) in the frontier-LLM slot instead of Claude Opus 5.5. On OpenRouter, Opus 5.5 has mandatory
> thinking and costs $4/$20 per million tokens, which did not fit the available prepaid credit. Haiku 5.5 costs
> $0.10/$0.50, about 40× less. It goes through the same chat-completions adapter, prompt and JSON-schema contract.
> To use Opus, set `MODEL_OPUS=anthropic/claude-opus-5.5` in `.env` and remove the `MODEL_OPUS_NAME`/`MODEL_OPUS_CATEGORY` overrides.

The ids are set in `.env`, so you can update them without changing code. Click **Check models (free)** in the UI to confirm they are listed in OpenRouter's public catalog.

---

## How it works

```
 browser (HTML/JS)  ──poll──▶  FastAPI backend  ──▶  OpenRouter
   cube nets, moves,           ├─ cube.py       deterministic engine (54-facelet state, 18 HTM moves)
   dashboard, slide            ├─ solver.py     exact shortest solution (bidirectional BFS)
                               ├─ adapters.py   Decisions API / chat-completions / offline mock
                               ├─ benchmark.py  rounds, call budget, timing, logging
                               └─ stats.py      metrics + answers to the 5 questions
```

**State/action space (like the Snake example).** Each turn a model receives the same **state**:

```json
{
  "cube_facelets": "UUFUUFUUFRRRRRRRRRFFDFFDFFDDDBDDBDDBLLLLLLLLLUBBUBBUBB",
  "faces": {"U": ["UUF","UUF","UUF"], "R": ["RRR","RRR","RRR"], "...": "..."},
  "recent_moves": ["R"],
  "moves_made": 1,
  "moves_remaining": 29
}
```

It must choose one **action** from the 18 half-turn-metric moves (`U U' U2 R R' R2 F … B2`).
The engine validates the move, applies it, and checks whether all six faces are solved.

* **Decision models:** `POST https://openrouter.ai/api/alpha/decisions` with a `choice` question named `next_move`.
  They all get the identical request from the assignment brief: state `{cube_facelets, recent_moves}`, the instruction
  "Choose the single next move most likely to progress toward the solved cube.", and the 18 moves as criteria.
  Option keys use `U_prime` instead of `U'`, mapped back to `U'`.
  The app reads `answers.next_move.choice` and records `confidence` and `probabilities`.
  GPT-6 Luna Decisions refused ("OpenAI refused to answer") when given a longer instruction that explained the facelet layout, so the shorter brief format is used for all three.
* **Claude Opus 5.5:** `POST https://openrouter.ai/api/v1/chat/completions` with the same instructions and state.
  A strict `json_schema` response format (`{"move": <enum of 18 moves>}`) and `provider.require_parameters` are set.
* **Validation:** a reply that isn't exactly one valid move is logged as *malformed* and counted. The app never converts it into a move.
  An invalid or failed reply uses up a turn (it counts toward the move limit) and leaves the cube unchanged.

**Fair experiment.** Every model gets the same scrambles (fixed `SEED`), the same engine, instructions, history window,
move limit (30), timeout, and retry policy. Only the model id and API interface differ.
The runner plays in **rounds**: each unfinished trial makes one move per round, in parallel.
Before each round it checks the call budget. If the budget can't cover one call per unfinished trial, the run stops there.
So under a budget, every unsolved trial has had **exactly the same number of turns**.

**Optimal reference.** Puzzles are generated so that their exact BFS distance equals the scramble length.
`optimality gap = model moves − exact shortest moves` is reported for solved puzzles.
For extension puzzles (15–20 turns), BFS only proves distances up to 8, so the optimum is reported as unknown.

## Metrics (dashboard + end slide)

Per model:

* average (and median) latency per move
* total solve time per puzzle (sum of call latencies plus engine time)
* total moves
* success rate
* average optimality gap
* invalid outputs, calls and cost (from OpenRouter `usage.cost`)

The page and `results/run_*.md` also answer the five assignment questions from the data.
The Q5 recommendation is a draft for you to rewrite.

---

## Setup

Requirements: Python 3.10+ and an OpenRouter API key.

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate      macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env        # macOS/Linux: cp .env.example .env
```

Edit `.env` and set `OPENROUTER_API_KEY`, `STUDENT_NAME` and `ROLL_NUMBER`.
The key is only read by the backend. It is never sent to the browser, and `.env` is git-ignored.

```bash
uvicorn backend.main:app --port 8000
```

Open http://localhost:8000.

Run the tests (offline):

```bash
python -m pytest -q
```

## Running on a small budget

| Step | What | Paid calls |
|---|---|---|
| 1 | **Mock** profile in the UI: full app with simulated models; practise the recording | 0 |
| 2 | **Check models (free)** button: model ids against the public catalog | 0 |
| 3 | `python -m scripts.ping`: one real call per model to verify each adapter | 4 |
| 4 | **Budget** profile: `BUDGET_PUZZLES` primary puzzles (4 moves deep) × 4 models, hard cap `MAX_CALLS` (the submitted run used 2 puzzles and a cap of 57) | ≤ `MAX_CALLS` |
| 5 | **Replay (0 calls)** / **Show results** / **Benchmark slide** for re-takes of the video | 0 |

Ways the budget is protected:

* `MAX_CALLS` is a hard cap. Every HTTP attempt counts, including retries.
* Round 1 sends one probe call per model first. A wrong id or schema (HTTP 400/403/404) disables that model after one call instead of one per puzzle.
* HTTP 401 (bad key) stops the whole run immediately. HTTP 402 (out of credit) disables only the model that hit it, so cheaper models can finish.
* `RETRIES=0` by default.
* Solved trials stop calling, so their unused budget goes to the remaining trials as extra rounds.

Each unsolved trial is guaranteed at least `MAX_CALLS ÷ (puzzles × 4)` turns, rounded down. For example, 2 puzzles with a cap of 57 gives at least 7 turns each.
The **Full** profile follows the complete recommended protocol: 2 warm-up, 5 primary and 2 extension puzzles. It can take about 1000 calls.

> The budget profile runs fewer than the recommended 20 trials. Trials that end with **BUDGET STOP** count as unsolved
> after the turns shown. See [RESULTS.md](RESULTS.md) for the deviations in the submitted run.

## Screen recording checklist

1. **In progress:** start a run (or replay one). All four models play side by side, showing the current move, move history and cube net.
2. **Completed:** every card shows SOLVED, MOVE LIMIT or BUDGET STOP. The dashboard fills in.
3. **Final slide:** click **Benchmark slide** for the full-screen statistics from section 3.
4. **Name and roll number** are in the sticky header and on the slide the whole time (set them in `.env`).

The badge in the header shows `LIVE`, `MOCK` or `REPLAY`, so the video is clear about what is on screen.

## Project layout

```
backend/   cube.py  solver.py  adapters.py  benchmark.py  stats.py  config.py  main.py
frontend/  index.html  app.js  style.css
scripts/   ping.py (4-call smoke test)   run_cli.py (headless run)
tests/     test_cube.py
results/   run_*.json (full logs) and run_*.md (report)   [git-ignored]
```

Headless alternative to the UI: `python -m scripts.run_cli budget` (or `mock`). Add `--models opus --move-limit 10` to run a subset.
Recompute a saved run's statistics offline: `python -m scripts.rebuild_report results/run_<id>.json`.
