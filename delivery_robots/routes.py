import json
import random
import time
import networkx as nx
from flask import Blueprint, jsonify, render_template, request

from .utils.geo_utils import haversine_distance
from .utils.metrics_utils import build_metrics_payload, record_route_metrics
from .core.route_analysis import build_route_response, nearest_node_id
from .utils.validation import (
    validate_coordinate,
    validate_lat_lon,
    validate_non_negative_int,
    validate_positive_number,
)
from .algorithms import run_astar, run_dijkstra, run_greedy, run_bfs

from . import map_manager, env_manager, _metrics

api_bp = Blueprint('api', __name__)

def get_road_graph():
    """Proxy function to MapManager for backward compatibility."""
    return map_manager.get_road_graph()

@api_bp.route("/")
def index():
    return render_template("index.html")

@api_bp.route("/api/health")
def health():
    return jsonify({"status": "ok"})

@api_bp.route("/api/traffic")
def traffic():
    now = time.time()
    roads = []
    
    graph, _ = map_manager.get_road_graph()
    
    if env_manager._traffic_routes is None:
        env_manager.initialize_traffic_routes()
        
    all_routes = list(env_manager._traffic_routes or [])
    with env_manager._dynamic_traffic_lock:
        all_routes.extend(env_manager._dynamic_traffic_routes)

    for road in all_routes:
        if len(road["path"]) < 2:
            roads.append({"name": road["name"], "segments": []})
            continue

        progress = (now / env_manager.TRAFFIC_PERIOD_SECONDS + road["severity"]) % 1
        active_segment = progress * (len(road["path"]) - 1)
        segments = []

        for idx in range(len(road["path"]) - 1):
            strength = max(0.0, 1 - abs(idx - active_segment))
            if strength < 0.15:
                continue

            segments.append(
                {
                    "points": [
                        [road["path"][idx]["lat"], road["path"][idx]["lon"]],
                        [road["path"][idx + 1]["lat"], road["path"][idx + 1]["lon"]],
                    ],
                    "severity": round(road["severity"] * strength, 3),
                }
            )

        roads.append({"name": road["name"], "segments": segments})

    return jsonify({"roads": roads, "updatedAt": now})

@api_bp.route("/api/weather")
def weather():
    return jsonify({
        "rainZones": [
            {
                "name": zone["name"],
                "center": {"lat": zone["center"][0], "lon": zone["center"][1]},
                "radius": zone["radius"],
                "multiplier": round(1 + zone.get("severity", 1.0), 2),
            }
            for zone in env_manager.rain_zones
        ]
    })

@api_bp.route("/api/clock")
def get_clock():
    hours, minutes, seconds = env_manager.get_simulation_time()
    rush_multiplier, rush_name = env_manager.get_rush_hour_multiplier()
    is_rush_hour = rush_name != "Normal"
    return jsonify({
        "time": {
            "hours": hours,
            "minutes": minutes,
            "seconds": seconds,
            "display": f"{hours:02d}:{minutes:02d}:{seconds:02d}",
        },
        "rushHour": {
            "isActive": is_rush_hour,
            "name": rush_name,
            "multiplier": round(rush_multiplier, 2),
            "schedule": env_manager.RUSH_HOURS,
        },
        "simulationSpeed": env_manager._simulation_speed,
    })

