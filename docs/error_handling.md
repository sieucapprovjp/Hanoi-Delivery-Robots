# Error Handling & Logging Strategy

This document describes the validation rules, HTTP status codes, exception handling practices, and logging strategy configured for the **AI Delivery Robots Simulation** application.

---

## 🛡️ Input Validation & Business Rules

Inputs to the system (coordinates, radii, counts) are validated in [validation.py](file:///home/lan/projects/AI-Intro/delivery_robots/utils/validation.py). The validation rules are:

| Parameter | Domain Constraint | Exception Thrown |
| :--- | :--- | :--- |
| **Latitude** | Must lie within range `[-90, 90]` | `ValueError` |
| **Longitude** | Must lie within range `[-180, 180]` | `ValueError` |
| **Radius** | Must be a positive float ($> 0.0$) | `ValueError` |
| **Count** | Must be a non-negative integer ($\ge 0$) | `ValueError` |
| **KMeans History**| Must have $\ge 5$ coordinates | `ValueError` |

---

## 📋 Standardized HTTP API Responses

If validation fails or a logical constraint is violated, the backend intercepts the request and responds with a standard error JSON format.

### 400 Bad Request (Validation Errors)
*   **Trigger**: Coordinates out of bounds, or radius is negative.
*   **Payload**:
    ```json
    { "error": "Latitude must be between -90 and 90" }
    ```

### 400 Bad Request (Business Logic Violations)
*   **Trigger**: Optimization invoked with insufficient history.
*   **Payload**:
    ```json
    { "error": "Not enough delivery data to optimize hubs. Need at least 5 points." }
    ```

### 500 Internal Server Error
*   **Trigger**: Uncaught Python runtime exception.
*   **Payload**:
    ```json
    { "error": "Exception message detail string" }
    ```

---

## 🔌 WebSocket Simulation Error Handling

During simulation runs (which happen asynchronously in background threads), errors cannot be returned via normal HTTP cycles:
*   **Search Failures (`NetworkXNoPath`)**: If an obstacle blocks all routes between a robot and its target, the search throws an exception.
*   **Graceful Recovery**: The simulation manager intercepts the exception, emits a `"system_event"` WebSocket message (e.g., `"Routing failed for ORDER-120, retrying later"`), and appends the order back to the queue to avoid dropping tasks.

---

## 🪵 Logging Architecture

### 1. In-Memory Logs Queue
Logs from both the frontend (user actions) and backend (dispatcher events) are collected in a centralized deque (`_api_logs`) inside `app.py`:
*   **Data Structure**: Thread-safe `collections.deque(maxlen=500)`.
*   **Retention**: Logs are kept in-memory and are cleared when the server is restarted.

### 2. Log Schema
Each log entry contains the following properties:
```json
{
  "ts": 1716382092100,
  "message": "New order ORDER-12 generated...",
  "level": "info",
  "source": "dispatch"
}
```

### 3. Log Levels & Sources
*   **Levels**:
    *   `info`: Standard events (e.g., displaying loaded layers, pathfinding completion).
    *   `warning`: Intermediate errors or retries (e.g., routing timeouts, battery alerts).
    *   `error`: Major failures (e.g., invalid coordinates, uncaught routing failures).
    *   `neutral`: Secondary events or system logs.
*   **Sources**:
    *   `ui` / `frontend`: Log events originating from Leaflet clicks or button triggers.
    *   `dispatch`: System logs originating from the background dispatcher thread.
