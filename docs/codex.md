# codex.md

## File Purpose
- Record the current project state for future Codex sessions.
- Provide a quick technical snapshot before planning or implementing new work.
- Canonical path for future sessions: `docs/codex.md`.
- Project root for all paths below: repository root.
- Future Codex sessions should read this file first, then inspect the specific files related to the requested change.
- This file does not replace `README.md`, detailed technical docs, or implementation plans.

## Project Summary
- Project name: AI Delivery Robots - Hoan Kiem District Simulation.
- Academic context: Intro AI project focused on practical AI concepts in a delivery robot fleet simulation.
- Main objective: simulate multi-agent delivery robots that route, reroute, allocate deliveries, and react to a dynamic city environment.
- Domain map: Hoan Kiem district, Hanoi, loaded from OpenStreetMap through OSMnx.
- Backend stack: Python, Flask, NetworkX, OSMnx, scikit-learn, NumPy.
- Frontend stack: Vanilla JavaScript, Alpine.js, Leaflet.
- Primary entrypoint: `main.py`.

## Working Rules For Codex

### Scope And Architecture
- Keep changes small and aligned with the current Flask/module structure.
- Prefer existing helpers in `delivery_robots/core`, `delivery_robots/utils`, and `delivery_robots/algorithms` over adding duplicate logic.
- Backend route handlers should stay thin: validate input, call domain helpers, and return JSON.
- Shared mutable runtime state should flow through `app_state` and the existing lock pattern in `delivery_robots/app.py`.
- Route calculations should use the existing route response contract from `build_route_response`.
- Do not add a new framework or heavy dependency unless the feature clearly needs it for an Intro AI concept.

### AI Project Priorities
- Prioritize features that are easy to explain in an Intro AI demo:
  - Search: A*, Dijkstra, GBFS, BFS comparison.
  - Dynamic cost functions: traffic, rain, obstacles, road memory.
  - Unsupervised learning: K-means hub optimization.
  - CSP: dispatch constraints for robot status, battery, capacity, and pickup distance.
  - XAI: readable decision explanations and timelines.
  - VRP/PDP: multi-order routing and pickup-before-dropoff constraints, if implemented later.
- When adding an AI feature, expose both the behavior and the explanation/metric needed to present it.

### Required Change Report
- Every change report should list changed files.
- Every change report should describe which behavior or API contract changed.
- Every change report should include verification commands or browser steps.
- For frontend changes, include a local browser smoke test when practical.
- For backend changes, run the focused unit tests and, when feasible, the full test suite.

### Test Commands
- Full Python tests:
  ```bash
  python -m unittest discover -s tests
  ```
- Python syntax check:
  ```bash
  python -m compileall -q delivery_robots tests
  ```
- JavaScript syntax check:
  ```bash
  Get-ChildItem delivery_robots/static/js -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
  ```

## Completed Features

### Flask Application And State
- `delivery_robots/app.py` initializes the Flask app, shared app state, locks, metrics, logs, graph state, and route registration.
- Runtime state is centralized in `_app_state`.
- A `before_request` hook synchronizes module globals into `_app_state` so routes use the latest state.
- Environment snapshots are available for route requests and dispatch so one request sees a consistent traffic/rain/obstacle state.
- Related files:
  - `main.py`
  - `delivery_robots/app.py`
  - `delivery_robots/routes/main_routes.py`
  - `delivery_robots/routes/environment_routes.py`

### Road Graph And Spatial Lookup
- The app loads a bike-network road graph centered around Hoan Kiem.
- OSMnx graph loading is cached on disk under ignored `cache/` when enabled.
- Graph projection is done once during startup/lazy graph load.
- Nearest-node lookup uses a `BallTree` spatial index when available and falls back to OSMnx or a manual Haversine scan.
- Related files:
  - `delivery_robots/core/graph.py`
  - `delivery_robots/utils/route_analysis.py`
  - `delivery_robots/config.py`
  - `.gitignore`

### Dynamic Environment
- The environment can model rush-hour traffic, dynamic traffic routes, rain zones, and obstacles.
- Edge weights multiply base edge length by traffic, rain, and obstacle penalties.
- Route response cost breakdown attributes the multiplicative model in sequence:
  - base distance
  - traffic penalty
  - rain penalty after traffic
  - obstacle penalty after traffic and rain
- API endpoints exist to list, add, randomize, and clear rain, traffic, and obstacles.
- Related files:
  - `delivery_robots/core/environment.py`
  - `delivery_robots/routes/environment_routes.py`
  - `delivery_robots/utils/route_analysis.py`
  - `tests/test_route_analysis.py`

### Production Routing
- Production routing supports A*, Dijkstra, and Greedy Best-First Search.
- Valid production algorithm IDs are `astar`, `dijkstra`, and `gbfs`.
- The API also accepts `greedy` as an alias and normalizes it to `gbfs`.
- Production route search accepts a dynamic weight function, so traffic/rain/obstacle and robot road memory can affect the chosen path.
- `/api/route` returns path, distance, algorithm ID, timing, nodes explored, path cost, and cost breakdown.
- Related files:
  - `delivery_robots/algorithms/weighted_search.py`
  - `delivery_robots/routes/main_routes.py`
  - `delivery_robots/config.py`
  - `tests/test_api.py`

