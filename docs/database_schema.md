# In-Memory State & Lightweight Persistence

The project does not use PostgreSQL, SQLite, or another database. Runtime state is
kept in memory inside `delivery_robots/app.py`, protected with locks where shared
collections may be updated. Lightweight persistence is handled with JSONL files under
`logs/`.

## App State

The Flask application state includes:

| Key / Concept | Type | Purpose |
| :--- | :--- | :--- |
| graph center/radius/network type | config values | Hoan Kiem graph loading parameters |
| simulation clock/speed | numbers | Time-dependent traffic and UI clock support |
| rain zones | list | Active weather penalty zones |
| obstacles | list | Active obstacle penalty zones |
| dynamic traffic routes | list | User-created congestion routes |
| delivery history | list | In-memory fallback pickup/dropoff points for K-means |
| road graph | NetworkX graph | OSMnx street graph |
| projected graph | NetworkX graph | Projected graph used for spatial operations |
| spatial tree/node ids | BallTree + arrays | Fast nearest-node lookup |
| API logs | deque | Recent in-memory UI/backend events |
| metrics | object/dict | Pathfinding and environment metrics |

## Frontend Robot Model

Robots are browser-side simulation agents. Important fields include:

```json
{
  "id": 5,
  "name": "Robot 5",
  "lat": 21.0303,
  "lon": 105.8539,
  "status": "routing_to_delivery",
  "battery": 49.3,
  "capacity": 3,
  "deliveryQueue": [],
  "routeSequence": [],
  "currentSequenceIndex": 0,
  "currentVrp": {
    "initialCost": 12400.0,
    "finalCost": 10300.0,
    "improvementRatio": 0.169
  }
}
```

Capacity means maximum active orders carried by one robot. The current demo value is
`3`.

## Delivery Model

```json
{
  "id": 12,
  "pickup": {
    "lat": 21.0355,
    "lon": 105.8516,
    "name": "Dong Xuan Market",
    "category": "market"
  },
  "dropoff": {
    "lat": 21.0240,
    "lon": 105.8480,
    "name": "Trang Tien Plaza",
    "category": "retail"
  },
  "createdAt": 1716382093000
}
```

## Dispatch Assignment Model

Assignments returned by `POST /api/dispatch/assign` may include:

```json
{
  "robotId": 5,
  "deliveryId": 12,
  "deliveryIds": [12, 14, 16],
  "route": {},
  "orderSequence": [],
  "routeSequence": [],
  "vrpStats": {},
  "explanation": {}
}
```

Single-order assignments remain compatible with older fields. Batch assignments add
VRP/PDP route sequencing and metrics.

## Environment Models

### Rain Zone

- `name`
- `center`: `[lat, lon]`
- `radius`: meters
- `severity`: incremental multiplier input

### Traffic Route

- `name`
- `severity`: `0.0` to `1.0`
- `path`: list of `{lat, lon}`

### Obstacle

- `name`
- `center`: `[lat, lon]`
- `radius`: meters
- `severity`: `1.0` to `50.0`
- `type`: `roadblock`, `construction`, or `accident`

## JSONL Files

`logs/app-events.jsonl` stores UI, dispatch, and VRP events.

`logs/delivery-history.jsonl` stores completed pickup/dropoff history. K-means hub optimization now prefers this file and falls back to in-memory history if the file has too few valid points.

Each line is a standalone JSON object so the files can be processed without a
database migration.

## Locks

Shared state should be accessed through the lock pattern already defined in
`delivery_robots/app.py`, especially for graph state, delivery history, dynamic
traffic routes, obstacles, rain zones, and API logs.
