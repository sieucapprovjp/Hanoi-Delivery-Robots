# In-Memory Data Models & State Schema

The **AI Delivery Robots Simulation** application does not employ an external database engine (such as PostgreSQL or SQLite). Instead, the system operates on a stateful, thread-safe, in-memory database schema structured as nested dictionaries and class instances inside [app.py](file:///home/lan/projects/AI-Intro/delivery_robots/app.py).

---

## 🏛️ In-Memory Data Models

### 1. AppState Schema
Coordinates the global state of the simulation.

| Parameter | Data Type | Purpose |
| :--- | :--- | :--- |
| `graph_center` | `Tuple[float, float]` | Center coordinates of the Hanoi OSM graph |
| `graph_dist_meters` | `int` | Distance radius in meters loaded from center |
| `graph_network_type` | `str` | Filter for OSM street network (e.g., `'bike'`) |
| `simulation_start_time`| `float` | Host epoch time when simulation was triggered |
| `simulation_speed` | `float` | Speed multiplier (e.g., `1.0`, `2.5`) |
| `sim_now` | `float` | Current timeline elapsed in SimPy simulation |
| `rain_zones` | `List[RainZone]` | Collection of active rain clouds |
| `obstacles` | `List[Obstacle]` | List of placed road block incidents |
| `dynamic_traffic_routes`| `List[TrafficRoute]`| Dynamic traffic routes added via API |
| `delivery_history` | `List[Tuple[float, float]]` | Coordinates of successful drop-offs for KMeans |
| `road_graph` | `networkx.DiGraph` | Memory structure representing street intersections |
| `spatial_node_ids` | `np.ndarray` | Numpy array mapping tree node indices to IDs |
| `spatial_tree` | `sklearn.neighbors.BallTree` | Fast $O(\log N)$ nearest-neighbor coordinate lookup index |
| `api_logs` | `collections.deque` | FIFO logs queue (capped at max length of 500) |

---

### 2. Robot Agent Model
Tracks status, position, battery, and target routing coordinates.

```json
{
  "id": 1,
  "name": "Robot 2",
  "color": "#34a853",
  "lat": 21.0285,
  "lon": 105.8542,
  "status": "moving_to_pickup",
  "battery": 98.4,
  "current_path_length": 12,
  "path_index": 4,
  "route_target": "Pickup",
  "segment_duration": 1.2,
  "geometry_path": [
    { "lat": 21.0285, "lon": 105.8542 },
    { "lat": 21.0290, "lon": 105.8550 }
  ],
  "segment_geometry": [
    [
      { "lat": 21.0285, "lon": 105.8542 },
      { "lat": 21.0290, "lon": 105.8550 }
    ]
  ]
}
```

---

### 3. Task / Order Model
Represents dynamic order events.

```json
{
  "id": "ORDER-320",
  "pickup": {
    "lat": 21.0355,
    "lon": 105.8516,
    "name": "Dong Xuan Market"
  },
  "dropoff": {
    "lat": 21.0240,
    "lon": 105.8480,
    "name": "Trang Tien Plaza"
  },
  "pickup_path": [11204212, 43902302],
  "dropoff_path": [43902302, 59281203],
  "pickup_geometry_path": [{"lat": 21.035, "lon": 105.85}, ...],
  "pickup_segment_geometry": [[{"lat": 21.035, "lon": 105.85}, ...]]
}
```

---

### 4. Environmental Modifiers

#### RainZone Model
*   `name`: `str` (e.g., `"Rain 1"`)
*   `center`: `Tuple[float, float]` (Latitude, Longitude)
*   `radius`: `float` (influence range in meters)
*   `severity`: `float` (default `1.0`, represents incremental cost penalty)

#### TrafficRoute Model
*   `name`: `str` (e.g., `"Traffic 1"`)
*   `severity`: `float` (bounds `0.0` to `1.0`)
*   `path`: `List[Dict[str, float]]` (list of `{"lat": float, "lon": float}`)

#### Obstacle Model
*   `name`: `str`
*   `center`: `Tuple[float, float]`
*   `radius`: `float` (meters)
*   `severity`: `float` (bounds `1.0` to `50.0`)
*   `type`: `str` (`'roadblock'`, `'construction'`, or `'accident'`)

---

## 🔒 Concurrent Lock Map

To avoid race conditions and access errors between WSGI workers and background threads, data operations must acquire locks:

| Lock Name | Controlled Variables | File Origin |
| :--- | :--- | :--- |
| `_graph_lock` | `_road_graph`, `_projected_road_graph` | `delivery_robots/app.py` |
| `_history_lock` | `DELIVERY_HISTORY` | `delivery_robots/app.py` |
| `_dynamic_traffic_lock` | `_dynamic_traffic_routes` | `delivery_robots/app.py` |
| `_obstacles_lock` | `_obstacles` | `delivery_robots/app.py` |
| `_api_logs_lock` | `_api_logs` | `delivery_robots/app.py` |
