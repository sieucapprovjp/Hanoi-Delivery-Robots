# Feature Engine Main AI Port Plan

Branch: `codex/feature-engine-add-main-ai`
Base: `feature/change-simulation-engine`
Target: keep the new simulation engine as the base, then port the missing AI logistics features from `main`.

## Goal

The feature branch already owns the new SimPy simulation engine, assignment policies, event bus, scenario hooks, and runtime robot lifecycle. The merge direction should therefore preserve that engine and bring back the higher-level product features from `main` in small phases.

## Phase Plan

### Phase 1: Audit and Mapping

Status: completed

Map feature-branch engine concepts to the `main` branch feature concepts before changing behavior. This prevents API and data-shape drift when porting VRP, XAI, logging, and FE panels.

Deliverables:

- Compare order/delivery payloads.
- Compare robot state payloads.
- Compare dispatch ownership boundaries.
- Identify direct ports, adapters, and deferred work.

### Phase 2: Persistent Logs and K-means Data Source

Status: completed

Port the JSONL log utilities from `main` and make hub optimization read historical delivery points from file logs first, then fall back to in-memory delivery history.

Deliverables:

- Add persistent JSONL log utility.
- Add `/api/log_delivery`.
- Make completed simulation deliveries eligible for persistent delivery history logging.
- Make K-means load delivery points from log when enough points exist.
- Preserve in-memory fallback for tests and short sessions.
- Keep optimized hubs compatible with the simulation engine by including charging spots.

### Phase 3: CSP / XAI Dispatch Adapter

Status: completed

Do not replace the feature branch assignment engine. Add a CSP/XAI adapter around the existing assignment pipeline so explanations can be emitted without regressing SimPy scheduling.

Deliverables:

- Feasibility filters: robot idle/status, battery, active capacity, pickup reachability.
- Score breakdown compatible with current `AssignmentInput`.
- Explanation payload for assignment decisions.
- Tests for acceptance/rejection reasons.

### Phase 4: VRP / PDP Batch Assignment

Status: completed

Port the max-3-order lightweight VRP behavior as a bounded batch planner on top of the simulation task queue.

Deliverables:

- Capacity: max 3 active orders per robot.
- Pickup/dropoff precedence.
- Simulated annealing or bounded local-search route improvement.
- Tests for capacity, precedence, and route ordering.

### Phase 5: FE State Panels

Status: completed

Adapt FE panels to the feature branch state stream instead of copying old `main` FE modules directly.

Deliverables:

- Show robot active order capacity and carried/queued orders.
- Show assignment/XAI decision details.
- Show persistent log status if useful.

### Phase 6: API Compatibility

Status: completed

Expose compatibility endpoints only where the FE or docs still need them.

Deliverables:

- Keep current simulation APIs stable.
- Add compatibility wrappers for missing `main` endpoints only when necessary.
- Update API docs after implementation.

### Phase 7: Documentation Update

Status: completed

Refresh README and docs after implementation stabilizes.

Deliverables:

- Architecture notes for feature-engine-based AI logistics.
- Logging and K-means data-source notes.
- Dispatch algorithm notes.

### Phase 8: Final Regression Pass

Status: completed

Run focused tests after each phase and a wider regression pass before merging.

Deliverables:

- Focused unit tests for each ported subsystem.
- API smoke checks where practical.
- Manual FE verification for state panels.

## Phase 8 Implementation Result

Date: 2026-06-14

- Full regression passed with the system Python environment: `114 tests OK`.
- Focused `.venv` regression subset passed for API compatibility, VRP, CSP/XAI, persistent logs, hubs, route analysis, validation, metrics, interceptors, neighbor ordering, stats, and stratification.
- `.venv` full discovery still requires dependency cleanup because `flask_socketio` and `simpy` are not installed there; system Python has both and is the verified runtime for this pass.
- Syntax checks passed for the touched Python modules and core frontend modules.
- API smoke checks passed for `/api/health`, `/api/snap`, `/api/data/robots`, and `/api/dispatch/explanations`.
- Browser smoke check passed on `http://127.0.0.1:5002/`: map and Leaflet rendered, main panels were present, and console error count was zero.

## Phase 1 Audit Result

Date: 2026-06-14

