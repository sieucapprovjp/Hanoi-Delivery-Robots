# Product Requirements Document

This PRD records the current product goals and implemented scope for the AI Delivery
Robots simulation.

## Overview

The app simulates a fleet of delivery robots operating around Hoan Kiem, Hanoi. It is
an academic AI demo focused on explainable routing and dispatch decisions under
dynamic city conditions.

Core AI topics:

- A*, Dijkstra, GBFS, and BFS comparison
- dynamic graph edge weights from rain, traffic, obstacles, and road memory
- CSP-based dispatch filtering
- XAI decision explanations
- VRP/PDP multi-order sequencing with Simulated Annealing
- K-means hub optimization

## User Stories

1. As an AI student, I want to compare A*, Dijkstra, GBFS, and BFS on the same road graph so I can explain their tradeoffs.
2. As a demo operator, I want to add rain, congestion, and obstacles so I can show why the chosen route changes.
3. As a logistics planner, I want robots to batch a small number of orders so I can demonstrate VRP/PDP without making the simulation too heavy.
4. As a reviewer, I want explanations for dispatch and route decisions so I can understand why a robot was selected or rejected.
5. As a logistics planner, I want delivery history to feed K-means hub optimization.

## Functional Requirements

### Routing

- Use a real OSMnx/NetworkX bike graph centered around Hoan Kiem.
- Support production A*, Dijkstra, and GBFS.
- Accept `greedy` as a GBFS alias.
- Compute edge weights dynamically instead of mutating graph geometry.
- Return geometry, route cost, nodes explored, timing, and cost breakdown.

### Dynamic Environment

- Support rush-hour traffic.
- Support user-created and randomized traffic routes.
- Support user-created and randomized rain zones.
- Support user-created and randomized obstacles.
- Include these penalties in route search, dispatch routing, and VRP distance matrices.

### Dispatch, CSP, and XAI

- Filter infeasible robots by status, battery, capacity, and pickup distance.
- Score feasible robots by route cost, battery risk, and delivery priority.
- Return route payloads with assignments so the frontend does not need a second route request.
- Return structured explanations for rejected, pruned, scored, and selected candidates.

### VRP/PDP

- Allow one robot to carry up to `3` active orders.
- Batch orders when pending queue pressure exceeds available idle robots.
- Enforce pickup-before-dropoff precedence.
- Use Simulated Annealing to improve multi-stop order sequence.
- Surface VRP metrics in the XAI/UI panel.

### K-means Hubs

- Persist completed pickup/dropoff coordinates to lightweight logs.
- Run K-means over delivery history.
- Return optimized hub coordinates and allow the frontend to reposition charging hubs.

### Logging

- Keep recent logs in memory for the UI.
- Append app events to `logs/app-events.jsonl`.
- Append delivery history to `logs/delivery-history.jsonl`.
- Avoid database setup for the current project scope.

## Edge Cases

- Invalid coordinates return `400`.
- Insufficient K-means history returns `400`.
- Unreachable route candidates are skipped or rejected with explanations.
- VRP handles unreachable matrix entries with fallback behavior instead of crashing the whole dispatch request.
- Robots that enter rain/traffic can reroute, but route memory and environment penalties should prevent repeated oscillation around bad segments.

## Current Non-Goals

- Persistent SQL database.
- Advanced K-means controls such as Auto-K/Elbow.
- Heavy production-grade fleet optimization beyond the small demo capacity.
