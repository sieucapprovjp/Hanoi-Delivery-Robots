# Technology Stack

This document records the current runtime, libraries, and development tools used by
the AI Delivery Robots simulation.

## Backend

| Component | Version / Source | Purpose |
| :--- | :--- | :--- |
| Python | 3.10+ recommended | Main backend language |
| Flask | `3.0.0` | REST API and web app server |
| OSMnx | `2.1.0` | OpenStreetMap graph loading |
| NetworkX | `3.6.1` | Road graph representation and graph search support |
| scikit-learn | `requirements.txt` | K-means hub optimization and BallTree nearest-node index |
| NumPy | `requirements.txt` | Numeric arrays and spatial lookup support |
| unittest | Python stdlib | Test framework |

The backend does not currently require Flask-SocketIO or SimPy for the active browser
simulation path. The live simulation loop is handled in the frontend, while Flask
serves routing, dispatch, environment, logging, metrics, and optimization APIs.

## Frontend

| Component | Purpose |
| :--- | :--- |
| HTML/CSS | Application shell and dashboard styling |
| Vanilla JavaScript | Simulation loop, robot state, API client, and map layers |
| Alpine.js | Lightweight UI state and panel rendering |
| Leaflet | Interactive Hoan Kiem map, markers, routes, and overlays |

Frontend code is split by domain under `delivery_robots/static/js/`:

- `core`
- `environment`
- `insider`
- `map`
- `robot`
- `simulation`

## Runtime Data

- OSM graph cache: `cache/`
- Persistent event logs: `logs/app-events.jsonl`
- Persistent delivery history: `logs/delivery-history.jsonl`

`cache/` and `logs/` are runtime artifacts and are ignored by Git.

## Development Commands

```powershell
python main.py
python -m unittest discover -s tests
python -m compileall -q delivery_robots tests
Get-ChildItem delivery_robots/static/js -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
```
