import random
import time
import networkx as nx
from flask import Blueprint, jsonify, request
from .. import env_manager, map_manager
from ..utils.validation import validate_coordinate, validate_lat_lon, validate_non_negative_int
from ..core.route_analysis import nearest_node_id, build_route_response

traffic_bp = Blueprint('traffic', __name__)

@traffic_bp.route("/active", methods=["GET"])
def get_traffic():
    """Get active traffic status on the map for animation."""
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

@traffic_bp.route("", methods=["GET"])
def list_traffic_routes():
    """List all dynamically added traffic routes."""
    with env_manager._dynamic_traffic_lock:
        return jsonify({"routes": env_manager._dynamic_traffic_routes[:]})

@traffic_bp.route("", methods=["POST"])
def add_traffic_route():
    """Add a new dynamic traffic route."""
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

@traffic_bp.route("/randomize", methods=["POST"])
def randomize_traffic():
    """Generate random traffic routes."""
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

@traffic_bp.route("", methods=["DELETE"])
def clear_traffic():
    """Clear all dynamic traffic routes."""
    with env_manager._dynamic_traffic_lock:
        env_manager._dynamic_traffic_routes = []
    return jsonify({"message": "Cleared"})
