# AI Delivery Robots - Academic Simulation

An interactive AI simulation of autonomous delivery robots in Hoan Kiem District, Hanoi, built for introductory AI coursework. The project focuses on classical search algorithms, runtime comparison, and explainable metrics under dynamic environment conditions.

## What This App Demonstrates

- Fleet-wide routing algorithm comparison: A*, Dijkstra, and GBFS.
- Dynamic path costs under rain, traffic, and obstacle penalties.
- Real-time multi-robot dispatch and rerouting behavior.
- K-means based hub optimization from historical pickup/dropoff points.
- Academic insights panel with runtime metrics and efficiency scoring.

## Core AI Features

- **Classical search routing**
  - `A*`: `f(n) = g(n) + h(n)`
  - `Dijkstra`: priority by `g(n)`
  - `GBFS`: priority by `h(n)`
  - Heuristic `h(n)` uses Haversine distance.

- **Fleet benchmark mode**
  - Apply one routing algorithm to all robots at once.
  - Compare average runtime, nodes explored, path cost, reroutes, and deliveries.

- **Efficiency score**
  - `score = deliveries / (costKm + 0.02*avgTimeMs + 0.005*avgNodes + 0.5*reroutes + 1)`
  - Higher score indicates better operational efficiency under current conditions.

- **RL-lite road memory**
  - Robots remember slow road segments and bias future routing costs.

- **K-means hub optimization**
  - Collect delivery coordinates and compute optimized hub centroids.
  - Reposition robots toward demand hotspots.

## Current UI Focus (Simplified for Demo)

- Kept visible:
  - Delivery control panel
  - Fleet algorithm selector
  - Academic insights panel
  - Robot computing panel
  - Weather panel (rain and traffic)

- Hidden to reduce clutter:
  - Delivery queue panel
  - Fleet analytics panel
  - Legacy event log panel
  - Insider panel

## Tech Stack

- Backend: Flask, NetworkX, OSMnx
- Frontend: Vanilla JS, Leaflet
- ML: scikit-learn (KMeans), NumPy

## Project Layout

```text
delivery_robots/
  app.py                Flask app, routing, k-means hub API
  routes_api.py         Environment, metrics, logs, utility APIs
  classical_ai.py       Classical algorithm comparison helpers
  static/js/
    app.js              UI wiring and controls
    simulation.js       Multi-robot simulation engine
    robot.js            Robot agent behavior and computing details
    map.js              Leaflet map and overlays
    pathfinding.js      Routing API client
  templates/
    index.html          Main UI
main.py                 Local runner entrypoint
requirements.txt        Dependencies
```

## Setup

### Prerequisites

- Python 3.10+
- pip

### Install

```bash
pip install -r requirements.txt
```

### Run

```bash
python main.py
```

Then open the printed URL (default: `http://127.0.0.1:5001`).

## Key API Endpoints

- Routing
  - `GET /api/route?fromLat=&fromLon=&toLat=&toLon=&algo=astar|dijkstra|gbfs`
  - `GET /api/snap?lat=&lon=`

- Environment
  - Rain: `/api/rain/list`, `/api/rain/add`, `/api/rain/randomize`, `/api/rain/clear`
  - Traffic: `/api/traffic/list`, `/api/traffic/add`, `/api/traffic/randomize`, `/api/traffic/clear`
  - Obstacles: `/api/obstacle/list`, `/api/obstacle/add`, `/api/obstacle/randomize`, `/api/obstacle/clear`

- Metrics and clocks
  - `GET /api/metrics`
  - `GET /api/clock`

- Academic compare
  - `GET /api/classical/compare`
  - `GET /api/insider`
  - `GET /api/astep`

- K-means hub optimization
  - `POST /api/log_delivery`
  - `POST /api/optimize-hubs`

- Unified API logs
  - `POST /api/logs`
  - `GET /api/logs?limit=200`

## Suggested Demo Flow

1. Start simulation.
2. Pick fleet routing algorithm and apply to all robots.
3. Open Academic Insights to compare runtime metrics.
4. Add rain/traffic to increase search complexity.
5. Run Optimize Hubs and observe repositioning.
6. Query `/api/logs` to inspect API-level event traces.

## License

MIT
