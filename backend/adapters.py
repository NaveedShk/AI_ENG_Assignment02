"""Model adapters. Every adapter takes the same game state and returns one move.

* DecisionAdapter - OpenRouter Decisions API (Jev, GPT-6 Luna Decisions, Clef)
* ChatAdapter     - OpenRouter chat completions with a JSON schema (Claude Opus 5.5)
* MockAdapter     - offline stand-ins used to test the whole app with zero API calls

Both live adapters share the same instructions, state payload and move options,
so the only difference between models is the model id and the API interface.
"""
from __future__ import annotations

import asyncio
import json
import random
import time

import httpx

from . import config
from .cube import MOVE_DESCRIPTIONS, MOVE_NAMES, is_valid_move
from .solver import shortest_solution

STATE_FORMAT = (
    "cube_facelets is a 54-character string: faces in the order U (up), R (right), F (front), "
    "D (down), L (left), B (back), 9 stickers per face, read row by row as seen looking straight "
    "at that face. U is viewed from above with the B edge at the top; D is viewed from below with "
    "the F edge at the top; F, R, B and L are viewed from outside with the U edge at the top. "
    "Each letter names the face whose centre has that colour, so the cube is solved when every "
    "face shows only its own letter. 'faces' shows the same stickers as three rows per face. "
    "Moves: X turns face X 90 degrees clockwise as seen looking at that face, X' turns it "
    "counterclockwise, X2 turns it 180 degrees."
)
INSTRUCTIONS = (
    "You are playing a 3x3 Rubik's Cube puzzle. Choose the single next move most likely to "
    "progress toward the solved cube, aiming to solve it in as few moves as possible. "
    + STATE_FORMAT
)
# Decision models get the request format from the assignment brief: short instructions and a
# state of {cube_facelets, recent_moves}. GPT-6 Luna Decisions refuses ("OpenAI refused to
# answer") when sent the long instructions above, so all three decision models use this
# identical, shorter contract. Option keys avoid the apostrophe (U_prime) and map back to U'.
DECISION_INSTRUCTIONS = "Choose the single next move most likely to progress toward the solved cube."
DECISION_KEYS = {m: m.replace("'", "_prime") for m in MOVE_NAMES}
DECISION_MOVES = {k: m for m, k in DECISION_KEYS.items()}
DECISION_CRITERIA = {DECISION_KEYS[m]: d for m, d in MOVE_DESCRIPTIONS.items()}
CHAT_SYSTEM = (
    INSTRUCTIONS
    + " Allowed moves: " + ", ".join(MOVE_NAMES) + "."
    + ' Reply with only a JSON object of the form {"move": "<one allowed move>"}.'
)


class Result(dict):
    """move (str|None), error (str|None), error_kind, confidence, probabilities, cost, raw."""


def _result(**kw) -> Result:
    base = {"move": None, "error": None, "error_kind": None, "confidence": None,
            "probabilities": None, "cost": None, "raw": None}
    base.update(kw)
    return Result(base)


def _http_error(resp: httpx.Response) -> Result:
    code = resp.status_code
    # 402 (credit) disables only the model that hit it: cheap models may still be affordable.
    kind = "fatal_run" if code == 401 else "fatal_model" if code in (400, 402, 403, 404) else "transient"
    return _result(error=f"HTTP {code}: {resp.text[:300]}", error_kind=kind, raw=resp.text[:500])


class _LiveAdapter:
    def __init__(self, model: dict, client: httpx.AsyncClient):
        self.model = model
        self.client = client
        self.headers = {
            "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "X-Title": "Rubik's Cube Race",
        }

    async def _post(self, path: str, body: dict):
        try:
            return await self.client.post(config.OPENROUTER_BASE_URL + path, json=body,
                                          headers=self.headers, timeout=config.REQUEST_TIMEOUT)
        except httpx.TimeoutException:
            return _result(error=f"timeout after {config.REQUEST_TIMEOUT}s", error_kind="transient")
        except httpx.HTTPError as e:
            return _result(error=f"network error: {e}", error_kind="transient")


