# AI-Optimized Hub Placement (k-means)

## Objective
- Add a k-means based optimizer that places robot hubs at demand hotspots using historical delivery coordinates.
- Reduce empty travel distance from robot spawn points to first pickup.

## What Is Implemented
- Backend dependency setup:
  - Added `scikit-learn` and `numpy` in `requirements.txt`.
- Backend data collection and optimization API:
  - `POST /api/log_delivery`: stores pickup/dropoff coordinates in memory and appends them to `logs/delivery-history.jsonl`.
  - `POST /api/optimize-hubs`: runs k-means (`k=5`) and returns centroid hubs.
  - K-means now prefers the persistent JSONL history and falls back to in-memory history if the file does not contain enough valid points.
- Frontend simulation integration in `delivery_robots/static/js/simulation.js`:
  - `logDeliveryData(delivery)` sends each generated delivery to backend.
  - `optimizeHubs()` calls optimizer endpoint and repositions robots.
- Frontend map visualization in `delivery_robots/static/js/map.js`:
  - `drawHubs(hubs)` renders optimized hub markers and influence circles.
- Frontend control wiring:
  - Added `🧠 Optimize Hubs` button in `delivery_robots/templates/index.html`.
  - Added click handler in `delivery_robots/static/js/app.js`.

## API Contracts

### POST `/api/log_delivery`
Request JSON:
```json
{
  "pickupLat": 21.0285,
  "pickupLon": 105.8542,
  "dropoffLat": 21.0334,
  "dropoffLon": 105.8509
}
```

Response JSON:
```json
{
  "status": "success"
}
```

### POST `/api/optimize-hubs`
Request JSON: none

Response JSON:
```json
{
  "hubs": [
    {"id": 0, "lat": 21.0291, "lon": 105.8537, "name": "AI Hub A"},
    {"id": 1, "lat": 21.0332, "lon": 105.8519, "name": "AI Hub B"}
  ]
}
```

Error when history is too small:
```json
{
  "error": "Not enough delivery data to optimize hubs. Need at least 5 points."
}
```

## Demo Walkthrough (Midterm)
1. Start simulation and let it run for ~30-60 seconds to collect delivery points, or reuse existing delivery history from `logs/delivery-history.jsonl`.
2. Open logs/dispatch panel to show ongoing AI decisions.
3. Click `🧠 Optimize Hubs` in the control panel.
4. Explain that k-means clusters demand points and returns 5 centroids.
5. Show robots repositioning to centroid hubs and new blue hub markers on map.
6. Continue simulation and discuss expected reduction in deadhead travel.

## AI Concepts You Can Explain
- **Unsupervised Learning:** k-means finds structure in unlabeled coordinate data.
- **Centroid Meaning:** each centroid approximates a high-demand area.
- **System Integration:**
  - Search layer: A* pathfinding for route decisions.
  - Learning layer: road memory (RL-lite) for segment penalties.
  - Clustering layer: k-means for macro-level fleet placement.

## Notes / Next Improvements
- Add a metric card for "empty distance before vs after optimization".
- Add controls to clear or scope delivery history when a clean demo run is needed.
- Optionally run optimization every fixed interval (e.g., every 2 simulated hours).
- Optionally keep separate pickup-only vs dropoff-only clustering modes.
