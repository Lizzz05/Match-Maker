#!/usr/bin/env python3
"""Fair Match-Maker: small, explainable local-search team scheduling demos."""

from __future__ import annotations

import argparse
import csv
import itertools
import math
import random
import statistics
import time
from dataclasses import dataclass
from typing import Optional


PENALTY = 100


@dataclass(frozen=True)
class Player:
    id: int
    rating: int
    free_slots: frozenset[int]
    name: Optional[str] = None

    @property
    def label(self) -> str:
        return self.name if self.name else str(self.id)


def validate_problem(players: list[Player], team_size: int, n_slots: int) -> None:
    if team_size < 1:
        raise ValueError("TEAM_SIZE must be at least 1.")
    if n_slots < 1:
        raise ValueError("There must be at least one time slot.")
    match_size = 2 * team_size
    if len(players) % match_size:
        raise ValueError(
            f"Player count ({len(players)}) must be a multiple of 2*TEAM_SIZE "
            f"({match_size}) so every match has two full teams."
        )


def make_players(n: int, n_slots: int, seed: int, p_free: float = 0.7) -> list[Player]:
    """Generate reproducible players with ratings 1–10 and at least one free slot."""
    if n_slots < 1:
        raise ValueError("There must be at least one time slot.")
    if not 0 <= p_free <= 1:
        raise ValueError("p_free must be between 0 and 1.")
    rng = random.Random(seed)
    players = []
    for player_id in range(n):
        free = {slot for slot in range(n_slots) if rng.random() < p_free}
        if not free:
            free.add(rng.randrange(n_slots))
        players.append(Player(player_id, rng.randint(1, 10), frozenset(free)))
    return players


