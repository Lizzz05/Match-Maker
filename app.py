"""Small Flask API and page server for Fair Match-Maker."""

import random
import time

from flask import Flask, jsonify, render_template, request

from matchmaker import (
    PENALTY,
    Player,
    brute_force,
    cost,
    hill_climb,
    random_assignment,
    simulated_annealing,
    validate_problem,
)


app = Flask(__name__)


def _read_problem(data):
    """Validate request JSON and convert the roster to existing Player objects."""
    if not isinstance(data, dict):
        raise ValueError("Send a JSON object with players, team_size, and slots.")
    try:
        team_size = int(data.get("team_size"))
        n_slots = int(data.get("slots"))
        seed = int(data.get("seed", 7))
    except (TypeError, ValueError):
        raise ValueError("Team size, slot count, and seed must be whole numbers.")
    raw_players = data.get("players")
    if not isinstance(raw_players, list) or not raw_players:
        raise ValueError("Add at least one player.")
    if len(raw_players) > 32:
        raise ValueError("The web app supports up to 32 players per run.")
    players = []
    for idx, row in enumerate(raw_players, 1):
        if not isinstance(row, dict):
            raise ValueError(f"Player {idx} has invalid data.")
        try:
            rating = int(row.get("rating"))
        except (TypeError, ValueError):
            raise ValueError(f"Player {idx}: rating must be a whole number from 1 to 10.")
        if not 1 <= rating <= 10:
            raise ValueError(f"Player {idx}: rating must be from 1 to 10.")
        name = str(row.get("name", "")).strip() or f"Player {idx}"
        slots = row.get("free_slots")
        if not isinstance(slots, list) or not slots:
            raise ValueError(f"{name}: choose at least one available slot.")
        try:
            free_slots = frozenset(int(slot) for slot in slots)
        except (TypeError, ValueError):
            raise ValueError(f"{name}: availability must contain valid slot numbers.")
        if any(slot < 0 or slot >= n_slots for slot in free_slots):
            raise ValueError(f"{name}: choose slots between 0 and {n_slots - 1}.")
        players.append(Player(idx - 1, rating, free_slots, name))
    validate_problem(players, team_size, n_slots)
    if n_slots > 12:
        raise ValueError("Choose 12 time slots or fewer for this demo.")
    return players, team_size, n_slots, seed


def _schedule(state, players, team_size, n_slots):
    matches = []
    for match_id in range(len(players) // (2 * team_size)):
        start = match_id * 2 * team_size
        a_ids = state[start:start + team_size]
        b_ids = state[start + team_size:start + 2 * team_size]
        slot = match_id % n_slots

        def describe(ids):
            return [
                {"id": players[i].id, "name": players[i].label, "rating": players[i].rating,
                 "free_slots": sorted(players[i].free_slots), "available": slot in players[i].free_slots}
                for i in ids
            ]

        team_a, team_b = describe(a_ids), describe(b_ids)
        sum_a = sum(player["rating"] for player in team_a)
        sum_b = sum(player["rating"] for player in team_b)
        unavailable = [p["name"] for p in team_a + team_b if not p["available"]]
        matches.append({
            "number": match_id + 1, "slot": slot,
            "team_a": team_a, "team_b": team_b,
            "sum_a": sum_a, "sum_b": sum_b,
            "imbalance": abs(sum_a - sum_b), "unavailable": unavailable,
        })
    return matches


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/match")
def match():
    try:
        players, team_size, n_slots, seed = _read_problem(request.get_json(silent=True))
        algorithm = request.get_json().get("algorithm", "hill_climbing")
        if algorithm not in {"hill_climbing", "simulated_annealing", "brute_force"}:
            raise ValueError("Choose hill climbing, simulated annealing, or brute force.")
        if algorithm == "brute_force" and len(players) > 8:
            raise ValueError("Brute force is available for 8 players or fewer.")

        start, baseline_cost = random_assignment(players, team_size, n_slots, random.Random(seed))
        comparison = [{"name": "Random assignment", "cost": baseline_cost}]
        outcomes = {}
        if algorithm == "brute_force":
            started = time.perf_counter()
            state, value = brute_force(players, team_size, n_slots)
            outcomes[algorithm] = {"state": state, "cost": value, "seconds": time.perf_counter() - started}
        else:
            for key, fn in (("hill_climbing", hill_climb), ("simulated_annealing", simulated_annealing)):
                started = time.perf_counter()
                state, value, _ = fn(players, team_size, n_slots, random.Random(seed + (1 if key == "hill_climbing" else 2)), start)
                outcomes[key] = {"state": state, "cost": value, "seconds": time.perf_counter() - started}
                comparison.append({"name": "Hill climbing" if key == "hill_climbing" else "Simulated annealing",
                                   "cost": value})
        outcome = outcomes[algorithm]
        labels = {"hill_climbing": "Hill climbing", "simulated_annealing": "Simulated annealing",
                  "brute_force": "Brute-force optimum"}
        return jsonify({
            "algorithm": algorithm, "algorithm_name": labels[algorithm], "cost": outcome["cost"],
            "seconds": round(outcome["seconds"], 4), "matches": _schedule(outcome["state"], players, team_size, n_slots),
            "comparison": comparison,
            "players": [{"name": p.label, "rating": p.rating, "free_slots": sorted(p.free_slots)} for p in players],
            "penalty": PENALTY,
        })
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400


if __name__ == "__main__":
    app.run(debug=True, port=5000)
