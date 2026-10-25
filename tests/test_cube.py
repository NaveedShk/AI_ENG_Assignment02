"""Engine and solver checks. Run: python -m pytest  (or: python -m tests.test_cube)"""
import random

from backend.cube import MOVE_NAMES, SOLVED, apply_move, apply_moves, inverse, is_solved, random_scramble
from backend.solver import shortest_solution


def test_every_move_has_order_four_and_inverse():
    for m in MOVE_NAMES:
        assert apply_moves(SOLVED, [m] * 4) == SOLVED
        assert apply_move(apply_move(SOLVED, m), inverse(m)) == SOLVED
        assert not is_solved(apply_move(SOLVED, m))


def test_known_facelet_string_after_R():
    # Reference value from the Kociemba facelet convention.
    assert apply_move(SOLVED, "R") == "UUFUUFUUFRRRRRRRRRFFDFFDFFDDDBDDBDDBLLLLLLLLLUBBUBBUBB"


def test_known_facelet_string_after_U():
    assert apply_move(SOLVED, "U") == "UUUUUUUUUBBBRRRRRRRRRFFFFFFDDDDDDDDDFFFLLLLLLLLLBBBBBB"


def test_sexy_move_has_order_six():
    seq = ["R", "U", "R'", "U'"]
    s = SOLVED
    for i in range(6):
        s = apply_moves(s, seq)
        assert (s == SOLVED) == (i == 5)


def test_solver_is_optimal_and_correct():
    rng = random.Random(1)
    for length in (1, 2, 3, 4, 5):
        for _ in range(5):
            scr = random_scramble(length, rng)
            state = apply_moves(SOLVED, scr)
            sol = shortest_solution(state, 6)
            assert sol is not None and len(sol) <= length
            assert is_solved(apply_moves(state, sol))
    # R U is distance 2, never 1
    assert len(shortest_solution(apply_moves(SOLVED, ["R", "U"]))) == 2


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
