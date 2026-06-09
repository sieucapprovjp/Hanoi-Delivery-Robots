# AI Development Instructions

This document provides system directives, constraints, and instructions for AI agents modifying, debugging, or writing code for the **AI Delivery Robots Simulation** codebase.

---

## 🚫 Critical Constraints & Coding Rules

### 1. Centralization of Constants
*   **No Magic Numbers**: All magic numbers, penalty weights, coordinate boundaries, radii, time periods, log lengths, or default strings must be defined in [config.py](file:///home/lan/projects/AI-Intro/delivery_robots/config.py) (backend) or [config.js](file:///home/lan/projects/AI-Intro/delivery_robots/static/js/config.js) (frontend).
*   Do not define inline literals in the algorithms, simulation loop, or API routers.

### 2. Thread Safety & Mutability
*   Flask routes run on concurrent threads. The simulation state (like graph data, history list, log queue) is stored in-memory.
*   **Lock Enforcement**: Any update or iteration of shared memory state must be protected using the corresponding lock. For example:
    ```python
    with state["obstacles_lock"]:
        state["obstacles"].append(new_obstacle)
    ```

### 3. Pathing & Geometry Rules
*   Never mutate the underlying graph geometry (`length`, coordinates) to simulate environment hazards. Mutate only the *weights* computed during search.
*   When writing new pathfinding search algorithms, ensure they return the tuple `(path_nodes_list, nodes_explored_count)` and raise `networkx.NetworkXNoPath` if no path connects the target nodes.

### 4. Package Import Paths
*   Ensure relative imports are structured correctly.
*   The `delivery_robots/core/simulation/` module is nested three directories deep from the root package. Importing the main utility package must use three dots (`from ...utils import ...`) rather than two dots (`from ..utils import ...`), which throws runtime errors.

---

## 🧪 Testing Guidelines

*   **Test Isolation**: Tests must never trigger live HTTP calls or download files from OpenStreetMap.
*   **Graph Mocking**: Mock out OSMnx network fetches using a simple, small in-memory `MultiDiGraph`.
*   **Node Coordinates**: Mocked nodes must define `y` (latitude) and `x` (longitude) keys, and edges must define the `length` property to prevent calculations from throwing KeyErrors.
*   **OSMnx Mocks**: When mocking `ox`, be aware that mock setups might trigger CRS lookups. Mock `ox.nearest_nodes` or avoid calls to it by providing custom node-matching callbacks in testing setups.

---

## 🏎️ Performance & Latency Constraints

*   Avoid invoking `ox.nearest_nodes` in the simulation loop. It is an expensive operation that builds GeoDataFrames.
*   Instead, utilize the spatial tree search (`state.get("spatial_tree")`) built on the projected coordinate maps. It delivers $O(\log N)$ nearest-neighbor queries, minimizing path calculation bottlenecks.
