"""Plain-assert checks; run with python test_matchmaker.py."""

import random

from matchmaker import (
    Player, brute_force, cost, hill_climb, make_players, simulated_annealing, swap_delta,
)


def run_tests():
    balanced = [Player(0, 5, frozenset({0})), Player(1, 5, frozenset({0})),
                Player(2, 4, frozenset({0})), Player(3, 6, frozenset({0}))]
    state = [0, 1, 2, 3]
    assert cost(state, balanced, 2, 1) == 0

    players = make_players(8, 3, 19)
    state = list(range(8))
    rng = random.Random(22)
    for _ in range(100):
        i, j = rng.sample(range(8), 2)
        before = cost(state, players, 2, 3)
        delta = swap_delta(state, i, j, players, 2, 3)
        state[i], state[j] = state[j], state[i]
        assert delta == cost(state, players, 2, 3) - before
        state[i], state[j] = state[j], state[i]

    start = list(range(8))
    hc_state, hc_value, history = hill_climb(players, 2, 3, random.Random(3), start)
    assert hc_value <= cost(start, players, 2, 3)
    assert hc_value == cost(hc_state, players, 2, 3)
    sa_state, sa_value, _ = simulated_annealing(players, 2, 3, random.Random(4), start, iters=300)
    assert sa_value == cost(sa_state, players, 2, 3)

    optimum_state, optimum = brute_force(players, 2, 3)
    assert optimum <= hc_value and optimum <= sa_value
    try:
        cost([0, 1, 2], players[:3], 2, 2)
        raise AssertionError("Uneven player count should fail")
    except ValueError as exc:
        assert "multiple of 2*TEAM_SIZE" in str(exc)
    print("All matchmaker checks passed.")


if __name__ == "__main__":
    run_tests()
