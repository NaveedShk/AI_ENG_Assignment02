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

## Answers to the five questions

1. **Fastest decisions:** Jev 1.13, at 0.62 s per move. Luna (0.65 s) and Clef (0.99 s) were close; the LLM was 2.8–16 s.
2. **Highest solve rate:** none. All four models scored 0% within their turn limits.
3. **Shortest solutions / closeness to optimum:** no model solved a puzzle, so no optimality gap exists. Measured as progress toward solved, all models tied at −0.5. The best single game was Haiku on P1 and Clef on P2, each ending 3 moves from solved, one move closer than the start.
4. **Did the fastest also have the best quality?** No. Speed bought nothing in quality here: the fastest model did no better than the slowest.
5. **Which would I use in a real-world application?** A **hybrid agent**. I would not use the fastest decision model alone, and the evidence does not justify the LLM alone either.

   **Evidence against the fast decision model alone:**
   * Speed was its only advantage: 0.6–1.0 s per move, with a 0% solve rate.
   * Its choices were close to random. Clef's average confidence was 0.04–0.08, about the 1/18 ≈ 0.056 of a blind guess among 18 moves.
   * Jev kept undoing its own previous move (`U U' U U' …`).
   * Reliability was a problem too: GPT-6 Luna Decisions refused to answer 7 of its 14 turns.
   * A fast agent that makes no progress, or does not answer, is not useful however fast it is.

   **Evidence against the LLM alone:**
   * It also scored 0%. With low thinking it was 3–4× slower than the decision models and ended no closer to solved.
   * Raising thinking to high made each move about 6× slower again (16 s) and cost about 10× more per move.
   * It still made no progress, and 3 of its 20 replies were empty because thinking used the whole token budget.
   * In this experiment, more time spent "planning" did not buy better plans.

   **What actually solved every puzzle:** the deterministic BFS search built into the app, which found the exact 4-move solution in milliseconds.

   **The design I would use:** let a model handle the parts it is good at, and leave multi-step planning to an explicit planner, with every step checked by a verifier.
   * **Fast decision model:** single-step choices that are cheap and reversible (routing, classification, picking the next action when the state is easy to read). It is 5–50× cheaper per call than the LLM here: about $0.00003 per move, vs $0.00016 for the LLM with low thinking and $0.0015 with high.
   * **Search or solver:** the actual multi-step planning, where correctness matters.
   * **Verifier:** measures progress, as this app's distance-to-solved does, and rejects or escalates a step when a model goes backwards or stalls.
   * **Frontier LLM:** best kept for open-ended reasoning, explaining a plan, or fallback when nothing else applies. It should not take every per-step decision.

   **Limits of this evidence:**
   * 8 games, plus a 2-game rerun.
   * Claude Haiku 5.5 stood in for Opus 5.5.
   * 7–10 turns instead of 30.
   * A full Opus run with the 30-move limit could change the LLM's numbers. Even so, the hybrid design would still be the safer choice, because it does not depend on any single model planning correctly.

## Deviations from the brief (budget constraints)

| Brief | This submission | Why |
|---|---|---|
| Claude Opus 5.5 as the frontier LLM | Claude Haiku 5.5 | On OpenRouter, Opus 5.5 has mandatory thinking and costs $4/$20 per M tokens, which the available credit could not cover. Haiku uses the same adapter, prompt and JSON schema. Set `MODEL_OPUS=anthropic/claude-opus-5.5` to use Opus. |
| ≥ 5 primary puzzles × 4 models (20 games) | 2 puzzles × 4 models (8 games), plus a 2-game LLM rerun | A total budget of about 85 API calls, including 8 setup/test calls |
| 30-move limit | Run 1 stopped at 7 turns (call budget); run 2 at 10 turns | Same budget. The app stops all unsolved games at the same turn count, so the comparison stays fair. |
| Warm-up and extension sets | Not run live. They are in the `mock` and `full` profiles. | Budget |

The code supports the full protocol: choose the **Full** profile, or raise `MAX_CALLS` / `BUDGET_PUZZLES` in `.env`.
