# Coding Convention & Standards

This document defines the coding standards, naming conventions, formatting rules, and architectural patterns for the AI Delivery Robots simulation project.

---

## 🐍 Backend (Python)

### Style Guide & Formatting
*   **PEP 8 Compatibility**: Code must strictly conform to PEP 8 standards.
*   **Line Length**: A maximum line length of 88 or 100 characters is preferred (aligned with modern toolings like Black).
*   **Code Formatter**: Python code should be formatted using **Black** or **Ruff**.
*   **Imports**: Imports should be grouped in the following order, with blank lines separating groups:
    1.  Standard library imports (e.g., `import math`, `import time`).
    2.  Third-party library imports (e.g., `import networkx as nx`, `from flask import Flask`).
    3.  Local application/parent package imports (e.g., `from ..config import SIMULATION_SPEED`, `from .base import reconstruct_node_path`).

### Naming Conventions
*   **Modules / Packages**: Lowercase with underscores (snake_case) (e.g., `delivery_robots`, `routes`, `algorithms`).
*   **Classes**: PascalCase (e.g., `RobotAgent`, `SimulatorManager`, `Profiler`).
*   **Functions & Methods**: snake_case (e.g., `astar_search`, `edge_weight_with_traffic`, `nearest_node_id`).
*   **Variables & Constants**:
    *   Local/Instance variables: snake_case (e.g., `start_node`, `tentative_g`).
    *   Module-level global variables: Prefixed with an underscore to denote internal use (e.g., `_road_graph`, `_app_state`).
    *   Configuration constants: UPPER_SNAKE_CASE (e.g., `SIMULATION_SPEED`, `DEFAULT_RAIN_SEVERITY`).

---

## 🌐 Frontend (JavaScript, HTML, CSS)

### JavaScript Style & Formatting
*   **Standard**: ECMAScript 6 (ES6+) syntax.
*   **Formatter**: Formatted with Prettier or equivalent style rules.
*   **Classes & Methods**: Classes in PascalCase (e.g., `DisplayEngine`, `RainManager`, `BackendAPI`). Methods and properties in camelCase (e.g., `initialize`, `getTraffic`, `logEvent`).
*   **Globals & Constants**: Centralized config object named `CONFIG` in `delivery_robots/static/js/core/config.js` in UPPER_SNAKE_CASE keys (e.g., `CONFIG.API.LOGS`).

### HTML & Alpine.js
*   Use semantic HTML5 elements where possible (e.g., `<header>`, `<nav>`, `<button>`).
*   Use Alpine.js for lightweight state binding (e.g., `x-data`, `x-show`, `x-text`). Alpine.js stores should define logic cleanly and avoid spaghetti JavaScript inside HTML tags.

### CSS Styling
*   Follow clean CSS structures. Use descriptive selectors.
*   Centralize typography and base layout styling in `static/css/style.css`.
*   Avoid inline styles; delegate dynamic positions or configurations to CSS classes or clean variables.

---

## 🏛️ Architectural Patterns

### State Management & Threading
*   **In-Memory State**: The simulation maintains an in-memory state dictionary (`_app_state` in `delivery_robots/app.py`).
*   **Thread Safety**: Flask routes run concurrently. Thread locks must be explicitly acquired and released when accessing shared in-memory collections:
    *   `_graph_lock` for graph initialization and updates.
    *   `_history_lock` for modifying `DELIVERY_HISTORY`.
    *   `_dynamic_traffic_lock` for adding or clearing dynamic traffic routes.
    *   `_obstacles_lock` for managing road obstacles.
    *   `_api_logs_lock` for adding frontend logs to the deque.
*   **Simulation Loop**: The active demo simulation loop runs in the browser. The frontend calls Flask REST APIs for route calculation, dispatch, environment state, logs, metrics, and hub optimization.
*   **Dispatch Scope**: Keep CSP constraints, XAI explanation construction, and VRP/PDP sequencing in backend modules under `delivery_robots/algorithms/dispatch/`.

### Weighting Function Patterns
*   Environment metrics (Rain, Traffic, Obstacles) must not directly mutate the underlying graph edge lengths. Instead, they must be computed as dynamic weights via the `edge_weight_with_traffic(state, from_node, to_node, edge_data)` function.
*   Graph modifications should keep topological geometry intact while updating weights dynamically.
*   Multi-order routing must preserve pickup-before-dropoff precedence and respect the configured robot capacity.
