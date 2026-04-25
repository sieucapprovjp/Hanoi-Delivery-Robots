import json
import time
import networkx as nx
from flask import Blueprint, jsonify, request
from .. import map_manager, env_manager, _metrics
from ..utils.geo_utils import haversine_distance
from ..utils.metrics_utils import record_route_metrics
from ..core.route_analysis import build_route_response, nearest_node_id
from ..utils.validation import validate_coordinate, validate_lat_lon

routing_bp = Blueprint('routing', __name__)

@routing_bp.route("", methods=["GET", "POST"])
def route():
    """Calculate the shortest path considering active penalties and memory."""
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

@routing_bp.route("/snap", methods=["GET"])
def snap():
    """Snap coordinates to the nearest road node."""
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