@api_bp.route("/api/route", methods=["GET", "POST"])
def route():
    start_t = time.time()
    
    req_data = request.get_json(silent=True) or {} if request.method == "POST" else {}
    
    def get_param(key, default=None):
        return req_data.get(key) if key in req_data else request.args.get(key, default)

    try:
        from_lat = validate_coordinate(get_param("fromLat"), "fromLat")
        from_lon = validate_coordinate(get_param("fromLon"), "fromLon")
        to_lat = validate_coordinate(get_param("toLat"), "toLat")
        to_lon = validate_coordinate(get_param("toLon"), "toLon")
        validate_lat_lon(from_lat, from_lon)
        validate_lat_lon(to_lat, to_lon)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if from_lat == to_lat and from_lon == to_lon:
        return jsonify({"path": [{"lat": from_lat, "lon": from_lon}], "distance": 0})

    try:
        if request.method == "POST" and "memory" in req_data:
            road_memory = req_data["memory"]
            if isinstance(road_memory, str):
                road_memory = json.loads(road_memory)
        else:
            road_memory = json.loads(request.args.get("memory", "{}"))
    except Exception:
        road_memory = {}

    try:
        graph, _ = map_manager.get_road_graph()
        start_node = nearest_node_id(graph, from_lat, from_lon, map_manager._ox)
        end_node = nearest_node_id(graph, to_lat, to_lon, map_manager._ox)

        def edge_weight_with_memory(from_node, to_node, edge_data):
            base = env_manager.edge_weight_with_traffic(from_node, to_node, edge_data, graph)
            fn = graph.nodes[from_node]
            tn = graph.nodes[to_node]
            key = f"{fn['y']:.4f},{fn['x']:.4f}->{tn['y']:.4f},{tn['x']:.4f}"
            memory_penalty = road_memory.get(key, 1.0)
            return base * memory_penalty

        weight_fn = edge_weight_with_memory if road_memory else lambda u, v, d: env_manager.edge_weight_with_traffic(u, v, d, graph)
        route_nodes = nx.shortest_path(graph, start_node, end_node, weight=weight_fn)
        payload = build_route_response(
            graph,
            route_nodes,
            env_manager.traffic_penalty_for_point,
            env_manager.rain_penalty_for_point,
            env_manager.obstacle_penalty_for_point,
        )
        payload["start"] = {
            "lat": graph.nodes[start_node]["y"],
            "lon": graph.nodes[start_node]["x"],
        }
        payload["end"] = {
            "lat": graph.nodes[end_node]["y"],
            "lon": graph.nodes[end_node]["x"],
        }

        calc_time = (time.time() - start_t) * 1000
        nodes_explored = len(route_nodes) * 5
        record_route_metrics(_metrics, calc_time, nodes_explored, len(route_nodes))

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

@api_bp.route("/api/snap")
def snap():
    try:
        lat = validate_coordinate(request.args.get("lat"), "lat")
        lon = validate_coordinate(request.args.get("lon"), "lon")
        validate_lat_lon(lat, lon)
        graph, _ = map_manager.get_road_graph()
        node_id = nearest_node_id(graph, lat, lon, map_manager._ox)
        return jsonify({
            "lat": graph.nodes[node_id]["y"],
            "lon": graph.nodes[node_id]["x"],
        })
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

@api_bp.route("/api/rain/list")
def list_rain():
    return jsonify({
        "rainZones": [
            {
                "name": z["name"],
                "center": {"lat": z["center"][0], "lon": z["center"][1]},
                "radius": z["radius"],
            }
            for z in env_manager.rain_zones
        ]
    })

@api_bp.route("/api/rain/add", methods=["POST"])
def add_rain():
    d = request.get_json(silent=True) or {}
    try:
        lat = validate_coordinate(d.get("lat"), "lat")
        lon = validate_coordinate(d.get("lon"), "lon")
        radius = validate_positive_number(d.get("radius", 150), "radius")
        validate_lat_lon(lat, lon)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    env_manager.rain_zones.append({
        "name": f"Rain {len(env_manager.rain_zones) + 1}",
        "center": (lat, lon),
        "radius": radius,
        "severity": 1.0,
    })
    return jsonify({
        "message": "Added",
        "rainZone": {
            "name": f"Rain {len(env_manager.rain_zones)}",
            "center": {"lat": lat, "lon": lon},
            "radius": radius,
        },
    })