### Classical AI Comparison
- Classical implementations exist for Dijkstra, A*, GBFS, and BFS.
- Classical comparison intentionally uses base physical edge length only, without rain/traffic/obstacle penalties.
- `/api/classical/compare` returns algorithm metrics for academic comparison.
- BFS is used for classical/insider comparison, not as a production fleet route algorithm.
- Related files:
  - `delivery_robots/algorithms/classical.py`
  - `delivery_robots/routes/main_routes.py`
  - `tests/test_classical_ai.py`

### Insider And Search Visualization
- A* step demo records selected node, `g`, `h`, `f`, open set size, closed set size, and final path data.
- Insider comparison runs A*, Dijkstra, GBFS, and BFS with environment penalties for explainability.
- The frontend can render step-by-step A* overlays and algorithm comparison tables.
- Related files:
  - `delivery_robots/algorithms/insider.py`
  - `delivery_robots/routes/main_routes.py`
  - `delivery_robots/static/js/core/app.js`
  - `delivery_robots/static/js/insider/insider_panel.js`
  - `delivery_robots/templates/index.html`

### Dispatch CSP And XAI
- Dispatch assigns pending deliveries to idle robots using a priority-aware scoring model.
- Delivery priority considers pickup category, dropoff category, and wait time.
- CSP filters reject robots that violate:
  - required status: `idle`
  - minimum battery percent
  - capacity rule: `currentLoad < capacity`
  - maximum pickup distance
- Feasible robots are pre-scored before expensive pathfinding.
- Only the top route candidates are expanded, with an extra candidate for high-priority orders.
- Final score minimizes route cost plus weighted battery risk minus weighted delivery priority.
- Dispatch response includes route payloads so the frontend does not need an extra route request after assignment.
- When `return_explanations=True`, dispatch returns both `assignments` and XAI `explanations`.
- Related files:
  - `delivery_robots/algorithms/dispatch/allocation.py`
  - `delivery_robots/routes/main_routes.py`
  - `delivery_robots/static/js/simulation/simulation.js`
  - `delivery_robots/static/js/simulation/dispatch_client.js`
  - `delivery_robots/templates/index.html`
  - `delivery_robots/static/css/style.css`
  - `tests/test_dispatch_allocation.py`

### VRP/PDP Batch Routing
- Dispatch can batch multiple pending deliveries onto one robot when queue pressure exceeds available idle robots.
- Each robot is capped by both physical capacity and `VRP_MAX_ORDERS_PER_ROBOT`; the current demo cap is 3 active orders per robot.
- The backend solves pickup/dropoff sequencing with a Simulated Annealing VRP/PDP helper while enforcing pickup-before-dropoff precedence.
- VRP distance matrices use the same weighted routing stack as production dispatch, so rain, traffic, obstacles, and road memory affect batch costs.
- Dispatch responses can include `deliveryIds`, `orderSequence`, `routeSequence`, `vrpStats`, `vrpCost`, and initial/final improvement metrics.
- The frontend supports multi-stop robot execution, charging resume, active order display, next-stop/stop-progress display, and VRP XAI timeline visibility.
- Related files:
  - `delivery_robots/algorithms/dispatch/vrp_solver.py`
  - `delivery_robots/algorithms/dispatch/allocation.py`
  - `delivery_robots/static/js/robot/robot.js`
  - `delivery_robots/static/js/robot/renderers.js`
  - `delivery_robots/static/js/simulation/simulation.js`
  - `delivery_robots/static/js/insider/xai_timeline.js`
  - `tests/test_vrp.py`
  - `tests/test_dispatch_allocation.py`

### K-means Hub Optimization
- The app records pickup/dropoff coordinates from generated deliveries.
- `/api/optimize-hubs` runs K-means with a default of 5 clusters.
- Optimized hub centroids are returned as AI hubs and synced into charging stations.
- The frontend can reposition robots to optimized hubs and draw hub markers/rings on the map.
- Related files:
  - `delivery_robots/core/hubs.py`
  - `delivery_robots/routes/main_routes.py`
  - `delivery_robots/static/js/simulation/simulation.js`
  - `delivery_robots/static/js/map/map.js`
  - `delivery_robots/static/js/map/delivery_layer.js`
  - `docs/kmeans_plan.md`

### Robot Simulation
- The frontend creates 5 robots and an initial delivery queue.
- Deliveries are generated from weighted location categories such as restaurant, market, office, hotel, landmark, retail, and residential.
- Robots move along route paths, consume battery, reroute under bad traffic/rain, and go to charging stations when battery is low.
- Robot road memory stores experienced bad segments and sends memory penalties to route requests.
- Fleet algorithm can be switched between A*, Dijkstra, and GBFS for comparative simulation.
- Related files:
  - `delivery_robots/static/js/simulation/simulation.js`
  - `delivery_robots/static/js/simulation/delivery_factory.js`
  - `delivery_robots/static/js/robot/robot.js`
  - `delivery_robots/static/js/core/pathfinding.js`
  - `delivery_robots/static/js/map/map.js`
  - `delivery_robots/static/js/core/config.js`
  - `delivery_robots/templates/index.html`

