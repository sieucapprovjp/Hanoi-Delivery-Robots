# Simulation Features Checklist (Frontend)

File mark existing feature for backend migration.

## 1. Core Simulation Engine
- [ ] **Main Loop**: `requestAnimationFrame` driven simulation cycle.
- [ ] **State Control**: Start, Pause, Resume, Reset functionality.
- [ ] **Time Management**: `simulationTime` tracking and configurable `speed` multiplier.
- [ ] **Clock System**: Syncing with backend clock, handling "Rush Hour" multipliers and display.
- [ ] **Asset Initialization**: Snapping locations to road network upon setup.

## 2. Robot Management (Multi-Agent)
- [ ] **State Machine**: Logic for `IDLE`, `MOVING`, `CHARGING`.
- [ ] **Movement Logic**: Linear interpolation between road network waypoints.
- [ ] **Battery System**: 
    - [ ] Constant drain per frame.
    - [ ] Rain-induced drain penalty.
    - [ ] Low battery threshold detection.
    - [ ] Autonomous diversion to charging stations.
- [ ] **Road Memory (Q-learning lite)**: 
    - [ ] Recording "experience" (penalties) on road segments.
    - [ ] Temporal decay of learned memory.
- [ ] **Dynamic Speed**: Calculation based on `traffic` and `rain` at current position.

## 3. Environment Simulation
- [ ] **Traffic System**:
    - [ ] Periodic refresh from API.
    - [ ] Severity-based speed penalties.
    - [ ] Visual overlay rendering.
    - [ ] Manual creation via map click (Point A -> Point B).
- [ ] **Weather System**:
    - [ ] Rain zone definitions (center, radius, multiplier).
    - [ ] Impact on robot speed and battery consumption.
    - [ ] Manual/Randomized generation.
- [ ] **Obstacle System**:
    - [ ] Dynamic obstacle placement with severity and type.
- [ ] **Charging Infrastructure**:
    - [ ] Station capacity/spot management (occupy/release).
    - [ ] Nearest available station logic.
- [ ] **Road Network**:
    - [ ] Graph-based street connectivity.
    - [ ] Snap-to-road/Snap-to-street logic.

## 4. Dispatch & Logistics
- [ ] **Delivery Generation**: 
    - [ ] Weighted random pickup/dropoff selection.
    - [ ] Category-based location filtering.
- [ ] **Assignment Logic**: 
    - [ ] Pending delivery queue.
    - [ ] Multi-agent assignment via backend API calls.
- [ ] **Delivery Workflow**: 
    - [ ] Phase tracking (`TO_PICKUP` -> `TO_DROPOFF`).
    - [ ] Arrival detection and state transition.

## 5. Pathfinding & Optimization
- [ ] **Routing Algorithms**: Support for A*, Dijkstra, and GBFS.
- [ ] **Cost Estimation**: Multi-factor cost calculation (distance + traffic + rain + memory).
- [ ] **Dynamic Rerouting**: Triggered by traffic/rain changes while moving.
- [ ] **Hub Optimization**: K-means clustering for optimal robot repositioning.

## 6. Analytics & Metrics
- [ ] **Fleet Stats**: Aggregated distance, deliveries, and battery usage.
- [ ] **Algorithm Comparison**: 
    - [ ] Tracking nodes explored, time taken, path cost per algorithm.
    - [ ] Efficiency score calculation.
    - [ ] Comparative benchmarking (A* vs Dijkstra vs GBFS vs BFS).
- [ ] **Pathfinding Visualization**: 
    - [ ] Real-time A* expansion overlay (explored nodes, open/closed sets).
    - [ ] Step-by-step formula breakdown (f = g + h).
- [ ] **Real-time Insights**: "Dispatch Insights" log for system events.
- [ ] **Centralized Logging**: Sending UI and Dispatch events to backend.

## 7. UI / Visualization (Reference Only)
- [ ] **Map Rendering**: Leaflet tile layers and markers.
- [ ] **Robot Popups**: Real-time attribute display (battery, speed, current target).
- [ ] **Path Polylines**: Visualizing current planned route for each robot.
- [ ] **Interactive Computing Panel**: Detailed A* breakdown and calculation history.