| Area | Feature branch shape | Main branch capability | Decision |
| --- | --- | --- | --- |
| Simulation runtime | SimPy `SimulatorManager`, `OrderManager`, `RobotAgent` own order lifecycle and robot movement. | Mostly FE-driven robots and delivery queues. | Keep feature runtime as source of truth. Port main features as adapters. |
| Order model | `id`, `pickup`, `dropoff`, `status`, `created_time`, `robot_name`, `reassign_count`, `last_reassign_time`. | `deliveryId`, `pickup*`, `dropoff*`, `createdAt`, category metadata. | Add compatibility logging payloads without changing runtime order shape. |
| Robot model | Backend agent emits `id`, `name`, `lat`, `lon`, `status`, `battery`, path/geometry data. | FE robot object tracked `deliveryQueue`, `routeSequence`, `currentLoad`, `capacity`, `currentVrp`. | Defer capacity/multi-order fields to VRP phase. |
| Dispatch | Existing policies: `nearest_idle`, `nearest_feasible`, `weighted_cost`, `hungarian`. | CSP/XAI and VRP/PDP assignment modules. | Wrap existing assignment first; do not overwrite current policies. |
| Replanning | Feature branch has projected-gap replanning and anti-chatter reassignment. | Main had route memory and explanation panels. | Preserve feature branch replanning; add XAI explanations later. |
| Hub optimization | K-means only reads `app_state["delivery_history"]`. | K-means can read JSONL delivery logs before RAM fallback. | Port persistent log and log-first K-means in Phase 2. |
| Charging hubs | Simulator expects each hub to include `spots`. | Main optimized hubs were normalized at route layer. | Normalize optimized hubs with default spots before storing in app state. |

## Phase 2 Success Criteria

- `tests.test_persistent_log` passes.
- `tests.test_hubs` passes.
- `/api/log_delivery` records both RAM and JSONL delivery history.
- `compute_optimized_hubs` uses JSONL delivery history when enough points exist.
- Optimized charging hubs keep a `spots` field so simulation restart is not broken.

## Phase 2 Implementation Result

Date: 2026-06-14

- Added `delivery_robots/utils/persistent_log.py` for JSONL append/read helpers.
- Added persistent log config constants in `delivery_robots/config.py`.
- Updated `delivery_robots/core/hubs.py` so K-means reads delivery history from JSONL first, then falls back to RAM.
- Added `/api/log_delivery` in `delivery_robots/routes/main_routes.py`.
- Updated completed simulation deliveries to record pickup and dropoff points in RAM and, when enabled, JSONL.
- Normalized optimized hubs with a default `spots` value before storing them in app state.
- Made package-level app exports lazy in `delivery_robots/__init__.py` so utility tests do not import the Flask app unnecessarily.

Verification:

- Passed: `python -m unittest tests.test_persistent_log tests.test_hubs`
- Passed import-focused subset: `tests.test_route_analysis`, `tests.test_validation`
- `tests.test_dispatch` could not fully run in the current virtualenv because `simpy` is not installed.

## Phase 3 Implementation Result

Date: 2026-06-14

- Added `delivery_robots/algorithms/dispatch/csp_xai.py` as a CSP/XAI adapter around the existing assignment policies.
- Added CSP constraints for idle status, minimum battery sanity, capacity, pickup distance, route reachability, and route battery feasibility.
- Kept low-battery robots feasible when a charging hub exists, so the feature branch three-leg charging workflow is not blocked by CSP.
- Updated `SimulatorManager` to call the CSP/XAI adapter and record dispatch explanations.
- Added `/api/dispatch/explanations` for FE consumption.
- Added dispatch explanation history storage in app state.
- Added `tests/test_csp_xai.py`.

Verification:

- Passed: `python -m unittest tests.test_csp_xai`
- Passed regression subset: `tests.test_csp_xai`, `tests.test_persistent_log`, `tests.test_hubs`, `tests.test_route_analysis`, `tests.test_validation`

## Phase 4 Implementation Result

Date: 2026-06-14

