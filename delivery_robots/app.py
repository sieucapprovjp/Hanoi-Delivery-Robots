from flask import Flask, jsonify, render_template, request
import heapq
import json
import math
import threading
import time
from collections import deque
import numpy as np
from sklearn.cluster import KMeans

import networkx as nx

from .classical_ai import compare_classical_algorithms
from .geo_utils import haversine_distance, point_to_segment_distance_meters
from .metrics_utils import build_metrics_payload, create_metrics, record_route_metrics
from .route_analysis import build_route_response, nearest_node_id
from .routes_api import register_api_routes
from .validation import (
    validate_coordinate,
    validate_lat_lon,
    validate_non_negative_int,
    validate_positive_number,
)

app = Flask(__name__)

GRAPH_CENTER = (21.0285, 105.8542)
GRAPH_DIST_METERS = 2200
GRAPH_NETWORK_TYPE = "bike"
TRAFFIC_ANCHORS = []
TRAFFIC_PERIOD_SECONDS = 36
RAIN_ZONES = []

# Simulation clock and rush hour configuration
_simulation_start_time = time.time()
_simulation_speed = 60  # 1 real second = 1 simulation minute (60x speed)
RUSH_HOURS = [
    {"name": "Morning Rush", "start": 7, "end": 9, "multiplier": 2.5},
    {"name": "Lunch Traffic", "start": 11, "end": 13, "multiplier": 1.3},
    {"name": "Evening Rush", "start": 17, "end": 19, "multiplier": 3.0},
]

_graph_lock = threading.Lock()
_road_graph = None
_projected_road_graph = None
_traffic_routes = None
_ox = None

# Delivery history for k-means optimization
DELIVERY_HISTORY = []
_history_lock = threading.Lock()


def get_road_graph():

    global _road_graph, _projected_road_graph, _traffic_routes, _ox

    if (
        _road_graph is not None
        and _projected_road_graph is not None
        and _traffic_routes is not None
    ):
        return _road_graph, _projected_road_graph, _traffic_routes

    with _graph_lock:
        if _ox is None:
            import osmnx as ox

            _ox = ox

        if _road_graph is None:
            _road_graph = _ox.graph_from_point(
                GRAPH_CENTER,
                dist=GRAPH_DIST_METERS,
                network_type=GRAPH_NETWORK_TYPE,
                simplify=True,
            )
            _projected_road_graph = _ox.project_graph(_road_graph)
            _traffic_routes = build_traffic_routes(_road_graph)

    return _road_graph, _projected_road_graph, _traffic_routes


def build_traffic_routes(graph):
    routes = []

    for anchor in TRAFFIC_ANCHORS:
        start_lat, start_lon = anchor["start"]
        end_lat, end_lon = anchor["end"]
        start_node = nearest_node_id(graph, start_lat, start_lon, _ox)
        end_node = nearest_node_id(graph, end_lat, end_lon, _ox)
        route_nodes = nx.shortest_path(graph, start_node, end_node, weight="length")
        route_payload = build_route_response(
            graph,
            route_nodes,
            traffic_penalty_for_point,
            rain_penalty_for_point,
            obstacle_penalty_for_point,
            include_cost_breakdown=False,
        )
        routes.append(
            {
                "name": anchor["name"],
                "severity": anchor["severity"],
                "path": route_payload["path"],
            }
        )

    return routes


