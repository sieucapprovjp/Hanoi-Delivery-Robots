# API Documentation

This document describes the REST API endpoints and WebSocket channels exposed by the backend of the **AI Delivery Robots Simulation** application.

---

## 🌐 REST API Endpoints

### 1. General & System

#### `GET /api/health`
*   **Description**: Basic service check.
*   **Response (200 OK)**:
    ```json
    { "status": "ok" }
    ```

#### `GET /api/logs`
*   **Description**: Retrieves recent client and backend log history.
*   **Query Parameters**:
    *   `limit` (integer, optional, default: 200, bounds: 1 to 1000)
*   **Response (200 OK)**:
    ```json
    {
      "count": 2,
      "logs": [
        {
          "ts": 1716382092100,
          "message": "Robot 1 assigned to order",
          "level": "info",
          "source": "dispatch"
        },
        {
          "ts": 1716382091000,
          "message": "✅ Display Ready",
          "level": "info",
          "source": "ui"
        }
      ]
    }
    ```

#### `POST /api/logs`
*   **Description**: Appends a log entry to the in-memory log deque.
*   **Request Payload**:
    ```json
    {
      "message": "Simulation speed adjusted to 2x",
      "level": "info",
      "source": "ui",
      "ts": 1716382093000
    }
    ```
*   **Response (200 OK / 400 Bad Request)**:
    *   `200 OK`: `{"status": "ok"}`
    *   `400 Bad Request`: `{"error": "message is required"}`

---

### 2. Environment & Routing Factors

#### `GET /api/weather`
*   **Description**: Fetches active rain storm zones and multipliers.
*   **Response (200 OK)**:
    ```json
    {
      "rainZones": [
        {
          "name": "Rain 1",
          "center": { "lat": 21.0285, "lon": 105.8542 },
          "radius": 150.0,
          "multiplier": 2.0
        }
      ]
    }
    ```

#### `POST /api/rain/add`
*   **Description**: Places a custom rain storm zone.
*   **Request Payload**:
    ```json
    {
      "lat": 21.0312,
      "lon": 105.8510,
      "radius": 120.0
    }
    ```
*   **Response (200 OK / 400 Bad Request)**:
    *   `200 OK`:
        ```json
        {
          "message": "Added",
          "rainZone": {
            "name": "Rain 2",
            "center": { "lat": 21.0312, "lon": 105.851 },
            "radius": 120.0
          }
        }
        ```

#### `POST /api/rain/randomize`
*   **Description**: Clears rain zones and populates random coordinates within Hanoi bounds.
*   **Request Payload**:
    ```json
    {
      "count": 3,
      "minRadius": 100,
      "maxRadius": 200
    }
    ```
*   **Response (200 OK)**: list of generated zones.

#### `POST /api/rain/clear`
*   **Description**: Erases all active rain zones.
*   **Response (200 OK)**: `{"message": "Cleared"}`

---

#### `GET /api/traffic`
*   **Description**: Fetches congestion segments under current time intervals.
*   **Response (200 OK)**:
    ```json
    {
      "roads": [
        {
          "name": "Traffic 1",
          "segments": [
            {
              "points": [[21.02, 105.84], [21.021, 105.841]],
              "severity": 0.52
            }
          ]
        }
      ],
      "updatedAt": 1716382092.42
    }
    ```

#### `POST /api/traffic/add`
*   **Description**: Commences a congestion zone path between closest nodes.
*   **Request Payload**:
    ```json
    {
      "startLat": 21.0240,
      "startLon": 105.8480,
      "endLat": 21.0285,
      "endLon": 105.8542,
      "severity": 0.8
    }
    ```
*   **Response (200 OK / 400 Bad Request)**: Returns route layout and path segments.

#### `POST /api/traffic/clear`
*   **Description**: Resets dynamic traffic segments.
*   **Response (200 OK)**: `{"message": "Cleared"}`

---

#### `GET /api/route`
*   **Description**: Calculates a path between two coordinates, returning the route geometry and cost breakdown (base distance + traffic, rain, and obstacle penalties).
*   **Query Parameters**:
    *   `fromLat` (float, required)
    *   `fromLon` (float, required)
    *   `toLat` (float, required)
    *   `toLon` (float, required)
