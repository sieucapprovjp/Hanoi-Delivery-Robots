# Testing Strategy

The project uses Python `unittest` plus syntax checks for Python and frontend
JavaScript.

## Test Commands

```powershell
python -m unittest discover -s tests
python -m compileall -q delivery_robots tests
Get-ChildItem delivery_robots/static/js -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
```

## Test Coverage Areas

| File | Main Coverage |
| :--- | :--- |
| `tests/test_validation.py` | Coordinate, radius, count, and payload validation |
| `tests/test_api.py` | Flask API smoke tests and route validation |
| `tests/test_route_analysis.py` | Route response geometry and cost breakdown |
| `tests/test_classical_ai.py` | Classical A*, Dijkstra, GBFS, BFS behavior |
| `tests/test_environment.py` | Traffic, rain, obstacle, and time-based penalties |
| `tests/test_insider.py` | A* step trace and insider comparison behavior |
| `tests/test_dispatch_constraints.py` | CSP feasibility checks |
| `tests/test_dispatch_allocation.py` | Dispatch scoring, candidate filtering, XAI, and batch assignment |
| `tests/test_vrp.py` | VRP/PDP sequence building, precedence, greedy seed, SA solver |
| `tests/test_persistent_log.py` | JSONL append behavior |

## Graph Mocking Rules

Tests must avoid live OpenStreetMap downloads. Use small `networkx.MultiDiGraph`
fixtures with:

- node `y` and `x` attributes
- edge `length` attributes
- predictable connectivity

When nearest-node behavior is relevant, inject or mock lookup helpers so tests do not
depend on OSMnx network access.

## Backend Test Expectations

- Route tests should check both path shape and cost semantics.
- Environment tests should verify penalty direction and boundary behavior.
- Dispatch tests should verify rejected candidates, selected candidates, and returned explanation payloads.
- VRP tests should verify pickup-before-dropoff precedence and finite fallback behavior when some matrix entries are unreachable.

## Frontend Verification

There is no formal frontend test runner yet. For frontend changes:

- run `node --check` over all JS files
- start `python main.py`
- smoke the browser on `http://127.0.0.1:5002`
- verify map renders, robots move, dispatch works, and XAI/VRP panels render without console errors