@api_bp.route("/api/rain/randomize", methods=["POST"])
def randomize_rain():
    d = request.get_json(silent=True) or {}
    try:
        count = validate_non_negative_int(d.get("count", 3), "count")
        min_radius = validate_positive_number(d.get("minRadius", 100), "minRadius")
        max_radius = validate_positive_number(d.get("maxRadius", 200), "maxRadius")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if min_radius > max_radius:
        return jsonify({"error": "minRadius must be less than or equal to maxRadius"}), 400

    env_manager.rain_zones = [
        {
            "name": f"Rain {i + 1}",
            "center": (
                random.uniform(21.0180, 21.0380),
                random.uniform(105.8430, 105.8650),
            ),
            "radius": random.uniform(min_radius, max_radius),
            "severity": 1.0,
        }
        for i in range(count)
    ]
    return jsonify({
        "message": f"Added {count}",
        "rainZones": [
            {
                "name": z["name"],
                "center": {"lat": z["center"][0], "lon": z["center"][1]},
                "radius": z["radius"],
            }
            for z in env_manager.rain_zones
        ],
    })

@api_bp.route("/api/rain/clear", methods=["POST"])
def clear_rain():
    env_manager.rain_zones = []
    return jsonify({"message": "Cleared"})

@api_bp.route("/api/traffic/list")
def list_traffic_routes():
    with env_manager._dynamic_traffic_lock:
        return jsonify({"routes": env_manager._dynamic_traffic_routes[:]})

@api_bp.route("/api/traffic/add", methods=["POST"])
def add_traffic_route():
    d = request.get_json(silent=True) or {}
    try:
        start_lat = validate_coordinate(d.get("startLat"), "startLat")
        start_lon = validate_coordinate(d.get("startLon"), "startLon")
        end_lat = validate_coordinate(d.get("endLat"), "endLat")
        end_lon = validate_coordinate(d.get("endLon"), "endLon")
        validate_lat_lon(start_lat, start_lon)
        validate_lat_lon(end_lat, end_lon)
        severity = float(d.get("severity", 0.7))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if start_lat == end_lat and start_lon == end_lon:
        return jsonify({"error": "Traffic start and end must be different"}), 400

    severity = max(0.0, min(1.0, severity))
    graph, _ = map_manager.get_road_graph()
    start_node = nearest_node_id(graph, start_lat, start_lon, map_manager._ox)
    end_node = nearest_node_id(graph, end_lat, end_lon, map_manager._ox)
    route_nodes = nx.shortest_path(graph, start_node, end_node, weight="length")
    route_payload = build_route_response(
        graph,
        route_nodes,
        env_manager.traffic_penalty_for_point,
        env_manager.rain_penalty_for_point,
        env_manager.obstacle_penalty_for_point,
        include_cost_breakdown=False,
    )

    with env_manager._dynamic_traffic_lock:
        route_name = d.get("name") or f"Traffic {len(env_manager._dynamic_traffic_routes) + 1}"
        route = {
            "name": route_name,
            "severity": severity,
            "path": route_payload["path"],
        }
        env_manager._dynamic_traffic_routes.append(route)

    return jsonify({"message": "Added", "route": route, "routes": env_manager._dynamic_traffic_routes[:]})

@api_bp.route("/api/traffic/randomize", methods=["POST"])
def randomize_traffic():
    d = request.get_json(silent=True) or {}
    try:
        count = validate_non_negative_int(d.get("count", 3), "count")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    routes = []
    for i in range(count):
        routes.append({
            "name": f"Traffic {i + 1}",
            "severity": random.uniform(0.4, 0.9),
            "path": [
                {
                    "lat": random.uniform(21.0200, 21.0350),
                    "lon": random.uniform(105.8450, 105.8600),
                }
                for _ in range(10)
            ],
        })
    with env_manager._dynamic_traffic_lock:
        env_manager._dynamic_traffic_routes = routes
    return jsonify({"message": f"Added {count}", "routes": routes})

