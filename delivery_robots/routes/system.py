from flask import Blueprint, jsonify, request
from .. import env_manager, map_manager
from ..utils.validation import validate_coordinate, validate_lat_lon
from ..core.route_analysis import nearest_node_id
from ..algorithms import run_astar, run_dijkstra, run_greedy, run_bfs

system_bp = Blueprint('system', __name__)

@system_bp.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})

@system_bp.route("/clock")
def get_clock():
    """Get the current simulation time and rush hour status."""
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

@system_bp.route("/insider")
def insider_comparison():
    """Compare multiple pathfinding algorithms for internal usage."""
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
