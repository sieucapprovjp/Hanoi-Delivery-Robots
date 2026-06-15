# Error Handling & Logging Strategy

This document describes validation, HTTP error responses, route failure behavior, and
logging in the current application.

## Validation

Input validation lives primarily in `delivery_robots/utils/validation.py` and route
handlers.

| Input | Rule |
| :--- | :--- |
| Latitude | `-90 <= lat <= 90` |
| Longitude | `-180 <= lon <= 180` |
| Radius | positive number |
| Count | non-negative integer |
| Traffic severity | bounded numeric value |
| Obstacle severity | bounded numeric value |
| K-means history | enough recorded points for requested cluster count |
| Dispatch payload | robots and deliveries must be lists with usable coordinates |

## HTTP Errors

Validation and business rule failures return JSON:

```json
{ "error": "Latitude must be between -90 and 90" }
```

Common statuses:

- `400`: invalid input or unmet business rule
- `404`: no route/path found where the endpoint contract expects a route
- `500`: uncaught server-side exception

## Route and Dispatch Failures

Route search can fail when graph connectivity or dynamic constraints make a path
unavailable. Dispatch handles this by:

- rejecting or skipping unreachable candidates
- preserving explanation records when `return_explanations` is enabled
- using finite fallback logic inside VRP where a partial distance matrix contains
  unreachable pairs
- returning no assignment rather than crashing the full dispatch request when all
  candidates are infeasible

## Logging

### In-Memory Logs

`GET /api/logs` reads recent entries from the in-memory deque. `POST /api/logs`
appends a new entry.

Example:

```json
{
  "ts": 1716382092100,
  "message": "Robot 1 assigned to order",
  "level": "info",
  "source": "dispatch"
}
```

### Persistent JSONL Logs

The project also writes lightweight persistent logs without a database:

- `logs/app-events.jsonl`
- `logs/delivery-history.jsonl`

These files are suitable for later analysis, debugging, and K-means/VRP research
without introducing database setup cost.

### Log Sources

- `ui`: frontend actions and simulation events
- `dispatch`: assignment and VRP events
- `backend`: route/environment/system events

### Log Levels

- `info`
- `warning`
- `error`
- `neutral`