@api_bp.route("/api/traffic/clear", methods=["POST"])
def clear_traffic():
    with env_manager._dynamic_traffic_lock:
        env_manager._dynamic_traffic_routes = []
    return jsonify({"message": "Cleared"})

@api_bp.route("/api/obstacle/list")
def list_obstacles():
    with env_manager._obstacles_lock:
        return jsonify({
            "obstacles": [
                {
                    "name": o["name"],
                    "center": {"lat": o["center"][0], "lon": o["center"][1]},
                    "radius": o["radius"],
                    "severity": o["severity"],
                    "type": o["type"],
                }
                for o in env_manager._obstacles
            ]
        })

@api_bp.route("/api/obstacle/add", methods=["POST"])
def add_obstacle():
    d = request.get_json(silent=True) or {}
    try:
        lat = validate_coordinate(d.get("lat"), "lat")
        lon = validate_coordinate(d.get("lon"), "lon")
        radius = validate_positive_number(d.get("radius", 80), "radius")
        severity = validate_positive_number(d.get("severity", 10), "severity")
        validate_lat_lon(lat, lon)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    o = {
        "name": f"Obstacle {len(env_manager._obstacles) + 1}",
        "center": (lat, lon),
        "radius": radius,
        "severity": severity,
        "type": d.get("type", "roadblock"),
    }
    with env_manager._obstacles_lock:
        env_manager._obstacles.append(o)
    return jsonify({
        "message": "Added",
        "obstacle": {
            "name": o["name"],
            "center": {"lat": lat, "lon": lon},
            "radius": o["radius"],
            "severity": o["severity"],
            "type": o["type"],
        },
    })

@api_bp.route("/api/obstacle/randomize", methods=["POST"])
def randomize_obstacles():
    d = request.get_json(silent=True) or {}
    try:
        count = validate_non_negative_int(d.get("count", 3), "count")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    types = ["roadblock", "construction", "accident"]
    with env_manager._obstacles_lock:
        env_manager._obstacles = [
            {
                "name": f"Obs {i + 1}",
                "center": (
                    random.uniform(21.0180, 21.0380),
                    random.uniform(105.8430, 105.8650),
                ),
                "radius": random.uniform(50, 120),
                "severity": random.uniform(5, 50),
                "type": random.choice(types),
            }
            for i in range(count)
        ]
    return jsonify({
        "message": f"Added {count}",
        "obstacles": [
            {
                "name": o["name"],
                "center": {"lat": o["center"][0], "lon": o["center"][1]},
                "radius": o["radius"],
                "severity": o["severity"],
                "type": o["type"],
            }
            for o in env_manager._obstacles
        ],
    })

@api_bp.route("/api/obstacle/clear", methods=["POST"])
def clear_obstacles():
    with env_manager._obstacles_lock:
        env_manager._obstacles = []
    return jsonify({"message": "Cleared"})

@api_bp.route("/api/metrics")
def get_metrics():
    return jsonify(
        build_metrics_payload(
            _metrics,
            map_manager._road_graph,
            len(env_manager.rain_zones),
            len(env_manager._dynamic_traffic_routes),
            len(env_manager._obstacles),
        )
    )