- Added `delivery_robots/algorithms/dispatch/vrp_solver.py` with pickup-delivery precedence, greedy seed, simulated annealing operators, and finite-sequence repair.
- Added VRP config constants and set `VRP_MAX_ORDERS_PER_ROBOT = 3`.
- Updated CSP/XAI dispatch adapter to batch multiple feasible pending orders for the selected robot up to remaining capacity.
- Added `vrp_batch_orders`, `vrp_sequence`, `vrp_stats`, and cost metadata to the selected compound task.
- Updated `RobotAgent` with `capacity = 3`, active order state, and VRP batch execution over pickup/dropoff stops.
- Updated `SimulatorManager` to prepare path/geometry segments for each VRP stop before assigning the compound task.
- Added `tests/test_vrp.py` and extended `tests/test_csp_xai.py` for batching.

Verification:

- Passed: `python -m unittest tests.test_vrp tests.test_csp_xai`
- Passed regression subset: `tests.test_vrp`, `tests.test_csp_xai`, `tests.test_persistent_log`, `tests.test_hubs`, `tests.test_route_analysis`, `tests.test_validation`
- Passed `py_compile` for VRP, CSP/XAI, robot agent, and simulator runtime files.

Known follow-up:

- FE can read `capacity`, `current_load`, and `active_orders` from robot state, but detailed route-sequence visualization still needs a frontend pass.

## Phase 5 Implementation Result

Date: 2026-06-14

- Added FE config for robot capacity and dispatch explanations endpoint.
- Added `BackendAPI.getDispatchExplanations()`.
- Updated robot state handling to store `capacity`, `current_load`, and `active_orders`.
- Updated robot fleet cards to show active order capacity and onboard/queued orders.
- Updated robot popup to show order load and active order list.
- Added Dispatch panel Decision/XAI section.
- Added websocket handling for `dispatch_explanations_update` with API fallback from `/api/dispatch/explanations`.
- Added XAI candidate display with selected/rejected/neutral states.
- Added VRP batch display with order count, sequence, cost before/after, and improvement ratio.
- Added CSS for robot order pills, popup orders, XAI cards, candidates, and VRP sequence.

Verification:

- Passed: `node --check delivery_robots/static/js/viewer/DisplayEngine.js`
- Passed: `node --check delivery_robots/static/js/viewer/DeliveryRobot.js`
- Passed: `node --check delivery_robots/static/js/api.js`
- Passed: `node --check delivery_robots/static/js/config.js`

Known follow-up:

- Browser visual QA should be done when the Flask server is started again.

## Phase 6 Implementation Result

Date: 2026-06-14

- Added `GET /api/snap` compatibility endpoint.
- Added `POST /api/dispatch/assign` compatibility endpoint.
- Kept the compatibility dispatch wrapper stateless and backed by the feature branch `AssignmentInput` plus `run_assignment_with_csp_xai`.
- Normalized legacy `destination` payloads to feature-engine `dropoff` orders.
- Normalized legacy robot dictionaries to lightweight robot objects compatible with the current assignment policies.
- Returned legacy-friendly assignment fields: `robotId`, `robotName`, `deliveryId`, `deliveryIds`, `route`, `breakdown`, `orderSequence`, and VRP stats when batching applies.
- Added `tests/test_api_compat.py` without importing the full Flask app, so compatibility can be tested even when optional runtime dependencies are missing.

Verification:

- Passed: `python -m unittest tests.test_api_compat tests.test_vrp tests.test_csp_xai`
- Passed regression subset: `tests.test_api_compat`, `tests.test_vrp`, `tests.test_csp_xai`, `tests.test_persistent_log`, `tests.test_hubs`, `tests.test_route_analysis`, `tests.test_validation`
- Passed JS syntax checks for the touched FE runtime files.

## Phase 7 Implementation Result

Date: 2026-06-14

- Updated `README.md` to reflect completed CSP/XAI, VRP/PDP, persistent logging, K-means log source, and FE dispatch panels.
- Corrected the documented default server port to `5000`.
- Added `docs/api_reference.md` with current simulation, routing, dispatch, logging, hub optimization, and websocket APIs.
- Added `docs/architecture_notes.md` covering runtime ownership, dispatch pipeline, CSP/XAI, VRP/PDP, persistent logs, frontend state, and compatibility endpoints.

Verification:

- Documentation files were checked for changed references and project status alignment.
