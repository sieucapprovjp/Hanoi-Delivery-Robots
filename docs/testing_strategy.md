# Testing Strategy

This document outlines the testing methodologies, frameworks, test cases, and mocking patterns for the **AI Delivery Robots Simulation** application.

---

## 🧪 Testing Methodologies

The codebase employs a automated testing suite categorized into:
1.  **Unit Tests**: Verify isolated functions such as calculations inside the routing engine, coordinate validators, and route geometry building.
2.  **Integration Tests**: Verify end-to-end Flask application client flows, validation filters on HTTP routes, and endpoint responses.

---

## 🛠️ Testing Framework & Run Environment

*   **Framework**: Python's standard `unittest` library.
*   **Virtualenv Invocation**: Tests must be executed using the virtual environment's Python interpreter to ensure dependencies (like NetworkX and OSMnx) are correctly loaded.
*   **Command**:
    ```bash
    .venv/bin/python -m unittest discover tests
    ```

---

## 📦 Test Suite Overview

The project maintains three test modules inside the [tests/](file:///home/lan/projects/AI-Intro/tests) folder:

### 1. [test_validation.py](file:///home/lan/projects/AI-Intro/tests/test_validation.py)
Validates input constraints.
*   Asserts coordinate errors when latitude is $> 90$ or $<-90$, or longitude is $> 180$ or $<-180$.
*   Checks that negative counts or non-positive values (like radii) raise correct exceptions.

### 2. [test_route_analysis.py](file:///home/lan/projects/AI-Intro/tests/test_route_analysis.py)
Tests path cost calculations and geometry processing.
*   Uses a mocked `FakeGraph` structure.
*   Verifies that `build_route_response` correctly aggregates environmental penalties into the cost breakdown:
    $$\text{TotalCost} = \text{BaseDistance} + \text{TrafficCost} + \text{RainCost} + \text{ObstacleCost}$$

### 3. [test_api.py](file:///home/lan/projects/AI-Intro/tests/test_api.py)
Tests Flask REST API endpoints using the Flask test client (`app.test_client()`).
*   Verifies `/api/health` returns status `'ok'`.
*   Verifies `/api/traffic/add` successfully maps coordinate points to the closest node and creates congestion paths.
*   Ensures bad coordinate values trigger HTTP 400 validations.

---

## 🪵 Graph Mocking Patterns

To prevent slow and fragile HTTP requests to OpenStreetMap or live downloads during testing, the graph must be mocked.

### 1. Minimal Graph Setup
Mocked graphs must be instances of `networkx.MultiDiGraph` or class doubles containing:
*   Nodes with `y` (latitude) and `x` (longitude) keys:
    ```python
    graph.add_node(1, y=21.0000, x=105.0000)
    ```
*   Edges containing the `"length"` attribute:
    ```python
    graph.add_edge(1, 2, length=100.0)
    ```

### 2. OSMnx Module Mocking
*   In API tests, mock `ox` reference to avoid real-world spatial tree construction or CRS exceptions.
*   Mock out `ox.nearest_nodes` or assign the module attribute `_ox = None` inside `setUp()` to ensure coordinate lookups fall back to fast Haversine loop algorithms in tests.