class DecisionAdapter(_LiveAdapter):
    async def choose(self, state: dict) -> Result:
        body = {
            "model": self.model["id"],
            "state": {"cube_facelets": state["cube_facelets"], "recent_moves": state["recent_moves"]},
            "questions": {
                "next_move": {
                    "type": "choice",
                    "instructions": DECISION_INSTRUCTIONS,
                    "criteria": DECISION_CRITERIA,
                }
            },
        }
        resp = await self._post("/api/alpha/decisions", body)
        if isinstance(resp, Result):
            return resp
        if resp.status_code != 200:
            return _http_error(resp)
        try:
            data = resp.json()
            ans = data["answers"]["next_move"]
        except (ValueError, KeyError, TypeError):
            return _result(error="malformed: no answers.next_move", error_kind="malformed", raw=resp.text[:500])
        cost = (data.get("usage") or {}).get("cost")
        if not isinstance(ans, dict):
            return _result(error="malformed: answer is not an object", error_kind="malformed", raw=resp.text[:500])
        move = DECISION_MOVES.get(ans.get("choice"))
        if ans.get("type") != "choice" or not is_valid_move(move):
            return _result(error=f"malformed: invalid choice {ans.get('choice')!r}", error_kind="malformed",
                           raw=json.dumps(ans)[:500], cost=cost)
        probs = ans.get("probabilities")
        if isinstance(probs, dict):
            probs = {DECISION_MOVES.get(k, k): v for k, v in probs.items()}
        return _result(move=move, confidence=ans.get("confidence"),
                       probabilities=probs, cost=cost, raw=json.dumps(ans)[:500])


class ChatAdapter(_LiveAdapter):
    async def choose(self, state: dict) -> Result:
        body = {
            "model": self.model["id"],
            "messages": [
                {"role": "system", "content": CHAT_SYSTEM},
                {"role": "user", "content": json.dumps(state)},
            ],
            "max_tokens": config.OPUS_MAX_TOKENS,
        }
        if config.OPUS_RESPONSE_FORMAT == "json_schema":
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "next_move",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {"move": {"type": "string", "enum": MOVE_NAMES}},
                        "required": ["move"],
                        "additionalProperties": False,
                    },
                },
            }
            body["provider"] = {"require_parameters": True}
        elif config.OPUS_RESPONSE_FORMAT == "json_object":
            body["response_format"] = {"type": "json_object"}
        if config.OPUS_REASONING_EFFORT and config.OPUS_REASONING_EFFORT != "none":
            body["reasoning"] = {"effort": config.OPUS_REASONING_EFFORT, "exclude": True}

        resp = await self._post("/api/v1/chat/completions", body)
        if isinstance(resp, Result):
            return resp
        if resp.status_code != 200:
            return _http_error(resp)
        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, TypeError, IndexError):
            return _result(error="malformed: no message content", error_kind="malformed", raw=resp.text[:500])
        cost = (data.get("usage") or {}).get("cost")
        # Strict parsing: anything that is not exactly {"move": <valid move>} is logged as malformed.
        try:
            obj = json.loads((content or "").strip())
            move = obj["move"] if isinstance(obj, dict) else None
        except (ValueError, KeyError):
            move = None
        if not is_valid_move(move):
            return _result(error=f"malformed: {str(content)[:120]!r}", error_kind="malformed",
                           raw=str(content)[:500], cost=cost)
        return _result(move=move, cost=cost, raw=str(content)[:500])


class MockAdapter:
    """Offline stand-in. skill = chance of playing an optimal move; otherwise a random move."""

    def __init__(self, model: dict, skill: float, latency: tuple[float, float], seed: int):
        self.model = model
        self.skill = skill
        self.latency = latency
        self.rng = random.Random(seed)

    async def choose(self, state: dict) -> Result:
        t0 = time.perf_counter()
        move = None
        if self.rng.random() < self.skill:
            sol = await asyncio.to_thread(shortest_solution, state["cube_facelets"], 6)
            move = sol[0] if sol else None
        if move is None:
            move = self.rng.choice(MOVE_NAMES)
        wait = self.rng.uniform(*self.latency) - (time.perf_counter() - t0)
        if wait > 0:
            await asyncio.sleep(wait)
        if self.rng.random() < 0.02:
            return _result(error="malformed: simulated bad output", error_kind="malformed", raw="{oops")
        return _result(move=move, confidence=round(self.rng.uniform(0.3, 0.95), 2), raw=json.dumps({"move": move}))


MOCK_PROFILES = {
    "jev": (0.35, (0.05, 0.25)),
    "luna": (0.30, (0.08, 0.30)),
    "clef": (0.25, (0.04, 0.20)),
    "opus": (0.92, (2.0, 5.0)),
}


def build_adapters(live: bool, client: httpx.AsyncClient | None, seed: int) -> dict:
    adapters = {}
    for i, m in enumerate(config.MODELS):
        if live:
            adapters[m["key"]] = (DecisionAdapter if m["api"] == "decisions" else ChatAdapter)(m, client)
        else:
            skill, lat = MOCK_PROFILES[m["key"]]
            adapters[m["key"]] = MockAdapter(m, skill, lat, seed + i)
    return adapters
