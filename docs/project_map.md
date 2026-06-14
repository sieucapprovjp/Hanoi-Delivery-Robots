# Project Map

This document maps the current repository structure and the role of each major file.

```text
AI-Intro/
├── main.py
├── requirements.txt
├── README.md
├── docs/
│   ├── codex.md
│   ├── architecture.md
│   ├── api_docs.md
│   ├── backend_documentation.md
│   ├── convention.md
│   ├── database_schema.md
│   ├── error_handling.md
│   ├── kmeans_plan.md
│   ├── prd.md
│   ├── project_map.md
│   ├── tech_stack.md
│   ├── testing_strategy.md
│   ├── vrp_implementation_plan.md
│   └── vrp_research.md
├── delivery_robots/
│   ├── app.py
│   ├── config.py
│   ├── algorithms/
│   │   ├── classical.py
│   │   ├── insider.py
│   │   ├── weighted_search.py
│   │   └── dispatch/
│   │       ├── allocation.py
│   │       ├── constraints.py
│   │       ├── vrp_solver.py
│   │       └── xai.py
│   ├── core/
│   │   ├── environment.py
│   │   ├── graph.py
│   │   └── hubs.py
│   ├── routes/
│   │   ├── environment_routes.py
│   │   └── main_routes.py
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/
│   │       ├── core/
│   │       ├── environment/
│   │       ├── insider/
│   │       ├── map/
│   │       ├── robot/
│   │       └── simulation/
│   ├── templates/index.html
│   └── utils/
│       ├── geo.py
│       ├── metrics.py
│       ├── persistent_log.py
│       ├── route_analysis.py
│       └── validation.py
├── tests/
│   ├── test_api.py
│   ├── test_classical_ai.py
│   ├── test_dispatch_allocation.py
│   ├── test_dispatch_constraints.py
│   ├── test_environment.py
│   ├── test_insider.py
│   ├── test_persistent_log.py
│   ├── test_route_analysis.py
│   ├── test_validation.py
│   └── test_vrp.py
├── cache/
└── logs/
```

## Important Backend Files

- `main.py`: starts the app.
- `delivery_robots/app.py`: creates the Flask app, shared state, locks, metrics, graph state, and registers routes.
- `delivery_robots/config.py`: central constants for graph loading, route penalties, dispatch, robot capacity, VRP, and logging.
- `delivery_robots/core/graph.py`: OSMnx graph loading, projection, cache, and nearest-node indexing.
- `delivery_robots/core/environment.py`: traffic, rain, obstacle, rush-hour, and road-memory weighting.
- `delivery_robots/core/hubs.py`: K-means hub optimization.
- `delivery_robots/algorithms/weighted_search.py`: production A*, Dijkstra, and GBFS routing.
- `delivery_robots/algorithms/classical.py`: base-distance algorithm comparison.
- `delivery_robots/algorithms/insider.py`: A* step trace and insider comparison data.
- `delivery_robots/algorithms/dispatch/allocation.py`: CSP filtering, priority scoring, candidate expansion, assignment, and VRP integration.
- `delivery_robots/algorithms/dispatch/constraints.py`: reusable dispatch feasibility checks.
- `delivery_robots/algorithms/dispatch/vrp_solver.py`: Simulated Annealing VRP/PDP sequencing.
- `delivery_robots/algorithms/dispatch/xai.py`: dispatch explanation records.
- `delivery_robots/utils/route_analysis.py`: snap-to-road, route geometry, segment geometry, and cost breakdown.
- `delivery_robots/utils/persistent_log.py`: JSONL append helpers.

## Important Frontend Folders

- `static/js/core/`: application bootstrap, config, REST client, route helpers.
- `static/js/environment/`: controls for rain, traffic, and obstacles.
- `static/js/map/`: Leaflet map setup, charging hubs, delivery markers, weather and traffic layers.
- `static/js/robot/`: robot state machine, movement, capacity, popup/card rendering.
- `static/js/simulation/`: delivery creation, dispatch calls, queue management, simulation view updates.
- `static/js/insider/`: A* expansion view and XAI/VRP timeline.

## Generated/Ignored Runtime Data

- `cache/`: OSMnx graph cache.
- `logs/app-events.jsonl`: persistent app and dispatch events.
- `logs/delivery-history.jsonl`: persistent pickup/dropoff history for later analysis.
- `__pycache__/`: Python bytecode cache.