def get_simulation_time():
    """Returns simulated time based on real elapsed time and simulation speed."""
    elapsed_real = time.time() - _simulation_start_time
    elapsed_simulated = elapsed_real * _simulation_speed
    # Start at 6:00 AM (21600 seconds from midnight)
    sim_seconds_from_midnight = 21600 + elapsed_simulated
    sim_seconds_from_midnight = sim_seconds_from_midnight % 86400  # Wrap at 24h
    hours = int(sim_seconds_from_midnight // 3600)
    minutes = int((sim_seconds_from_midnight % 3600) // 60)
    seconds = int(sim_seconds_from_midnight % 60)
    return hours, minutes, seconds


def get_rush_hour_multiplier():
    """Returns traffic multiplier based on current simulated time."""
    hours, minutes, seconds = get_simulation_time()
    current_hour = hours + minutes / 60.0

    for rush in RUSH_HOURS:
        if rush["start"] <= current_hour < rush["end"]:
            # Smooth transition: ramp up at start, ramp down at end
            progress = (current_hour - rush["start"]) / (rush["end"] - rush["start"])
            # Peak in the middle
            multiplier = 1 + (rush["multiplier"] - 1) * math.sin(progress * math.pi)
            return multiplier, rush["name"]

    return 1.0, "Normal"


def traffic_penalty_for_point(lat, lon):
    penalty = 1.0
    now = time.time()
    if _traffic_routes is None and not _dynamic_traffic_routes:
        return penalty

    traffic_routes = list(_traffic_routes or [])
    with _dynamic_traffic_lock:
        traffic_routes.extend(_dynamic_traffic_routes)

    rush_multiplier, _ = get_rush_hour_multiplier()
    penalty *= rush_multiplier

    for road in traffic_routes:
        if len(road["path"]) < 2:
            continue

        progress = (now / TRAFFIC_PERIOD_SECONDS + road["severity"]) % 1
        active_segment = progress * (len(road["path"]) - 1)

        for idx in range(len(road["path"]) - 1):
            if abs(idx - active_segment) > 0.9:
                continue

            start = road["path"][idx]
            end = road["path"][idx + 1]
            distance = point_to_segment_distance_meters(
                lat, lon, start["lat"], start["lon"], end["lat"], end["lon"]
            )

            if distance <= 24:
                segment_strength = max(0.35, 1 - abs(idx - active_segment))
                penalty = max(penalty, 1 + road["severity"] * segment_strength * 3.2)

    return penalty


def rain_penalty_for_point(lat, lon):
    penalty = 1.0

    for zone in RAIN_ZONES:
        center_lat, center_lon = zone["center"]
        distance = haversine_distance(lat, lon, center_lat, center_lon)
        if distance <= zone["radius"]:
            penalty = max(penalty, 1 + zone.get("severity", 1.0))

    return penalty


def obstacle_penalty_for_point(lat, lon):
    penalty = 1.0

    with _obstacles_lock:
        obstacles = list(_obstacles)

    for obstacle in obstacles:
        center_lat, center_lon = obstacle["center"]
        distance = haversine_distance(lat, lon, center_lat, center_lon)
        radius = obstacle["radius"]
        if distance > radius:
            continue

        closeness = 1 - (distance / radius if radius else 1)
        severity = obstacle.get("severity", 10.0)
        penalty = max(penalty, 1 + (severity / 10.0) * max(0.2, closeness))

    return penalty


def edge_weight_with_traffic(from_node, to_node, edge_data):
    from_data = _road_graph.nodes[from_node]
    to_data = _road_graph.nodes[to_node]
    midpoint_lat = (from_data["y"] + to_data["y"]) / 2
    midpoint_lon = (from_data["x"] + to_data["x"]) / 2
    penalty = traffic_penalty_for_point(midpoint_lat, midpoint_lon)
    penalty *= rain_penalty_for_point(midpoint_lat, midpoint_lon)
    penalty *= obstacle_penalty_for_point(midpoint_lat, midpoint_lon)

    if "length" in edge_data:
        return edge_data.get("length", 0.0) * penalty

    best_length = min(data.get("length", float("inf")) for data in edge_data.values())
    return best_length * penalty


def _reconstruct_node_path(came_from, current):
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path


def _run_weighted_route_search(
    graph,
    start_node,
    end_node,
    goal_lat,
    goal_lon,
    weight_fn,
    algorithm,
):
    g_score = {start_node: 0.0}
    came_from = {}
    visited = set()
    nodes_explored = 0

    start_h = haversine_distance(
        graph.nodes[start_node]["y"],
        graph.nodes[start_node]["x"],
        goal_lat,
        goal_lon,
    )

    if algorithm == "dijkstra":
        open_set = [(0.0, start_node)]
    elif algorithm == "gbfs":
        open_set = [(start_h, start_node)]
    else:
        open_set = [(start_h, start_node)]

    while open_set:
        _, current = heapq.heappop(open_set)
        if current in visited:
            continue

        visited.add(current)
        nodes_explored += 1

        if current == end_node:
            return _reconstruct_node_path(came_from, current), nodes_explored

        for neighbor in graph.neighbors(current):
            if neighbor in visited:
                continue

            edge_data = graph[current][neighbor]
            tentative_g = g_score[current] + weight_fn(current, neighbor, edge_data)
            if tentative_g >= g_score.get(neighbor, float("inf")):
                continue

            came_from[neighbor] = current
            g_score[neighbor] = tentative_g

            h_neighbor = haversine_distance(
                graph.nodes[neighbor]["y"],
                graph.nodes[neighbor]["x"],
                goal_lat,
                goal_lon,
            )

            if algorithm == "dijkstra":
                priority = tentative_g
            elif algorithm == "gbfs":
                priority = h_neighbor
            else:
                priority = tentative_g + h_neighbor

            heapq.heappush(open_set, (priority, neighbor))

    raise nx.NetworkXNoPath


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/route")
def route():
    start_t = time.time()
    try:
        from_lat = validate_coordinate(request.args.get("fromLat"), "fromLat")
        from_lon = validate_coordinate(request.args.get("fromLon"), "fromLon")
        to_lat = validate_coordinate(request.args.get("toLat"), "toLat")
        to_lon = validate_coordinate(request.args.get("toLon"), "toLon")
        validate_lat_lon(from_lat, from_lon)
        validate_lat_lon(to_lat, to_lon)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if from_lat == to_lat and from_lon == to_lon:
        return jsonify({"path": [{"lat": from_lat, "lon": from_lon}], "distance": 0})

    # Parse robot memory (optional — falls back to empty dict)
    try:
        road_memory = json.loads(request.args.get("memory", "{}"))
    except Exception:
        road_memory = {}

    algo = (request.args.get("algo") or "astar").strip().lower()
    if algo not in {"astar", "gbfs", "dijkstra"}:
        return jsonify({"error": "Invalid algo. Use astar, gbfs, or dijkstra."}), 400

    try:
        graph, projected_graph, _ = get_road_graph()
        start_node = nearest_node_id(graph, from_lat, from_lon, _ox)
        end_node = nearest_node_id(graph, to_lat, to_lon, _ox)

        def edge_weight_with_memory(from_node, to_node, edge_data):
            base = edge_weight_with_traffic(from_node, to_node, edge_data)
            # Look up memory penalty for this segment
            fn = graph.nodes[from_node]
            tn = graph.nodes[to_node]
            key = f"{fn['y']:.4f},{fn['x']:.4f}->{tn['y']:.4f},{tn['x']:.4f}"
            memory_penalty = road_memory.get(key, 1.0)
            return base * memory_penalty

        weight_fn = edge_weight_with_memory if road_memory else edge_weight_with_traffic
        route_nodes, nodes_explored = _run_weighted_route_search(
            graph,
            start_node,
            end_node,
            to_lat,
            to_lon,
            weight_fn,
            algo,
        )
        payload = build_route_response(
            graph,
            route_nodes,
            traffic_penalty_for_point,
            rain_penalty_for_point,
            obstacle_penalty_for_point,
        )
        payload["start"] = {
            "lat": graph.nodes[start_node]["y"],
            "lon": graph.nodes[start_node]["x"],
        }
        payload["end"] = {
            "lat": graph.nodes[end_node]["y"],
            "lon": graph.nodes[end_node]["x"],
        }
        payload["algo"] = algo

        calc_time = (time.time() - start_t) * 1000
        record_route_metrics(_metrics, calc_time, nodes_explored, len(route_nodes))
        payload["timeMs"] = round(calc_time, 2)
        payload["nodesExplored"] = nodes_explored
        payload["pathCost"] = payload.get("costBreakdown", {}).get(
            "totalCost", round(payload.get("distance", 0.0), 1)
        )

        return jsonify(payload)
    except nx.NetworkXNoPath:
        fallback_distance = haversine_distance(from_lat, from_lon, to_lat, to_lon)
        return jsonify(
            {
                "path": [
                    {"lat": from_lat, "lon": from_lon},
                    {"lat": to_lat, "lon": to_lon},
                ],
                "distance": fallback_distance,
                "fallback": True,
            }
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/snap")
def snap():
    try:
        lat = validate_coordinate(request.args.get("lat"), "lat")
        lon = validate_coordinate(request.args.get("lon"), "lon")
        validate_lat_lon(lat, lon)
        graph, projected_graph, _ = get_road_graph()
        node_id = nearest_node_id(graph, lat, lon, _ox)
        return jsonify(
            {
                "lat": graph.nodes[node_id]["y"],
                "lon": graph.nodes[node_id]["x"],
            }
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/log_delivery", methods=["POST"])
def log_delivery():
    """Records pickup and drop-off coordinates for k-means clustering."""
    try:
        data = request.json
        pickup_lat = validate_coordinate(data.get("pickupLat"), "pickupLat")
        pickup_lon = validate_coordinate(data.get("pickupLon"), "pickupLon")
        dropoff_lat = validate_coordinate(data.get("dropoffLat"), "dropoffLat")
        dropoff_lon = validate_coordinate(data.get("dropoffLon"), "dropoffLon")

        with _history_lock:
            DELIVERY_HISTORY.append([pickup_lat, pickup_lon])
            DELIVERY_HISTORY.append([dropoff_lat, dropoff_lon])

        return jsonify({"status": "success"}), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/optimize-hubs", methods=["POST"])
def optimize_hubs():
    """Uses k-means clustering to find optimal robot hub locations."""
    with _history_lock:
        if len(DELIVERY_HISTORY) < 5:
            return jsonify(
                {
                    "error": "Not enough delivery data to optimize hubs. Need at least 5 points."
                }
            ), 400

        data = np.array(DELIVERY_HISTORY)

    try:
        # We want 5 hubs for our 5 robots
        kmeans = KMeans(n_clusters=5, n_init="auto", random_state=42)
        kmeans.fit(data)
        centroids = kmeans.cluster_centers_

        hubs = []
        for i, center in enumerate(centroids):
            hubs.append(
                {
                    "id": i,
                    "lat": float(center[0]),
                    "lon": float(center[1]),
                    "name": f"AI Hub {chr(65 + i)}",
                }
            )

        return jsonify({"hubs": hubs}), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ========== Traffic Controls ==========

_dynamic_traffic_lock = threading.Lock()
_dynamic_traffic_routes = []


# ========== Obstacles Controls ==========
_obstacles_lock = threading.Lock()
_obstacles = []


# ========== Metrics ==========
_metrics = create_metrics()
_api_logs_lock = threading.Lock()
_api_logs = deque(maxlen=500)


def _get_ox():
    return _ox


register_api_routes(
    app,
    {
        "get_road_graph": get_road_graph,
        "road_graph_getter": lambda: _road_graph,
        "get_simulation_time": get_simulation_time,
        "get_rush_hour_multiplier": get_rush_hour_multiplier,
        "build_metrics_payload": build_metrics_payload,
        "build_route_response": build_route_response,
        "nearest_node_id": nearest_node_id,
        "validate_coordinate": validate_coordinate,
        "validate_lat_lon": validate_lat_lon,
        "validate_non_negative_int": validate_non_negative_int,
        "validate_positive_number": validate_positive_number,
        "traffic_penalty_for_point": traffic_penalty_for_point,
        "rain_penalty_for_point": rain_penalty_for_point,
        "obstacle_penalty_for_point": obstacle_penalty_for_point,
        "traffic_period_seconds": TRAFFIC_PERIOD_SECONDS,
        "rush_hours": RUSH_HOURS,
        "simulation_speed": _simulation_speed,
        "rain_zones": RAIN_ZONES,
        "dynamic_traffic_lock": _dynamic_traffic_lock,
        "dynamic_traffic_routes": _dynamic_traffic_routes,
        "obstacles_lock": _obstacles_lock,
        "obstacles": _obstacles,
        "metrics": _metrics,
        "api_logs": _api_logs,
        "api_logs_lock": _api_logs_lock,
        "get_ox": _get_ox,
    },
)


@app.route("/api/astep")
def astep_demo():
    """Visual A* step-by-step demo for presentation."""
    import heapq

    start_t = time.time()

    try:
        from_lat = validate_coordinate(request.args.get("fromLat", 21.0285), "fromLat")
        from_lon = validate_coordinate(request.args.get("fromLon", 105.8542), "fromLon")
        to_lat = validate_coordinate(request.args.get("toLat", 21.0355), "toLat")
        to_lon = validate_coordinate(request.args.get("toLon", 105.8516), "toLon")
        validate_lat_lon(from_lat, from_lon)
        validate_lat_lon(to_lat, to_lon)
    except ValueError:
        return jsonify({"error": "Invalid coords"}), 400

    graph, _, _ = get_road_graph()
    start_node = nearest_node_id(graph, from_lat, from_lon, _ox)
    end_node = nearest_node_id(graph, to_lat, to_lon, _ox)

    # A* with step tracking
    open_set = [(0, start_node)]
    came_from = {}
    g_score = {start_node: 0}
    h_score = {
        start_node: haversine_distance(
            graph.nodes[start_node]["y"], graph.nodes[start_node]["x"], to_lat, to_lon
        )
    }
    f_score = {start_node: h_score[start_node]}
    closed_set = set()
    steps = []
    explored_nodes = []
    max_steps = 30  # Limit for visualization

    step_count = 0
    while open_set and step_count < max_steps:
        step_count += 1
        current_f, current = heapq.heappop(open_set)

        if current == end_node:
            # Reconstruct path
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()

            path_coords = [
                {"lat": graph.nodes[n]["y"], "lon": graph.nodes[n]["x"]} for n in path
            ]

            return jsonify(
                {
                    "success": True,
                    "path": path_coords,
                    "pathLength": len(path),
                    "steps": steps,
                    "exploredPath": [
                        {"lat": graph.nodes[node]["y"], "lon": graph.nodes[node]["x"]}
                        for node in explored_nodes
                    ],
                    "totalSteps": step_count,
                    "calcTime": round((time.time() - start_t) * 1000, 2),
                    "startNode": start_node,
                    "endNode": end_node,
                    "openSetSize": len(open_set),
                    "closedSetSize": len(closed_set),
                }
            )

        if current in closed_set:
            continue
        closed_set.add(current)
        explored_nodes.append(current)

        # Record step
        current_lat = graph.nodes[current]["y"]
        current_lon = graph.nodes[current]["x"]
        h_current = haversine_distance(current_lat, current_lon, to_lat, to_lon)

        steps.append(
            {
                "step": step_count,
                "currentNode": current,
                "currentCoords": {
                    "lat": round(current_lat, 5),
                    "lon": round(current_lon, 5),
                },
                "g": round(g_score.get(current, 0), 1),
                "h": round(h_current, 1),
                "f": round(f_score.get(current, 0), 1),
                "openSetSize": len(open_set),
                "closedSetSize": len(closed_set),
                "formula": f"f(n) = {g_score.get(current, 0):.0f} + {h_current:.0f} = {f_score.get(current, 0):.0f}",
            }
        )

        for neighbor in graph.neighbors(current):
            if neighbor in closed_set:
                continue

            edge_data = graph[current][neighbor]
            edge_length = min(d.get("length", 10) for d in edge_data.values())

            # Apply penalties
            mid_lat = (graph.nodes[current]["y"] + graph.nodes[neighbor]["y"]) / 2
            mid_lon = (graph.nodes[current]["x"] + graph.nodes[neighbor]["x"]) / 2
            traffic_pen = traffic_penalty_for_point(mid_lat, mid_lon)
            rain_pen = rain_penalty_for_point(mid_lat, mid_lon)
            obs_pen = obstacle_penalty_for_point(mid_lat, mid_lon)
            total_weight = edge_length * traffic_pen * rain_pen * obs_pen

            tentative_g = g_score[current] + total_weight

            if tentative_g < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                h_neighbor = haversine_distance(
                    graph.nodes[neighbor]["y"],
                    graph.nodes[neighbor]["x"],
                    to_lat,
                    to_lon,
                )
                h_score[neighbor] = h_neighbor
                f_score[neighbor] = tentative_g + h_neighbor
                heapq.heappush(open_set, (f_score[neighbor], neighbor))

    return jsonify(
        {
            "success": False,
            "steps": steps,
            "exploredPath": [
                {"lat": graph.nodes[node]["y"], "lon": graph.nodes[node]["x"]}
                for node in explored_nodes
            ],
            "totalSteps": step_count,
            "calcTime": round((time.time() - start_t) * 1000, 2),
        }
    )


@app.route("/api/insider")
def insider_comparison():
    """Compare A*, Dijkstra, Greedy Best-First, and BFS."""
    import heapq
    import time as py_time

    try:
        from_lat = validate_coordinate(request.args.get("fromLat", 21.0285), "fromLat")
        from_lon = validate_coordinate(request.args.get("fromLon", 105.8542), "fromLon")
        to_lat = validate_coordinate(request.args.get("toLat", 21.0355), "toLat")
        to_lon = validate_coordinate(request.args.get("toLon", 105.8516), "toLon")
        validate_lat_lon(from_lat, from_lon)
        validate_lat_lon(to_lat, to_lon)
    except ValueError:
        return jsonify({"error": "Invalid coords"}), 400

    graph, _, _ = get_road_graph()
    start_node = nearest_node_id(graph, from_lat, from_lon, _ox)
    end_node = nearest_node_id(graph, to_lat, to_lon, _ox)

    def run_astar():
        """A* with penalties."""
        t0 = py_time.time()
        open_set = [(0, start_node)]
        came_from = {}
        g_score = {start_node: 0}
        h_val = {
            start_node: haversine_distance(
                graph.nodes[start_node]["y"],
                graph.nodes[start_node]["x"],
                to_lat,
                to_lon,
            )
        }
        f_score = {start_node: h_val[start_node]}
        closed = set()
        nodes_explored = 0

        while open_set:
            _, current = heapq.heappop(open_set)
            if current == end_node:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start_node)
                path.reverse()
                return {
                    "path_length": len(path),
                    "nodes_explored": nodes_explored,
                    "time_ms": round((py_time.time() - t0) * 1000, 2),
                    "optimal": True,
                }
            if current in closed:
                continue
            closed.add(current)
            nodes_explored += 1

            for neighbor in graph.neighbors(current):
                if neighbor in closed:
                    continue
                edge_data = graph[current][neighbor]
                edge_len = min(d.get("length", 10) for d in edge_data.values())
                mid_lat = (graph.nodes[current]["y"] + graph.nodes[neighbor]["y"]) / 2
                mid_lon = (graph.nodes[current]["x"] + graph.nodes[neighbor]["x"]) / 2
                w = (
                    edge_len
                    * traffic_penalty_for_point(mid_lat, mid_lon)
                    * rain_penalty_for_point(mid_lat, mid_lon)
                    * obstacle_penalty_for_point(mid_lat, mid_lon)
                )
                tg = g_score[current] + w
                if tg < g_score.get(neighbor, float("inf")):
                    came_from[neighbor] = current
                    g_score[neighbor] = tg
                    h = haversine_distance(
                        graph.nodes[neighbor]["y"],
                        graph.nodes[neighbor]["x"],
                        to_lat,
                        to_lon,
                    )
                    f = tg + h
                    f_score[neighbor] = f
                    heapq.heappush(open_set, (f, neighbor))
        return {
            "path_length": 0,
            "nodes_explored": nodes_explored,
            "time_ms": round((py_time.time() - t0) * 1000, 2),
            "optimal": False,
        }

    def run_dijkstra():
        """Dijkstra (uninformed)."""
        t0 = py_time.time()
        open_set = [(0, start_node)]
        dist = {start_node: 0}
        came_from = {}
        visited = set()
        nodes_explored = 0

        while open_set:
            d, current = heapq.heappop(open_set)
            if current == end_node:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start_node)
                path.reverse()
                return {
                    "path_length": len(path),
                    "nodes_explored": nodes_explored,
                    "time_ms": round((py_time.time() - t0) * 1000, 2),
                    "optimal": True,
                }
            if current in visited:
                continue
            visited.add(current)
            nodes_explored += 1

            for neighbor in graph.neighbors(current):
                if neighbor in visited:
                    continue
                edge_data = graph[current][neighbor]
                w = min(d.get("length", 10) for d in edge_data.values())
                nd = dist[current] + w
                if nd < dist.get(neighbor, float("inf")):
                    dist[neighbor] = nd
                    came_from[neighbor] = current
                    heapq.heappush(open_set, (nd, neighbor))
        return {
            "path_length": 0,
            "nodes_explored": nodes_explored,
            "time_ms": round((py_time.time() - t0) * 1000, 2),
            "optimal": False,
        }

    def run_greedy():
        """Greedy Best-First (only heuristic)."""
        t0 = py_time.time()
        h_start = haversine_distance(
            graph.nodes[start_node]["y"], graph.nodes[start_node]["x"], to_lat, to_lon
        )
        open_set = [(h_start, start_node)]
        came_from = {}
        visited = set()
        nodes_explored = 0

        while open_set:
            _, current = heapq.heappop(open_set)
            if current == end_node:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start_node)
                path.reverse()
                return {
                    "path_length": len(path),
                    "nodes_explored": nodes_explored,
                    "time_ms": round((py_time.time() - t0) * 1000, 2),
                    "optimal": False,
                }
            if current in visited:
                continue
            visited.add(current)
            nodes_explored += 1

            for neighbor in graph.neighbors(current):
                if neighbor in visited:
                    continue
                h = haversine_distance(
                    graph.nodes[neighbor]["y"],
                    graph.nodes[neighbor]["x"],
                    to_lat,
                    to_lon,
                )
                came_from[neighbor] = current
                heapq.heappush(open_set, (h, neighbor))
        return {
            "path_length": 0,
            "nodes_explored": nodes_explored,
            "time_ms": round((py_time.time() - t0) * 1000, 2),
            "optimal": False,
        }

    def run_bfs():
        """BFS (blind search)."""
        t0 = py_time.time()
        from collections import deque

        queue = deque([start_node])
        came_from = {start_node: None}
        visited = set([start_node])
        nodes_explored = 0

        while queue:
            current = queue.popleft()
            if current == end_node:
                path = []
                while current is not None:
                    path.append(current)
                    current = came_from[current]
                path.reverse()
                return {
                    "path_length": len(path),
                    "nodes_explored": nodes_explored,
                    "time_ms": round((py_time.time() - t0) * 1000, 2),
                    "optimal": True,
                }
            nodes_explored += 1

            for neighbor in graph.neighbors(current):
                if neighbor not in visited:
                    visited.add(neighbor)
                    came_from[neighbor] = current
                    queue.append(neighbor)
        return {
            "path_length": 0,
            "nodes_explored": nodes_explored,
            "time_ms": round((py_time.time() - t0) * 1000, 2),
            "optimal": False,
        }

    # Run all 4
    astar = run_astar()
    dijkstra = run_dijkstra()
    greedy = run_greedy()
    bfs = run_bfs()

    # Find best path length for optimality check
    best_path = min(
        p["path_length"] for p in [astar, dijkstra, greedy, bfs] if p["path_length"] > 0
    )

    return jsonify(
        {
            "algorithms": {
                "A*": astar,
                "Dijkstra": dijkstra,
                "Greedy Best-First": greedy,
                "BFS": bfs,
            },
            "best_path_length": best_path,
            "from": {"lat": from_lat, "lon": from_lon},
            "to": {"lat": to_lat, "lon": to_lon},
        }
    )


@app.route("/api/classical/compare")
def classical_compare():
    try:
        from_lat = validate_coordinate(request.args.get("fromLat", 21.0285), "fromLat")
        from_lon = validate_coordinate(request.args.get("fromLon", 105.8542), "fromLon")
        to_lat = validate_coordinate(request.args.get("toLat", 21.0355), "toLat")
        to_lon = validate_coordinate(request.args.get("toLon", 105.8516), "toLon")
        validate_lat_lon(from_lat, from_lon)
        validate_lat_lon(to_lat, to_lon)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    graph, _, _ = get_road_graph()
    start_node = nearest_node_id(graph, from_lat, from_lon, _ox)
    end_node = nearest_node_id(graph, to_lat, to_lon, _ox)
    payload = compare_classical_algorithms(graph, start_node, end_node, to_lat, to_lon)
    payload["from"] = {"lat": from_lat, "lon": from_lon, "nodeId": start_node}
    payload["to"] = {"lat": to_lat, "lon": to_lon, "nodeId": end_node}
    payload["note"] = (
        "Classical AI compare uses base edge length only (no rain/traffic/obstacle penalties)."
    )
    return jsonify(payload)