### Metrics And Logs
- Backend metrics track route calculation time, nodes explored, path lengths, and graph/environment counts.
- Frontend metrics track completed deliveries, route time, nodes, path cost, reroutes, and efficiency score.
- Efficiency score formula:
  ```text
  Deliveries / (Distance_Km + 0.02*Time_ms + 0.005*Nodes_Explored + 0.5*Reroutes + 1)
  ```
- `/api/logs` stores UI and dispatch events in an in-memory bounded queue.
- UI events and delivery history are also appended to JSONL files under ignored `logs/` for lightweight persistent analysis without a database.
- Related files:
  - `delivery_robots/utils/metrics.py`
  - `delivery_robots/utils/persistent_log.py`
  - `delivery_robots/routes/environment_routes.py`
  - `delivery_robots/routes/main_routes.py`
  - `delivery_robots/static/js/simulation/simulation.js`
  - `delivery_robots/static/js/core/app.js`

### API Surface
- Main API endpoints:
  - `GET /api/route`
  - `GET /api/snap`
  - `POST /api/log_delivery`
  - `POST /api/dispatch/assign`
  - `POST /api/optimize-hubs`
  - `GET /api/astep`
  - `GET /api/insider`
  - `GET /api/classical/compare`
- Environment and operations endpoints:
  - `GET /api/health`
  - `GET /api/logs`
  - `POST /api/logs`
  - `GET /api/metrics`
  - `GET /api/clock`
  - `GET /api/charging-stations`
  - `PUT /api/charging-stations/<station_id>`
  - `GET /api/traffic`
  - `GET /api/weather`
  - `GET /api/rain/list`
  - `POST /api/rain/add`
  - `POST /api/rain/randomize`
  - `POST /api/rain/clear`
  - `GET /api/traffic/list`
  - `POST /api/traffic/add`
  - `POST /api/traffic/randomize`
  - `POST /api/traffic/clear`
  - `GET /api/obstacle/list`
  - `POST /api/obstacle/add`
  - `POST /api/obstacle/randomize`
  - `POST /api/obstacle/clear`

### Tests
- Unit/integration tests cover validation, API basics, route analysis cost breakdown, classical AI, and dispatch allocation.
- Current known full test result after recent optimization work: 17 tests passing with `python -m unittest discover -s tests`.
- Related files:
  - `tests/test_validation.py`
  - `tests/test_api.py`
  - `tests/test_route_analysis.py`
  - `tests/test_classical_ai.py`
  - `tests/test_dispatch_allocation.py`

## Documentation Inventory
- `README.md`: high-level project overview, setup, metric formula, roadmap, and folder structure.
- `docs/backend_documentation.md`: backend architecture, core modules, algorithms, APIs, and utilities.
- `docs/ai_instructions.md`: AI-agent coding constraints, testing rules, thread-safety guidance, and performance notes.
- `docs/api_docs.md`: REST API and planned WebSocket contract reference.
- `docs/architecture.md`: high-level architecture, data flow, component layout, and dynamic weighting math.
- `docs/convention.md`: backend/frontend coding standards, naming conventions, lock usage, and styling conventions.
- `docs/database_schema.md`: in-memory app state, robot/task/environment models, and lock map.
- `docs/error_handling.md`: validation, HTTP error response patterns, and logging strategy.
- `docs/kmeans_plan.md`: implemented K-means hub optimization notes, API contracts, demo walkthrough, and improvement ideas.
- `docs/prd.md`: product requirements, user stories, functional requirements, and edge cases.
- `docs/project_map.md`: intended module map and file-purpose overview. Some listed paths describe a target/older structure and may differ from the current repo.
- `docs/tech_stack.md`: documented backend/frontend stack and development tooling.
- `docs/testing_strategy.md`: unittest strategy, graph mocking rules, and endpoint test expectations.
- `docs/vrp_research.md`: research notes for TSP, VRP, PDP, Simulated Annealing, precedence constraints, and how they map onto this project.
- `docs/vrp_implementation_plan.md`: detailed implementation plan for future VRP/TSP with Simulated Annealing.
- `docs/codex.md`: current concise memory file for Codex sessions.

## Current Not-Implemented Items
- Advanced K-means controls such as manual `K`, Auto-K/Elbow, and before/after empty-distance metrics are not implemented.
- Persistent database storage is not implemented; lightweight JSONL logs are used instead.

## Demo Narrative For Intro AI
- Start with routing: show A*, Dijkstra, and GBFS on the same road graph.
- Add rain, traffic, or obstacles: explain dynamic edge weights and why the chosen route can change.
- Use Insider/A* step view: explain `g(n)`, `h(n)`, `f(n)`, open set, closed set, and nodes explored.
- Run dispatch: explain CSP filtering first, then scoring among feasible robots.
- Show XAI timeline: explain why a robot was rejected, pruned, scored, or selected.
- Run Optimize Hubs after enough deliveries: explain K-means clustering on delivery demand points.
- Use efficiency score to compare algorithms or before/after behavior.
