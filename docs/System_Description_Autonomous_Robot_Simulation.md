# Autonomous Delivery Robot Simulation: System Specifications

## 1. Executive Summary
This document outlines the architecture and technical specifications for a discrete-event simulation of a fleet of autonomous delivery robots operating in the urban environment of Hoan Kiem District, Hanoi. The system integrates real-world mapping data, dynamic search and routing algorithms, and environmental constraints to model urban logistics under various real-world conditions (e.g., rain, traffic, roadblocks). 

## 2. Technical Stack
| Layer | Technology |
| :--- | :--- |
| **Backend Framework** | Flask (Python 3.10+) |
| **Simulation Engine** | SimPy (Discrete Event Simulation) |
| **Mapping & AI Routing** | OSMnx, NetworkX |
| **Communication** | Flask-SocketIO (WebSockets) |
| **Frontend UI Client** | Alpine.js, Vanilla JavaScript |
| **Map Rendering** | Leaflet.js |

## 3. Operational Parameters

### 3.1 Robot Specifications
* **Fleet Size:** Configurable active fleet of robots.
* **Base Speed:** Estimated at 180 meters per minute (approx. 10.8 km/h), as defined in configuration.
* **Maximum Range:** Estimated based on battery constraints (e.g., 100 km on full charge).
* **Charging Duration:** Modeled to take approximately 4 hours for a full cycle.
* **Safety Threshold:** 20% minimum battery reserve before forcing a re-route to the nearest hub/station.

### 3.2 Environment & Logistics
* **Simulation Area:** Centered around Hoan Kiem District, Hanoi (`21.0285, 105.8542`), covering a radius of approximately 2200 meters.
* **Dynamic Penalties (Environment):**
    * **Rain Zones:** Regions where movement speed is penalized based on Haversine distance from the center of the rain zone.
    * **Traffic Routes:** Segments of roads experiencing congestion, applying severity multipliers based on proximity and duration.
    * **Obstacles:** Local roadblocks and construction sites adding localized penalties to passing vehicles.
* **Order Model:** Customer-to-customer delivery. Pickup and delivery points are dynamic addresses on the graph, not fixed warehouses.

### 3.3 Time & Synchronization
* **Time Scale:** Time is mapped via speed multipliers (e.g., a default speed of 60x makes 1 second of real-time equal to 1 minute of simulation time).
* **Update Strategy:** Event-driven synchronization. Data is pushed to the client via WebSockets to keep the visualization layer updated upon state or milestone changes.
* **Movement Rendering:** The frontend acts as a visual rendering engine, performing interpolation between coordinates to ensure smooth, visually accurate robot movement.

## 4. Core Logic & Systems

### 4.1 State Machine
Each robot agent follows a strictly defined lifecycle:
1.  **Idle**: Stationary at the last location, awaiting a task.
2.  **Moving_to_Pickup**: Navigating to the customer's origin.
3.  **Moving_to_Dropoff**: Transporting the package to the destination.
4.  **Moving_to_Charge**: Redirecting to the nearest station when battery is low.
5.  **Charging**: Inactive for delivery while replenishing power.

### 4.2 Dispatcher & Battery Constraint Logic
The system uses a "Pre-check" mechanism before task assignment:
* **Route Projection**: Calculates the entire path sequence: `Current Location` → `Pickup` → `Dropoff` → `Nearest Charging Station`.
* **Validation**: The order is only assigned if the robot can complete the delivery and reach a charging station with $\ge 20\%$ battery remaining.
* **Prioritization**: If the validation fails, the robot enters the `Moving_to_Charge` state, and the order remains in the queue for another agent.

### 4.3 Routing & Environmental Event System
* **Search Algorithms**: Supports AI routing algorithms including A*, Dijkstra, and Greedy Best-First Search (GBFS).
* **Dynamic Edge Weighting**:
    * **Penalties**: Calculates total travel cost dynamically by combining base physical length with environmental multipliers (traffic, rain, obstacles).
    * **Local Events**: Intercepts specific nodes or edges, forcing immediate path recalculation for impacted routes.
* **Triggers**: Dynamic events support random generation via the backend or explicit manual placement via the frontend interface.

## 5. System Workflow
1.  **Initialization**: Load the OSMnx graph around Hoan Kiem from local cache or directly; initialize robots at starting nodes or stations.
2.  **Order Generation**: Orders are dispatched into a central queue based on simulation logic.
3.  **Task Allocation**: The Dispatcher matches available idle robots to incoming tasks based on proximity, battery, and AI routing metrics.
4.  **Execution**: The SimPy environment processes the movement events, yielding for calculated travel times.
5.  **Real-time Synchronization**: State changes trigger Flask-SocketIO broadcasts to the frontend.
6.  **Visualization**: The Leaflet.js dashboard receives coordinates and updates marker positions and metrics (battery, status).