def load_players(path: str, n_slots: int) -> list[Player]:
    """Load name,rating,slots CSV rows; slots use semicolon-separated indices."""
    players = []
    with open(path, newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        required = {"name", "rating", "slots"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("CSV must have columns: name, rating, slots.")
        for idx, row in enumerate(reader):
            try:
                rating = int(row["rating"])
                slots = frozenset(int(x.strip()) for x in row["slots"].split(";") if x.strip())
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid rating or slots on CSV row {idx + 2}.") from exc
            if not 1 <= rating <= 10:
                raise ValueError(f"Rating on CSV row {idx + 2} must be from 1 to 10.")
            if not slots or any(slot < 0 or slot >= n_slots for slot in slots):
                raise ValueError(f"Slots on CSV row {idx + 2} must include a valid slot 0..{n_slots - 1}.")
            players.append(Player(idx, rating, slots, row["name"].strip() or None))
    return players


def match_cost(state: list[int], match: int, players: list[Player], team_size: int,
               n_slots: int, penalty: int = PENALTY) -> int:
    """Cost for one match: team rating gap plus unavailability penalties."""
    start = match * 2 * team_size
    team_a = state[start:start + team_size]
    team_b = state[start + team_size:start + 2 * team_size]
    gap = abs(sum(players[i].rating for i in team_a) - sum(players[i].rating for i in team_b))
    slot = match % n_slots
    unavailable = sum(slot not in players[i].free_slots for i in team_a + team_b)
    return gap + penalty * unavailable


def cost(state: list[int], players: list[Player], team_size: int, n_slots: int,
         penalty: int = PENALTY) -> int:
    validate_problem(players, team_size, n_slots)
    if len(state) != len(players) or set(state) != set(range(len(players))):
        raise ValueError("State must contain every player id exactly once.")
    return sum(match_cost(state, m, players, team_size, n_slots, penalty)
               for m in range(len(players) // (2 * team_size)))


def swap_delta(state: list[int], i: int, j: int, players: list[Player], team_size: int,
               n_slots: int, penalty: int = PENALTY) -> int:
    """Return swap cost change by re-scoring only the affected matches."""
    match_size = 2 * team_size
    affected = {i // match_size, j // match_size}
    before = sum(match_cost(state, m, players, team_size, n_slots, penalty) for m in affected)
    state[i], state[j] = state[j], state[i]
    after = sum(match_cost(state, m, players, team_size, n_slots, penalty) for m in affected)
    state[i], state[j] = state[j], state[i]
    return after - before


def hill_climb(players: list[Player], team_size: int, n_slots: int,
               rng: random.Random, start: Optional[list[int]] = None,
               penalty: int = PENALTY) -> tuple[list[int], int, list[int]]:
    """Steepest descent over all pair swaps, returning final state/cost/history."""
    validate_problem(players, team_size, n_slots)
    state = list(range(len(players))) if start is None else list(start)
    rng.shuffle(state) if start is None else None
    current = cost(state, players, team_size, n_slots, penalty)
    history = [current]
    while True:
        best_delta, best_pair = 0, None
        for i in range(len(state) - 1):
            for j in range(i + 1, len(state)):
                delta = swap_delta(state, i, j, players, team_size, n_slots, penalty)
                if delta < best_delta:
                    best_delta, best_pair = delta, (i, j)
        if best_pair is None:
            break
        i, j = best_pair
        state[i], state[j] = state[j], state[i]
        current += best_delta
        history.append(current)
    return state, current, history


def simulated_annealing(players: list[Player], team_size: int, n_slots: int,
                        rng: random.Random, start: Optional[list[int]] = None,
                        iters: int = 20_000, t_start: float = 10.0,
                        t_end: float = 0.05, penalty: int = PENALTY
                        ) -> tuple[list[int], int, list[int]]:
    """Random-swap annealing with geometric cooling; history records best cost."""
    validate_problem(players, team_size, n_slots)
    if iters < 1 or t_start <= 0 or t_end <= 0:
        raise ValueError("iters and both temperatures must be positive.")
    state = list(range(len(players))) if start is None else list(start)
    if start is None:
        rng.shuffle(state)
    current = cost(state, players, team_size, n_slots, penalty)
    best_state, best_cost = state.copy(), current
    history = [best_cost]
    for step in range(iters):
        i, j = rng.sample(range(len(state)), 2)
        delta = swap_delta(state, i, j, players, team_size, n_slots, penalty)
        fraction = step / max(1, iters - 1)
        temperature = t_start * (t_end / t_start) ** fraction
        if delta <= 0 or rng.random() < math.exp(-delta / temperature):
            state[i], state[j] = state[j], state[i]
            current += delta
            if current < best_cost:
                best_state, best_cost = state.copy(), current
        history.append(best_cost)
    return best_state, best_cost, history


def brute_force(players: list[Player], team_size: int, n_slots: int,
                penalty: int = PENALTY) -> tuple[list[int], int]:
    """Exhaustively check all player permutations; suitable only for small inputs."""
    validate_problem(players, team_size, n_slots)
    best_state, best_cost = None, math.inf
    for candidate in itertools.permutations(range(len(players))):
        value = cost(list(candidate), players, team_size, n_slots, penalty)
        if value < best_cost:
            best_state, best_cost = list(candidate), value
    return best_state or [], int(best_cost)


def random_assignment(players: list[Player], team_size: int, n_slots: int,
                      rng: random.Random) -> tuple[list[int], int]:
    state = list(range(len(players)))
    rng.shuffle(state)
    return state, cost(state, players, team_size, n_slots)


def format_schedule(state: list[int], players: list[Player], team_size: int,
                    n_slots: int) -> str:
    rows = []
    for m in range(len(players) // (2 * team_size)):
        offset = m * 2 * team_size
        a, b = state[offset:offset + team_size], state[offset + team_size:offset + 2 * team_size]
        slot = m % n_slots
        fmt = lambda ids: ", ".join(f"{players[i].label} ({players[i].rating})" for i in ids)
        bad = [players[i].label for i in a + b if slot not in players[i].free_slots]
        rows.append(f"Match {m + 1}, slot {slot}: Team A [{fmt(a)}] sum={sum(players[i].rating for i in a)}; "
                    f"Team B [{fmt(b)}] sum={sum(players[i].rating for i in b)}; "
                    f"difference={abs(sum(players[i].rating for i in a)-sum(players[i].rating for i in b))}; "
                    f"unavailable={', '.join(bad) if bad else 'none'}")
    return "\n".join(rows)


def experiment_demo(team_size: int = 2, players: Optional[list[Player]] = None,
                    n_slots: int = 2, seed: int = 7) -> None:
    players = players or make_players(2 * team_size * 2, n_slots, seed)
    validate_problem(players, team_size, n_slots)
    rng = random.Random(seed)
    start, start_cost = random_assignment(players, team_size, n_slots, rng)
    hc_state, hc_cost, _ = hill_climb(players, team_size, n_slots, random.Random(seed + 1), start)
    sa_state, sa_cost, _ = simulated_annealing(players, team_size, n_slots, random.Random(seed + 2), start)
    if len(players) <= 8:
        opt_state, opt_cost = brute_force(players, team_size, n_slots)
    else:
        opt_state, opt_cost = None, None
    print("Players:")
    for p in players:
        print(f"  {p.label}: rating={p.rating}, free slots={sorted(p.free_slots)}")
    schedules = [("Random start", start, start_cost), ("Hill climbing", hc_state, hc_cost),
                 ("Simulated annealing", sa_state, sa_cost)]
    if opt_state is not None:
        schedules.append(("Brute force optimum", opt_state, opt_cost))
    else:
        print("\nBrute force optimum skipped: exhaustive search is limited to 8 players in this demo.")
    for title, state, value in schedules:
        print(f"\n{title} (cost={value})\n{format_schedule(state, players, team_size, n_slots)}")


def experiment_accuracy(seed: int = 7, trials: int = 50, make_plot: bool = True) -> dict:
    hits = {"Hill climbing": 0, "Simulated annealing": 0}
    gaps = {name: [] for name in hits}
    stuck_example = None
    first_plot = None
    for trial in range(trials):
        players = make_players(8, 2, seed + trial, 0.7)
        opt_state, opt_cost = brute_force(players, 2, 2)
        start, _ = random_assignment(players, 2, 2, random.Random(seed + 10_000 + trial))
        hc_state, hc_value, hc_hist = hill_climb(players, 2, 2, random.Random(seed + 20_000 + trial), start)
        sa_state, sa_value, sa_hist = simulated_annealing(players, 2, 2,
                random.Random(seed + 30_000 + trial), start, iters=3000)
        for name, value in (("Hill climbing", hc_value), ("Simulated annealing", sa_value)):
            hits[name] += value == opt_cost
            gaps[name].append(value - opt_cost)
        if hc_value > opt_cost and stuck_example is None:
            stuck_example = (players, hc_state, hc_value, opt_cost)
        if first_plot is None:
            first_plot = (hc_hist, sa_hist)
    print(f"Accuracy over {trials} instances (8 players, 2 slots):")
    for name in hits:
        print(f"  {name}: {hits[name]}/{trials} reached optimum; mean gap={statistics.mean(gaps[name]):.3f}")
    if stuck_example:
        p, state, value, optimum = stuck_example
        print(f"\nHill-climbing local minimum (cost={value}, optimum={optimum}):\n{format_schedule(state, p, 2, 2)}")
    else:
        print("No hill-climbing run got stuck above the optimum in these instances.")
    if make_plot:
        _plot_accuracy(first_plot, hits, trials, seed)
    return {"hits": hits, "gaps": gaps, "stuck": stuck_example is not None}


def _plot_accuracy(histories, hits, trials, seed) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("Plot skipped: matplotlib is not installed (optional dependency).")
        return
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    # Required cost curves use one shared random start on the 32-player case.
    plot_players = make_players(32, 4, seed + 32)
    start, _ = random_assignment(plot_players, 2, 4, random.Random(seed + 32_001))
    _, _, hc = hill_climb(plot_players, 2, 4, random.Random(seed + 32_002), start)
    _, _, sa = simulated_annealing(plot_players, 2, 4, random.Random(seed + 32_003), start, iters=20_000)
    axes[0].plot(range(len(hc)), hc, label="Hill climbing")
    # Histories may have different lengths; use each algorithm's iteration index.
    axes[0].plot(range(len(sa)), sa, label="Simulated annealing")
    axes[0].set(title="Cost over iterations (32-player instance, shared start)", xlabel="Iteration", ylabel="Best cost")
    axes[0].legend()
    labels = list(hits)
    axes[1].bar(labels, [100 * hits[x] / trials for x in labels])
    axes[1].set(title="Runs reaching optimum", ylabel="Runs (%)")
    fig.tight_layout()
    fig.savefig("results.png", dpi=150)
    plt.close(fig)
    print("Saved plots to results.png (left panel uses the first 8-player accuracy instance).")


def experiment_scaling(seed: int = 7, runs: int = 20) -> None:
    print("Brute-force measurements:")
    measured_per_perm = None
    for n in (4, 8):
        players = make_players(n, 2, seed + n)
        started = time.perf_counter()
        brute_force(players, 1 if n == 4 else 2, 2)
        elapsed = time.perf_counter() - started
        per_perm = elapsed / math.factorial(n)
        if n == 8:
            measured_per_perm = per_perm
        print(f"  N={n}: measured {elapsed:.6f} seconds")
    for n in (12, 16, 20, 32):
        estimate = measured_per_perm * math.factorial(n)
        print(f"  N={n}: ESTIMATE {estimate:.6g} seconds (measured N=8 time per permutation times N!)")
    n, slots, team_size = 32, 4, 2
    players = make_players(n, slots, seed + 32)
    results = {method: {"costs": [], "times": []} for method in ("Random baseline", "Hill climbing", "Simulated annealing")}
    for run in range(runs):
        for method, fn in (
            ("Random baseline", lambda rng: random_assignment(players, team_size, slots, rng)),
            ("Hill climbing", lambda rng: hill_climb(players, team_size, slots, rng)),
            ("Simulated annealing", lambda rng: simulated_annealing(players, team_size, slots, rng, iters=5000)),
        ):
            rng = random.Random(seed + run * 100 + len(method))
            started = time.perf_counter()
            _, value = fn(rng)[:2]
            results[method]["times"].append(time.perf_counter() - started)
            results[method]["costs"].append(value)
    print(f"\n32-player comparison over {runs} seeds (lower cost is better):")
    for name, data in results.items():
        print(f"  {name}: mean cost={statistics.mean(data['costs']):.2f}, best cost={min(data['costs'])}, "
              f"mean time={statistics.mean(data['times']):.4f}s")


def run_all(args) -> None:
    if args.csv:
        players = load_players(args.csv, args.slots)
    else:
        players = make_players(args.players, args.slots, args.seed)
    validate_problem(players, args.team_size, args.slots)
    experiment_demo(args.team_size, players, args.slots, args.seed)
    print("\n=== Accuracy ===")
    experiment_accuracy(args.seed)
    print("\n=== Scaling ===")
    experiment_scaling(args.seed)


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Fair Match-Maker local-search project")
    parser.add_argument("command", nargs="?", choices=("demo", "accuracy", "scaling", "all"), default="all")
    parser.add_argument("--team-size", type=int, default=2)
    parser.add_argument("--players", type=int, default=8)
    parser.add_argument("--slots", type=int, default=2)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--csv", metavar="PATH")
    args = parser.parse_args(argv)
    try:
        if args.csv:
            players = load_players(args.csv, args.slots)
        elif args.command == "demo":
            players = make_players(args.players, args.slots, args.seed)
        else:
            players = None
        if players is not None:
            validate_problem(players, args.team_size, args.slots)
        if args.command == "demo":
            experiment_demo(args.team_size, players, args.slots, args.seed)
        elif args.command == "accuracy":
            experiment_accuracy(args.seed)
        elif args.command == "scaling":
            experiment_scaling(args.seed)
        else:
            run_all(args)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
