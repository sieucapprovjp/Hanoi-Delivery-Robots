import time
import heapq
from flask import Blueprint, jsonify, request
from .. import map_manager, env_manager
from ..utils.geo_utils import haversine_distance
from ..utils.validation import validate_coordinate, validate_lat_lon
from ..core.route_analysis import nearest_node_id

algorithms_bp = Blueprint('algorithms', __name__)

@algorithms_bp.route("/astep", methods=["GET"])
def astep_demo():
    """A* Step-by-step algorithm demonstration endpoint."""
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
