# Fair Match-Maker

A small Python 3 project for a university AI course module on local search. It puts players into balanced teams and assigns each match a fixed time slot. Player ratings are supplied or generated inputs; the program does not measure skill.

## Run it

```text
python matchmaker.py demo
python matchmaker.py accuracy
python matchmaker.py scaling
python matchmaker.py all
python matchmaker.py demo --team-size 1 --players 8 --slots 2 --seed 7
python matchmaker.py demo --team-size 5 --players 30 --slots 3
python matchmaker.py demo --csv players.csv --team-size 2 --slots 2
python test_matchmaker.py
```

## Web application

The Flask interface lets you edit player names, ratings, availability, team size, and time slots, then view real schedules and compare search costs.

```text
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5000>. Hill climbing and simulated annealing are compared with the same random start and a random-assignment baseline. Brute force can be selected for at most 8 players. The web app accepts up to 32 players and 12 slots. Flask is the only added runtime dependency; no database, remote service, or account is used. Stop the local server with Ctrl+C.

With no command, the program runs `all`. Use `--seed` to reproduce generated inputs and random-search runs. CSV files need `name,rating,slots` columns; list available zero-based slot numbers with semicolons, for example `0;2`.

## What the experiments show

- `demo` prints a random schedule, hill-climbing schedule, simulated-annealing schedule, and exhaustive optimum for the selected instance.
- `accuracy` compares both local searches with brute force on 50 seeded 8-player instances, reports optimum hits and mean gaps, and prints an actual hill-climbing local minimum when one occurs.
- `scaling` measures brute force at 4 and 8 players, labels extrapolations for larger sizes as estimates, and compares local search with random assignment on 32 players.
- `all` runs all three experiments. If matplotlib is installed, an optional plot is saved as `results.png`; otherwise the program continues and says the plot was skipped.

## Model and limitations

The state is a permutation of player IDs, grouped match by match. Each match's first `TEAM_SIZE` positions form Team A and the next positions form Team B. Match `m` is assigned slot `m mod S`. Cost is the absolute difference between team rating totals plus a default penalty of 100 for every player unavailable in that slot. A swap's cost delta only re-scores the one or two affected matches.

Balance is by total rating only (no positions or chemistry); the slot of each match is fixed by its index; simulated annealing is a heuristic with hand-chosen settings and no guarantee of optimality; brute-force times beyond N=8 are estimates. Brute force is factorial and should only be used on small instances. Hill climbing can stop at a local minimum. The optional plotting dependency is matplotlib; all other functionality uses the Python standard library.