*   **Response (200 OK)**:
    ```json
    {
      "path": [{"lat": 21.0000, "lon": 105.0000}, {"lat": 21.0020, "lon": 105.0020}],
      "distance": 100.0,
      "costBreakdown": {
        "baseDistance": 100.0,
        "trafficPenalty": 0.0,
        "rainPenalty": 0.0,
        "obstaclePenalty": 0.0,
        "totalCost": 100.0,
        "estimatedMinutes": 0.8
      }
    }
    ```
*   **Response (400 Bad Request / 404 Not Found)**:
    *   `400 Bad Request`: `{"error": "Invalid coordinates"}`
    *   `404 Not Found`: `{"error": "No path found between the specified coordinates"}`

---

#### `GET /api/obstacle/list`
*   **Description**: Retrieves currently placed roadblock incidents.
*   **Response (200 OK)**: List of obstacle objects with center, radius, severity, type.

#### `POST /api/obstacle/add`
*   **Description**: Adds a roadblock, construction zone, or accident.
*   **Request Payload**:
    ```json
    {
      "lat": 21.0275,
      "lon": 105.8520,
      "radius": 80.0,
      "severity": 20.0,
      "type": "construction"
    }
    ```
*   **Response (200 OK)**: Confirms added obstacle details.

#### `POST /api/obstacle/clear`
*   **Description**: Clears active roadblock incidents.
*   **Response (200 OK)**: `{"message": "Cleared"}`

---

### 3. Analytics & Optimizations

#### `GET /api/metrics`
*   **Description**: Fetches execution speed metrics, nodes explored, and factors counts.
*   **Query Parameters**:
    *   `static` (boolean, optional, default: `false`. Includes graph node/edge counts if `true`).
*   **Response (200 OK)**:
    ```json
    {
      "activeFactors": { "rainZones": 2, "trafficRoutes": 1, "obstacles": 0 },
      "pathfinding": {
        "avgCalculationTime": 1.25,
        "avgNodesExplored": 86.4,
        "avgPathLength": 1240.2,
        "lastCalculationTime": 1.1,
        "maxCalculationTime": 8.4,
        "minCalculationTime": 0.2,
        "totalCalculations": 45
      }
    }
    ```

#### `POST /api/optimize-hubs`
*   **Description**: Applies KMeans on historical successful delivery coordinates to locate new central depots.
*   **Response (200 OK / 400 Bad Request)**:
    *   `200 OK`:
        ```json
        {
          "hubs": [
            { "id": 0, "lat": 21.025, "lon": 105.851, "name": "AI Hub A" }
          ]
        }
        ```
    *   `400 Bad Request`: `{"error": "Not enough delivery data to optimize hubs. Need at least 5 points."}`

---

## 🔌 WebSockets (Flask-SocketIO Channel Events)

### Client-to-Server Events (Action Triggers)
*   **`start_simulation`**: Instructs backend to begin simulator execution thread.
*   **`pause_simulation`**: Pauses SimPy clock progression.
*   **`reset_simulation`**: Erases active queues, re-aligns robots to default hubs, and updates coordinate statuses.

### Server-to-Client Events (State Broadcasts)
*   **`clock_update`**: Real-time simulated time ticks.
    ```json
    {
      "time": { "display": "06:14:32" },
      "rushHour": { "isActive": false, "multiplier": 1.0 },
      "simulationSpeed": 1.5
    }
    ```
*   **`robot_state_update`**: Broadcasts specific coordinate positions, battery, status strings.
    ```json
    {
      "id": 1,
      "name": "Robot 2",
      "color": "#34a853",
      "lat": 21.0285,
      "lon": 105.8542,
      "status": "moving_to_pickup",
      "path_index": 4,
      "route_target": "Pickup",
      "battery": 98.4,
      "current_path_length": 12,
      "segment_duration": 1.2,
      "geometry_path": [{"lat": 21.028, "lon": 105.85}, ...],
      "segment_geometry": [[{"lat": 21.028, "lon": 105.85}, ...]]
    }
    ```
*   **`system_event`**: Broad-spectrum simulation status updates.
    ```json
    {
      "message": "New order ORDER-120 generated from Trang Tien Plaza to Melia Hanoi"
    }
    ```
