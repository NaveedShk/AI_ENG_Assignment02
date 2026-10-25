"""Exact shortest solutions (half-turn metric) via bidirectional breadth-first search.

Complete and optimal up to max_depth: the search expands one full BFS level at a
time from whichever side has the smaller frontier, and on the first level where
the two searches meet it keeps the meeting point with the smallest total depth.
Depth 4-5 puzzles (the primary benchmark) solve in milliseconds; depth 8 takes a
few seconds; beyond that the result is None (distance unknown).
"""
from __future__ import annotations

from .cube import MOVE_NAMES, SOLVED, apply_move, inverse, is_solved


def _expand(frontier, own, other):
    nxt, best = [], None
    for s in frontier:
        depth = own[s][2] + 1
        for m in MOVE_NAMES:
            t = apply_move(s, m)
            if t in own:
                continue
            own[t] = (s, m, depth)
            nxt.append(t)
            if t in other and (best is None or other[t][2] < other[best][2]):
                best = t
    return nxt, best


def shortest_solution(state: str, max_depth: int = 8):
    """Return an optimal move list that solves `state`, or None if longer than max_depth."""
    if is_solved(state):
        return []
    fwd = {state: (None, None, 0)}
    bwd = {SOLVED: (None, None, 0)}
    ff, bf = [state], [SOLVED]
    df = db = 0
    while df + db < max_depth and ff and bf:
        if len(ff) <= len(bf):
            ff, meet = _expand(ff, fwd, bwd)
            df += 1
        else:
            bf, meet = _expand(bf, bwd, fwd)
            db += 1
        if meet is not None:
            return _path(meet, fwd, bwd)
    return None


def _path(meet, fwd, bwd):
    head = []
    s = meet
    while fwd[s][0] is not None:
        parent, move, _ = fwd[s]
        head.append(move)
        s = parent
    head.reverse()
    tail = []
    s = meet
    while bwd[s][0] is not None:
        parent, move, _ = bwd[s]
        tail.append(inverse(move))
        s = parent
    return head + tail


def distance(state: str, max_depth: int = 8):
    sol = shortest_solution(state, max_depth)
    return None if sol is None else len(sol)
