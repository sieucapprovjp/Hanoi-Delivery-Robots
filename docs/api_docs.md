# API Documentation

The backend exposes REST APIs from a Flask server. The frontend simulation uses these
endpoints for routing, dispatch, environment controls, metrics, logs, XAI, and hub
optimization.

Base local URL:

```text
http://127.0.0.1:5002
```

## System

### `GET /api/health`

Returns service health.

```json
{ "status": "ok" }
```

### `GET /api/clock`

Returns simulated clock and rush-hour information.

### `GET /api/metrics`

Returns pathfinding metrics and active environment factor counts.

Optional query:

- `static=true`: include graph node/edge counts when available.

## Logs

### `GET /api/logs`

Returns recent in-memory logs.

Query:

- `limit`: optional, default `200`, bounded by the backend.

### `POST /api/logs`

Appends an app event to in-memory logs and persistent JSONL logs.

```json
{
  "message": "Simulation started",
  "level": "info",
  "source": "ui",
  "ts": 1716382093000
}
```

### `POST /api/log_delivery`

Records delivery points in memory and appends them to persistent K-means delivery history.

Typical payload:

```json
{
  "pickup": { "lat": 21.0355, "lon": 105.8516 },
  "dropoff": { "lat": 21.0240, "lon": 105.8480 },
  "deliveryId": 12
}
```

## Routing

### `GET /api/route`

Calculates a weighted route between two coordinates.

Query:

- `fromLat`
- `fromLon`
- `toLat`
- `toLon`
- `algo`: optional, `astar`, `dijkstra`, `gbfs`, or `greedy` alias

Response includes route geometry, distance/cost, explored node count, timing, and a
cost breakdown.

```json
{
  "algorithm": "astar",
  "path": [{ "lat": 21.0285, "lon": 105.8542 }],
  "distance": 9165.0,
  "nodesExplored": 120,
  "calculationTime": 4.2,
  "costBreakdown": {
    "baseDistance": 7000.0,
    "trafficPenalty": 900.0,
    "rainPenalty": 800.0,
    "obstaclePenalty": 0.0,
    "totalCost": 8700.0,
    "estimatedMinutes": 18.4
  }
}
```

### `GET /api/snap`

Snaps a coordinate to the nearest road node.

Query:

- `lat`
- `lon`

## Dispatch, CSP, XAI, and VRP

### `POST /api/dispatch/assign`

Assigns pending deliveries to feasible robots.

Dispatch flow:

1. Score delivery priority.
2. Apply CSP filters: robot status, battery, capacity, pickup distance.
3. Expand the best route candidates.
4. Batch deliveries when queue pressure warrants it.
5. Solve pickup/dropoff order with VRP/PDP Simulated Annealing for multi-order batches.
6. Return assignment payloads and optional explanations.

Payload shape:

```json
{
  "robots": [
    {
      "id": 5,
      "lat": 21.0303,
      "lon": 105.8539,
      "status": "idle",
      "battery": 80,
      "capacity": 3,
      "currentLoad": 0,
      "roadMemory": {}
    }
  ],
  "deliveries": [
    {
      "id": 12,
      "pickup": { "lat": 21.0355, "lon": 105.8516, "category": "market" },
      "dropoff": { "lat": 21.0240, "lon": 105.8480, "category": "retail" },
      "createdAt": 1716382093000
    }
  ],
  "algorithm": "astar",
  "return_explanations": true
}
```

Response shape:

```json
{
  "assignments": [
    {
      "robotId": 5,
      "deliveryId": 12,
      "deliveryIds": [12, 14, 16],
      "route": {},
      "orderSequence": [],
      "routeSequence": [],
      "vrpStats": {
        "iterations": 5000,
        "acceptedMoves": 312,
        "improvements": 18
      },
      "vrpCost": 10300.0,
      "vrpInitialCost": 12400.0,
      "vrpImprovementRatio": 0.169,
      "explanation": {}
    }
  ],
  "explanations": []
}
```

Capacity is currently `3` active orders per robot.

## K-means Hubs

### `POST /api/optimize-hubs`

Runs K-means on recorded delivery coordinates and returns optimized hub locations. The optimizer prefers `logs/delivery-history.jsonl` and falls back to in-memory history when the log file does not contain enough valid points.

```json
{
  "hubs": [
    { "id": 0, "lat": 21.025, "lon": 105.851, "name": "AI Hub A" }
  ]
}
```

If there are not enough points, the API returns `400`.

## Insider and Classical AI

### `GET /api/astep`

Runs an A* expansion demo and returns recorded steps: selected node, `g`, `h`, `f`,
open set size, closed set size, and final path data.

### `GET /api/insider`

Compares A*, Dijkstra, GBFS, and BFS with environment-aware weights for explainability.

### `GET /api/classical/compare`

Compares A*, Dijkstra, GBFS, and BFS with base physical edge length only. This is for
academic comparison and intentionally ignores rain/traffic/obstacle penalties.

## Environment

### Rain

- `GET /api/weather`
- `GET /api/rain/list`
- `POST /api/rain/add`
- `POST /api/rain/randomize`
- `POST /api/rain/clear`

`POST /api/rain/add` example:

```json
{
  "lat": 21.0312,
  "lon": 105.8510,
  "radius": 120.0,
  "severity": 1.0
}
```

### Traffic

- `GET /api/traffic`
- `GET /api/traffic/list`
- `POST /api/traffic/add`
- `POST /api/traffic/randomize`
- `POST /api/traffic/clear`

`POST /api/traffic/add` example:

```json
{
  "startLat": 21.0240,
  "startLon": 105.8480,
  "endLat": 21.0285,
  "endLon": 105.8542,
  "severity": 0.8
}
```

### Obstacles

- `GET /api/obstacle/list`
- `POST /api/obstacle/add`
- `POST /api/obstacle/randomize`
- `POST /api/obstacle/clear`

`POST /api/obstacle/add` example:

```json
{
  "lat": 21.0275,
  "lon": 105.8520,
  "radius": 80.0,
  "severity": 20.0,
  "type": "construction"
}
```

## Charging Stations

- `GET /api/charging-stations`
- `PUT /api/charging-stations/<station_id>`

These endpoints expose and update charging station/hub coordinates used by the frontend.