@api_bp.route("/api/astep")
def astep_demo():
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

    graph, _ = map_manager.get_road_graph()
    start_node = nearest_node_id(graph, from_lat, from_lon, map_manager._ox)
    end_node = nearest_node_id(graph, to_lat, to_lon, map_manager._ox)

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
    max_steps = 30

    step_count = 0
    while open_set and step_count < max_steps:
        step_count += 1
        current_f, current = heapq.heappop(open_set)

        if current == end_node:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            path_coords = [{"lat": graph.nodes[n]["y"], "lon": graph.nodes[n]["x"]} for n in path]
            return jsonify({
                "success": True,
                "path": path_coords,
                "pathLength": len(path),
                "steps": steps,
                "exploredPath": [{"lat": graph.nodes[node]["y"], "lon": graph.nodes[node]["x"]} for node in explored_nodes],
                "totalSteps": step_count,
                "calcTime": round((time.time() - start_t) * 1000, 2),
                "startNode": start_node,
                "endNode": end_node,
                "openSetSize": len(open_set),
                "closedSetSize": len(closed_set),
            })

        if current in closed_set:
            continue
        closed_set.add(current)
        explored_nodes.append(current)

        current_lat = graph.nodes[current]["y"]
        current_lon = graph.nodes[current]["x"]
        h_current = haversine_distance(current_lat, current_lon, to_lat, to_lon)

        steps.append({
            "step": step_count,
            "currentNode": current,
            "currentCoords": {"lat": round(current_lat, 5), "lon": round(current_lon, 5)},
            "g": round(g_score.get(current, 0), 1),
            "h": round(h_current, 1),
            "f": round(f_score.get(current, 0), 1),
            "openSetSize": len(open_set),
            "closedSetSize": len(closed_set),
            "formula": f"f(n) = {g_score.get(current, 0):.0f} + {h_current:.0f} = {f_score.get(current, 0):.0f}",
        })

        for neighbor in graph.neighbors(current):
            if neighbor in closed_set:
                continue
            edge_data = graph[current][neighbor]
            total_weight = env_manager.edge_weight_with_traffic(current, neighbor, edge_data, graph)
            tentative_g = g_score[current] + total_weight
            if tentative_g < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                h_neighbor = haversine_distance(
                    graph.nodes[neighbor]["y"], graph.nodes[neighbor]["x"], to_lat, to_lon
                )
                h_score[neighbor] = h_neighbor
                f_score[neighbor] = tentative_g + h_neighbor
                heapq.heappush(open_set, (f_score[neighbor], neighbor))

    return jsonify({
        "success": False,
        "steps": steps,
        "exploredPath": [{"lat": graph.nodes[node]["y"], "lon": graph.nodes[node]["x"]} for node in explored_nodes],
        "totalSteps": step_count,
        "calcTime": round((time.time() - start_t) * 1000, 2),
    })

@api_bp.route("/api/insider")
def insider_comparison():
    try:
        from_lat = validate_coordinate(request.args.get("fromLat", 21.0285), "fromLat")
        from_lon = validate_coordinate(request.args.get("fromLon", 105.8542), "fromLon")
        to_lat = validate_coordinate(request.args.get("toLat", 21.0355), "toLat")
        to_lon = validate_coordinate(request.args.get("toLon", 105.8516), "toLon")
        validate_lat_lon(from_lat, from_lon)
        validate_lat_lon(to_lat, to_lon)
    except ValueError:
        return jsonify({"error": "Invalid coords"}), 400

    graph, _ = map_manager.get_road_graph()
    start_node = nearest_node_id(graph, from_lat, from_lon, map_manager._ox)
    end_node = nearest_node_id(graph, to_lat, to_lon, map_manager._ox)

    astar = run_astar(graph, start_node, end_node, to_lat, to_lon, env_manager)
    dijkstra = run_dijkstra(graph, start_node, end_node)
    greedy = run_greedy(graph, start_node, end_node, to_lat, to_lon)
    bfs = run_bfs(graph, start_node, end_node)

    best_path = min(
        p["path_length"] for p in [astar, dijkstra, greedy, bfs] if p["path_length"] > 0
    )

    for p in [astar, dijkstra, greedy, bfs]:
        p.pop("path", None)

    return jsonify({
        "algorithms": {
            "A*": astar,
            "Dijkstra": dijkstra,
            "Greedy Best-First": greedy,
            "BFS": bfs,
        },
        "best_path_length": best_path,
        "from": {"lat": from_lat, "lon": from_lon},
        "to": {"lat": to_lat, "lon": to_lon},
    })
