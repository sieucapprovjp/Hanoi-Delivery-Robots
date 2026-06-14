# Architecture Notes

## Runtime Ownership

The feature-engine branch keeps the backend simulation engine as the source of truth.

- `SimulatorManager` owns the SimPy environment, dispatcher loop, robot initialization, route preparation, and websocket emission.
- `OrderManager` owns order lifecycle transitions: pending, assigned, in transit, delivered, expired.
- `RobotAgent` owns robot movement, charging, battery safety checks, single-order execution, and VRP batch execution.
- Frontend components render state streamed from the backend instead of calculating dispatch or movement locally.

## Dispatch Pipeline

Dispatch is layered to preserve the existing assignment policies while adding AI logistics features.

1. `SimulatorManager` builds an `AssignmentInput` from idle robots and pending orders.
2. `run_assignment_with_csp_xai` evaluates CSP constraints and builds explanation payloads.
3. Eligible candidates are passed to the selected assignment policy:
   - `nearest_idle`
   - `nearest_feasible`
   - `weighted_cost`
   - `hungarian`
4. If batching is possible, the selected robot receives up to `VRP_MAX_ORDERS_PER_ROBOT` orders.
5. `vrp_solver.solve_vrp_sa` builds a pickup/dropoff sequence with precedence preserved.
6. `SimulatorManager.prepare_vrp_batch_task` calculates route segments and geometry for each stop.
7. `RobotAgent.execute_vrp_batch` moves through the sequence and updates each order lifecycle.

## CSP / XAI

CSP checks are implemented in `delivery_robots/algorithms/dispatch/csp_xai.py`.

Current checks:

- Robot is idle.
- Battery value is above minimum sanity threshold.
- Robot has remaining capacity.
- Pickup is within configured maximum distance.
- Robot can route to pickup and pickup can route to dropoff.
- Route battery feasibility passes, or a charging hub exists for three-leg handling.

Explanations are emitted over `dispatch_explanations_update` and are also available from `GET /api/dispatch/explanations`.

## VRP / PDP

VRP logic lives in `delivery_robots/algorithms/dispatch/vrp_solver.py`.

- Robot capacity is capped at 3 active orders.
- Each order contributes a pickup stop and a dropoff stop.
- `check_precedence` enforces pickup-before-dropoff.
- The solver uses a greedy initial solution and simulated annealing operators: swap, relocate, and two-opt.
- For small batches, the solver may skip simulated annealing and keep the greedy sequence.

## Persistent Logs And K-means

Delivery history is written through `delivery_robots/utils/persistent_log.py`.

- Runtime deliveries append pickup and dropoff points to in-memory history.
- When persistent logging is enabled, completed deliveries are also written to `logs/delivery-history.jsonl`.
- `compute_optimized_hubs` loads JSONL history first. If the log has too few points, it falls back to in-memory history.
- Optimized hubs are normalized with a `spots` value before becoming charging stations, so SimPy charging resources can be recreated safely.

## Frontend State

The frontend remains a renderer of backend state.

- Robot cards and popups read `capacity`, `current_load`, and `active_orders`.
- Dispatch panel reads explanations from websocket and falls back to `/api/dispatch/explanations`.
- VRP batch details show order count, stop sequence, cost before/after, and improvement ratio.

## Compatibility Layer

The branch exposes a small compatibility surface for code and docs that still use older APIs.

- `GET /api/snap`
- `POST /api/dispatch/assign`

The compatibility dispatch endpoint normalizes old payload names such as `destination` into the feature-engine `dropoff` shape, then uses the same CSP/XAI adapter as the live simulation.
