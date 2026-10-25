"""Deterministic 3x3 Rubik's Cube engine.

State is a 54-character facelet string in URFDLB order (the Kociemba convention):
9 stickers per face, read row by row as seen looking straight at that face.
  U: viewed from above, B edge at the top      D: viewed from below, F edge at the top
  F, R, B, L: viewed from outside, U edge at the top
Each letter names the face whose centre has that colour, so the solved cube is
"UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB".

Moves use the half-turn metric (HTM): 18 moves, X = 90 deg clockwise looking at
face X, X' = counter-clockwise, X2 = 180 deg. Every model uses this one engine.
"""
from __future__ import annotations

import random
from operator import itemgetter

FACES = "URFDLB"
SOLVED = "".join(f * 9 for f in FACES)
FACE_WORDS = {"U": "upper", "R": "right", "F": "front", "D": "down", "L": "left", "B": "back"}
NORMALS = {"U": (0, 1, 0), "R": (1, 0, 0), "F": (0, 0, 1),
           "D": (0, -1, 0), "L": (-1, 0, 0), "B": (0, 0, -1)}
OPPOSITE = {"U": "D", "D": "U", "R": "L", "L": "R", "F": "B", "B": "F"}

MOVE_NAMES = [f + s for f in FACES for s in ("", "'", "2")]
MOVE_DESCRIPTIONS = {}
for _f in FACES:
    _w = FACE_WORDS[_f]
    MOVE_DESCRIPTIONS[_f] = f"Turn the {_w} face clockwise by 90 degrees"
    MOVE_DESCRIPTIONS[_f + "'"] = f"Turn the {_w} face counterclockwise by 90 degrees"
    MOVE_DESCRIPTIONS[_f + "2"] = f"Turn the {_w} face by 180 degrees"


def _sticker(face: str, r: int, c: int):
    """3D position and outward normal of sticker (row r, col c) on a face."""
    a, b = r - 1, c - 1
    pos = {
        "U": (b, 1, a),
        "D": (b, -1, -a),
        "F": (b, -a, 1),
        "B": (-b, -a, -1),
        "R": (1, -a, -b),
        "L": (-1, -a, b),
    }[face]
    return pos, NORMALS[face]


def _rotate(v, axis):
    """Rotate v by -90 degrees about axis (clockwise seen from outside that face)."""
    ax, ay, az = axis
    x, y, z = v
    cross = (ay * z - az * y, az * x - ax * z, ax * y - ay * x)
    dot = ax * x + ay * y + az * z
    return tuple(-cross[i] + axis[i] * dot for i in range(3))


_STICKERS = [_sticker(f, r, c) for f in FACES for r in range(3) for c in range(3)]
_INDEX = {s: i for i, s in enumerate(_STICKERS)}


def _quarter_perm(face: str):
    axis = NORMALS[face]
    perm = list(range(54))
    for i, (pos, nrm) in enumerate(_STICKERS):
        if sum(p * q for p, q in zip(pos, axis)) == 1:
            perm[_INDEX[(_rotate(pos, axis), _rotate(nrm, axis))]] = i
    return perm


def _compose(p, q):
    """Permutation equal to applying p, then q (new[k] = old[p[q[k]]])."""
    return [p[q[k]] for k in range(54)]


PERMS = {}
for _f in FACES:
    _q = _quarter_perm(_f)
    _q2 = _compose(_q, _q)
    PERMS[_f] = _q
    PERMS[_f + "2"] = _q2
    PERMS[_f + "'"] = _compose(_q2, _q)

_GETTERS = {m: itemgetter(*p) for m, p in PERMS.items()}


def apply_move(state: str, move: str) -> str:
    return "".join(_GETTERS[move](state))


def apply_moves(state: str, moves) -> str:
    for m in moves:
        state = apply_move(state, m)
    return state


def inverse(move: str) -> str:
    if move.endswith("2"):
        return move
    return move[0] if move.endswith("'") else move + "'"


def is_valid_move(move) -> bool:
    return isinstance(move, str) and move in PERMS


def is_solved(state: str) -> bool:
    return all(len(set(state[i * 9:(i + 1) * 9])) == 1 for i in range(6))


def faces(state: str) -> dict:
    """Face -> three rows, e.g. {"U": ["UUU", "UUU", "UUF"], ...}."""
    return {f: [state[i * 9 + r * 3:i * 9 + r * 3 + 3] for r in range(3)] for i, f in enumerate(FACES)}


def random_scramble(length: int, rng: random.Random) -> list[str]:
    """Random move sequence with no redundant same-face or same-axis repeats."""
    seq: list[str] = []
    while len(seq) < length:
        m = rng.choice(MOVE_NAMES)
        if seq:
            last = seq[-1][0]
            if m[0] == last:
                continue
            # avoid e.g. R L R (third turn on one axis collapses)
            if len(seq) >= 2 and m[0] == seq[-2][0] and OPPOSITE[m[0]] == last:
                continue
            # canonical order for commuting opposite faces (R L, never L R)
            if OPPOSITE[m[0]] == last and FACES.index(m[0]) < FACES.index(last):
                continue
        seq.append(m)
    return seq
