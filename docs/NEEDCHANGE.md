# Frontend functions to Rework/Remove for Backend-Driven Simulation

This document lists JavaScript functions in `delivery_robots/static/js/` that must be removed or significantly reworked when migrating from a **Frontend-Time-Stepped** model to a **Backend-Driven** model.

## 1. Simulation Engine (Loop & Flow Control)
*Core logic responsible for stepping time and triggering updates.*

| Function | File | Action | Description |
| :--- | :--- | :--- | :--- |
| `update()` | `simulation.js` | **REMOVE** | Main simulation tick loop. Moves to backend thread/task. |
| `start()` | `simulation.js` | **REWORK** | Replace `requestAnimationFrame` with an API call to start backend sim. |
| `pause()` | `simulation.js` | **REWORK** | Replace local flag change with an API call to pause backend sim. |
| `reset()` | `simulation.js` | **REWORK** | Should call a backend reset endpoint to clear state in Python/Redis. |
| `updateStats()` | `simulation.js` | **REWORK** | Consume stats from backend payload instead of calculating locally. |

## 2. Delivery & Dispatch Management
*Logic for creating orders and assigning them to robots.*

| Function | File | Action | Description |
| :--- | :--- | :--- | :--- |
| `generateDelivery()` | `simulation.js` | **REMOVE** | Order generation based on weights must happen on the backend. |
| `assignDeliveries()` | `simulation.js` | **REMOVE** | Dispatcher logic (scanning idle robots) moves to backend. |
| `logDeliveryData()` | `simulation.js` | **REMOVE** | Backend will log its own generated data directly. |
| `assignDelivery()` | `robot.js` | **REMOVE** | Local assignment state management moves to backend. |

## 3. Robot Movement & State Logic
*Physics, battery, and behavioral transitions.*

| Function | File | Action | Description |
| :--- | :--- | :--- | :--- |
| `update()` | `robot.js` | **REWORK** | Remove movement/battery logic. Keep only for smooth marker interpolation. |
| `arriveAtWaypoint()` | `robot.js` | **REMOVE** | Phase transitions (Pickup -> Dropoff) are now backend business logic. |
| `goCharge()` | `robot.js` | **REMOVE** | Charging decision logic moves to backend. |
| `startCharging()` | `robot.js` | **REMOVE** | Battery increment logic over time moves to backend. |
| `finishCharging()` | `robot.js` | **REMOVE** | State transition after charge moves to backend. |
| `maybeReroute()` | `robot.js` | **REMOVE** | Environmental reaction logic moves to backend. |
| `estimateBatteryRisk()` | `robot.js` | **REMOVE** | Prediction logic moves to backend. |

## 4. Map & Environment Intelligence
*Spatial reasoning and environmental impact calculations.*

| Function | File | Action | Description |
| :--- | :--- | :--- | :--- |
| `buildRoadGraph()` | `map.js` | **REMOVE** | Graph construction must happen in Python for backend pathfinding. |
| `findShortestPath()` | `map.js` | **REMOVE** | Dijkstra/A* logic on the road graph moves to backend. |
| `getRoute()` | `map.js` | **REMOVE** | Coordinate-based routing moves to backend. |
| `getTrafficAt()` | `map.js` | **REMOVE** | Traffic heatmap lookup moves to backend. |
| `getRainPenaltyAt()` | `map.js` | **REMOVE** | Weather impact calculation moves to backend. |
| `snapToRoad()` | `map.js` | **REMOVE** | Geometry snapping moves to backend. |
| `getNearestGraphNode()`| `map.js` | **REMOVE** | Spatial indexing lookups move to backend. |

## 5. Pathfinding Infrastructure
*Communication wrappers for routing services.*

| Function | File | Action | Description |
| :--- | :--- | :--- | :--- |
| `getRoute()` | `pathfinding.js` | **REMOVE** | Backend will call internal modules; no need for JS to fetch via API. |
| `snapToRoad()` | `pathfinding.js` | **REMOVE** | Redundant when snapping happens server-side during tick. |
| `estimateRouteCost()`| `pathfinding.js` | **REMOVE** | Cost breakdown calculation moves to backend. |
| `buildRouteToTarget()`| `robot.js` | **REMOVE** | Logic to trigger and store new paths moves to backend. |

## 6. Learning System (Q-Learning Lite)
*Experience tracking and road memory.*

| Function | File | Action | Description |
| :--- | :--- | :--- | :--- |
| `recordRoadExperience()`| `robot.js` | **REMOVE** | Learning data should be stored in a backend database/cache. |
| `decayMemory()` | `robot.js` | **REMOVE** | Memory maintenance logic moves to backend. |

---
**Note:** Functions related to **Leaflet rendering** (e.g., `drawPathLine`, `createMarker`, `renderTraffic`, `showDeliveryMarkers`) should be **RETAINED** but updated to receive data from the backend simulation state.
