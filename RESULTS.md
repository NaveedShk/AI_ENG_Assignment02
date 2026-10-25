# Results — Rubik's Cube Race

**Sheikh Naveed Azeemi · 23K-0003**

Two live OpenRouter runs, both on the same two primary puzzles (seed 2026, exact optimal distance 4 for both):

| Puzzle | Scramble | Shortest solution (BFS, HTM) |
|---|---|---|
| P1 | `D' B' R F'` | `F R' B D` (4 moves) |
| P2 | `B2 L2 F' U` | `U' F L2 B2` (4 moves) |

Full logs, including every move, latency, confidence and raw reply: `results/run_*.json`. The matching reports are in `results/run_*.md`.
Both runs can be replayed in the app with **Saved runs → Replay (0 calls)**.

## Run 1 — all four models (recorded demo)

`results/run_20261025_132427_budget` · 56 API calls · total cost ≈ $0.0035 · LLM thinking effort: low

| Model | Avg latency / move | Avg total time / puzzle | Moves | Success rate | Optimality gap | Progress* | Invalid |
|---|---|---|---|---|---|---|---|
| Jev 1.13 | **0.62 s** | 4.4 s | 14 | 0% (0/2) | – | −0.5 | 0 |
| GPT-6 Luna Decisions | 0.65 s | 4.5 s | 7 | 0% (0/2) | – | −0.5 | 7 |
| Cloudflare Clef | 0.99 s | 6.9 s | 14 | 0% (0/2) | – | −0.5 | 0 |
| Claude Haiku 5.5 (Opus 5.5 stand-in) | 2.81 s | 19.7 s | 14 | 0% (0/2) | – | −0.5 | 0 |

\*Progress = exact distance to solved at the start minus at the end. Positive means the cube ended closer to solved.

Every game stopped at **7 turns**, because the call budget could not cover another full round. Each unsolved game got the same number of turns.

## Run 2 — LLM only, more thinking

`results/run_20261025_133421_budget_opus` · 20 API calls · cost ≈ $0.030 · LLM thinking effort: **high** · 10-turn limit

| Model | Avg latency / move | Avg total time / puzzle | Moves | Success rate | Progress | Invalid |
|---|---|---|---|---|---|---|
| Claude Haiku 5.5, high thinking | 16.0 s | 160 s | 17 | 0% (0/2) | −0.5 | 3 |

Moves played: P1 `U U' R R' F F' U' U2 U2 U` (ends 4 from solved), P2 `U U' R R' F F' R'` (ends 5 from solved).
The 3 invalid replies were empty: the model used its whole 8,000-token budget thinking and never answered.

## What the data shows

* **Speed:** the System-1 decision models answered in 0.6–1.0 s per move. The LLM took 2.8 s with low thinking and 16 s with high thinking, so it was 4–25× slower.
* **Quality:** no model solved a 4-move puzzle.
  * The decision models' choices were close to random. Clef's average confidence was 0.04–0.08, about the same as picking 1 of 18 moves at random (0.056).
  * The decision models often undid their own previous move (`U U' U U' …`).
  * The LLM did the same, even with high thinking.
  * On average, every model ended **0.5 moves further** from solved than it started.
* **Reliability:** GPT-6 Luna Decisions refused to answer on every turn of puzzle 2 ("OpenAI refused to answer"). Those turns were logged as invalid, not converted into moves.
* **More thinking did not help here:** going from low to high effort made each move about 6× slower, gave the same 0% solve rate, and caused 3 empty replies.

## Answers to the five questions (draft — rewrite in your own words)

1. **Fastest decisions:** Jev 1.13, at 0.62 s per move. Luna (0.65 s) and Clef (0.99 s) were close; the LLM was 2.8–16 s.
2. **Highest solve rate:** none. All four models scored 0% within their turn limits.
3. **Shortest solutions / closeness to optimum:** no model solved a puzzle, so no optimality gap exists. Measured as progress toward solved, all models tied at −0.5. The best single game was Haiku on P1 and Clef on P2, each ending 3 moves from solved, one move closer than the start.
4. **Did the fastest also have the best quality?** No. Speed bought nothing in quality here: the fastest model did no better than the slowest.
5. **Which to use:** neither model type alone. Multi-step planning from a raw 54-character state is beyond both the fast decision models and this LLM. A practical agent would be a hybrid: a fast model for cheap, reversible choices, backed by explicit search or a verifier (like the BFS solver in this app) for planning.

## Deviations from the brief (budget constraints)

| Brief | This submission | Why |
|---|---|---|
| Claude Opus 5.5 as the frontier LLM | Claude Haiku 5.5 | On OpenRouter, Opus 5.5 has mandatory thinking and costs $4/$20 per M tokens, which the available credit could not cover. Haiku uses the same adapter, prompt and JSON schema. Set `MODEL_OPUS=anthropic/claude-opus-5.5` to use Opus. |
| ≥ 5 primary puzzles × 4 models (20 games) | 2 puzzles × 4 models (8 games), plus a 2-game LLM rerun | A total budget of about 85 API calls, including 8 setup/test calls |
| 30-move limit | Run 1 stopped at 7 turns (call budget); run 2 at 10 turns | Same budget. The app stops all unsolved games at the same turn count, so the comparison stays fair. |
| Warm-up and extension sets | Not run live. They are in the `mock` and `full` profiles. | Budget |

The code supports the full protocol: choose the **Full** profile, or raise `MAX_CALLS` / `BUDGET_PUZZLES` in `.env`.
