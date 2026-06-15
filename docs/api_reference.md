# API Reference

This document tracks the API surface used by the feature-engine branch.

## Simulation And Data

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/` | Main Leaflet simulation UI. |
| `GET` | `/api/health` | Health check. |
| `GET` | `/api/data/locations` | Static Hoan Kiem delivery locations. |
| `GET` | `/api/data/hubs` | Current charging hubs. |
| `GET` | `/api/data/robots` | Initial robot metadata. |
| `GET` | `/api/orders` | Current order lifecycle state. |

## Routing And Environment

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/route` | Route with cost breakdown under current rain, traffic, and obstacle weights. |
| `GET` | `/api/snap` | Compatibility endpoint that returns nearest graph node coordinates for a lat/lon. |
| `GET` | `/api/weather` | Current rain zones. |
| `GET` | `/api/traffic` | Current active traffic segments. |
| `GET` | `/api/metrics` | Routing and reliability metrics. |
| `GET/POST` | `/api/routing/neighbor-policy` | Read/update neighbor ordering policy. |

## Dispatch

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/dispatch/model` | Current assignment policy. |
| `POST` | `/api/dispatch/select` | Set assignment policy: `nearest_idle`, `nearest_feasible`, `weighted_cost`, or `hungarian`. |
| `GET` | `/api/dispatch/explanations` | Latest CSP/XAI explanations. Supports `limit`. |
| `POST` | `/api/dispatch/assign` | Compatibility wrapper for legacy stateless dispatch requests. Internally uses the feature-engine CSP/XAI adapter. |

`POST /api/dispatch/assign` accepts:

```json
{
  "robots": [
    {
      "id": "r1",
      "name": "Robot 1",
      "lat": 21.0,
      "lon": 105.0,
      "battery": 100,
      "status": "idle",
      "capacity": 3,
      "currentLoad": 0
    }
  ],
  "deliveries": [
    {
      "id": "o1",
      "pickup": {"lat": 21.001, "lon": 105.0, "name": "Pickup"},
      "destination": {"lat": 21.002, "lon": 105.0, "name": "Dropoff"}
    }
  ],
  "model": "nearest_idle"
}
```

The response contains `assignments` and `explanations`. When VRP batching applies, assignment entries include `deliveryIds`, `orderSequence`, `vrpStats`, `vrpCost`, and `vrpImprovementRatio`.

## Logs And Hub Optimization

| Method | Path | Description |
| --- | --- | --- |
| `GET/POST` | `/api/logs` | In-memory API/event logs. |
| `POST` | `/api/log_delivery` | Persist delivery pickup/dropoff history to RAM and JSONL. |
| `POST` | `/api/optimize-hubs` | Run K-means using JSONL delivery history first, then RAM fallback. |

Persistent delivery history is stored as JSONL in `logs/delivery-history.jsonl`.

## WebSocket Events

| Event | Direction | Payload |
| --- | --- | --- |
| `start_simulation` | client -> server | Starts SimPy simulation. |
| `pause_simulation` | client -> server | Pauses simulation loop. |
| `reset_simulation` | client -> server | Resets simulation state. |
| `robot_state_update` | server -> client | Robot position, status, battery, path geometry, `capacity`, `current_load`, and `active_orders`. |
| `order_state_update` | server -> client | Order lifecycle update. |
| `dispatch_explanations_update` | server -> client | New CSP/XAI explanation batch. |
| `clock_update` | server -> client | Simulation clock and rush-hour state. |
| `system_event` | server -> client | Human-readable simulation event. |
