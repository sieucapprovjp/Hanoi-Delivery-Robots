# Product Requirements Document (PRD)

This Product Requirements Document details the business logic, user stories, functional requirements, and edge cases for the **AI Delivery Robots Simulation** application.

---

## 🎯 Project Overview

The **AI Delivery Robots Simulation** is an academic and interactive simulator designed to model a fleet of autonomous delivery robots operating in Hanoi's Hoan Kiem district. The platform serves as a benchmark and educational tool to compare classic pathfinding algorithms (Dijkstra, GBFS, A*) under dynamically changing environmental constraints, while applying unsupervised learning (K-Means) to optimize logistics hubs.

---

## 👥 User Stories

1.  **Algorithmic Comparison**: *As an AI student, I want to run Dijkstra, GBFS, and A\* searches on the same street network under identical constraints so that I can analyze performance metrics (calculation time, nodes explored, path cost).*
2.  **Dynamic Incident Injection**: *As a simulator researcher, I want to place rainstorms, traffic blockages, or construction zones onto the map in real-time to observe how routing weights adapt and how robot transit times are affected.*
3.  **Hub Relocation & Optimization**: *As a logistics planner, I want the system to analyze historical delivery coordinates and automatically reposition charging hubs to minimize future travel distances.*
4.  **Simulation Controls**: *As an evaluator, I want to speed up, slow down, pause, or reset the simulation so that I can inspect specific multi-agent interactions and queue states.*

---

## ⚙️ Functional Requirements

### 1. Classical Search Routing Engine
*   The system must calculate routes on a real Hoan Kiem street graph downloaded via OSMnx.
*   Implemented search algorithms:
    *   **Dijkstra**: Evaluates cumulative edge lengths without look-ahead heuristics.
    *   **Greedy Best-First Search (GBFS)**: Guides search using the Haversine distance to the goal.
    *   **A\***: Balances cumulative edge cost and Haversine distance heuristic.
*   **Dynamic Weighting**: Routing calculations must incorporate environment penalty multipliers (Rain, Congestion, Roadblocks) instead of relying on static geographical distance.

### 2. Dynamic Environment Engine
*   **Traffic Congestion**:
    *   **Rush Hour Cycles**: Simulated time triggers rush periods (Morning: 7-9 AM, Lunch: 11 AM-1 PM, Evening: 5-7 PM) applying wave multipliers (up to 3.0x) to traffic weights.
    *   **Congestion Routes**: Users can select two points on the map to introduce heavy traffic, applying severity coefficients (0.0 to 1.0).
*   **Rain Zones**: Users can place rainfall circles. Any graph edge midpoint within the radius suffers a travel cost multiplier.
*   **Obstacles**: Users can mark roadblock coordinates, construction hazards, or accidents, applying localized penalties based on proximity to the obstacle center.

### 3. SimPy Discrete-Event Simulation Loop
*   A background loop handles simulated clock ticks synced via websockets.
*   **Naive Dispatching**:
    *   Generates delivery orders periodically (every 1 to 3 simulated minutes) between random coordinates.
    *   Identifies idle robots and dispatches orders sequentially.
    *   Calculates a route to the pickup point, waits for a loading delay (30 seconds), then routes to the drop-off location.
*   **Battery Drain**: Robots deplete their battery charge (e.g., 1% per 60 simulated seconds of transit).

### 4. Unsupervised K-Means Hub Optimization
*   The system stores successful drop-off coordinates in a history queue.
*   Clicking "Optimize Hubs" takes coordinate histories and groups them using K-Means clustering (default $K=5$).
*   Charging depots are repositioned to the calculated cluster centroids to optimize fleet logistics.

---

## 🚨 Edge Cases & Exception Handling

*   **Graph Disconnection / Path Blockages**:
    *   *Scenario*: Roadblocks or configuration choices leave a robot with no traversable path to its target node.
    *   *Action*: The search throws a `NetworkXNoPath` exception. The Simulator catches the exception, logs it, and pushes the order back to the front of the queue to retry.
*   **Insufficient Data for K-Means Clustering**:
    *   *Scenario*: User clicks `Optimize Hubs` before enough orders have been completed.
    *   *Action*: The server validates history size (requires $\ge 5$ coordinates) and returns an HTTP 400 error showing a helpful user message.
*   **Out-of-Bound Inputs**:
    *   *Scenario*: User adds rain or roadblocks with invalid latitudes, longitudes, or negative radii.
    *   *Action*: Backend validation layer intercepts requests, returns HTTP 400 with a detailed validation message, and prevents memory corruption.
