from flask import jsonify, render_template, request

from ..algorithms import (
    compare_classical_algorithms,
    run_astep_demo,
    run_insider_comparison,
)
from ..core.data import CHARGING_STATIONS, INITIAL_ROBOTS, LOCATIONS
from ..core.hubs import compute_optimized_hubs
from ..config import (
    CLASSICAL_COMPARE_NOTE,
    DEFAULT_DEMO_FROM_LAT,
    DEFAULT_DEMO_FROM_LON,
    DEFAULT_DEMO_TO_LAT,
    DEFAULT_DEMO_TO_LON,
    DEFAULT_HUB_CLUSTER_COUNT,
    INVALID_COORDS_ERROR,
)


def register_main_routes(app, ctx):
    get_road_graph = ctx["get_road_graph"]
    validate_coordinate = ctx["validate_coordinate"]
    validate_lat_lon = ctx["validate_lat_lon"]
    nearest_node_id = ctx["nearest_node_id"]
    traffic_penalty_for_point = ctx["traffic_penalty_for_point"]
    rain_penalty_for_point = ctx["rain_penalty_for_point"]
    obstacle_penalty_for_point = ctx["obstacle_penalty_for_point"]
    app_state = ctx["app_state"]

    @app.route("/api/data/locations")
    def get_locations():
        return jsonify({"locations": LOCATIONS})

    @app.route("/api/data/hubs")
    def get_hubs():
        return jsonify({"hubs": CHARGING_STATIONS})

    @app.route("/api/data/robots")
    def get_robots():
        return jsonify({"robots": INITIAL_ROBOTS})

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/optimize-hubs", methods=["POST"])
    def optimize_hubs():
        try:
            hubs = compute_optimized_hubs(
                app_state, cluster_count=DEFAULT_HUB_CLUSTER_COUNT
            )
            return jsonify({"hubs": hubs}), 200
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/astep")
    def astep_demo():
        try:
            from_lat = validate_coordinate(
                request.args.get("fromLat", DEFAULT_DEMO_FROM_LAT), "fromLat"
            )
            from_lon = validate_coordinate(
                request.args.get("fromLon", DEFAULT_DEMO_FROM_LON), "fromLon"
            )
            to_lat = validate_coordinate(
                request.args.get("toLat", DEFAULT_DEMO_TO_LAT), "toLat"
            )
            to_lon = validate_coordinate(
                request.args.get("toLon", DEFAULT_DEMO_TO_LON), "toLon"
            )
            validate_lat_lon(from_lat, from_lon)
            validate_lat_lon(to_lat, to_lon)
        except ValueError:
            return jsonify({"error": INVALID_COORDS_ERROR}), 400

        graph, _, _ = get_road_graph()
        start_node = nearest_node_id(graph, from_lat, from_lon, app_state["ox"])
        end_node = nearest_node_id(graph, to_lat, to_lon, app_state["ox"])
        payload = run_astep_demo(
            graph,
            start_node,
            end_node,
            to_lat,
            to_lon,
            traffic_penalty_for_point,
            rain_penalty_for_point,
            obstacle_penalty_for_point,
        )
        return jsonify(payload)

    @app.route("/api/insider")
    def insider_comparison():
        try:
            from_lat = validate_coordinate(
                request.args.get("fromLat", DEFAULT_DEMO_FROM_LAT), "fromLat"
            )
            from_lon = validate_coordinate(
                request.args.get("fromLon", DEFAULT_DEMO_FROM_LON), "fromLon"
            )
            to_lat = validate_coordinate(
                request.args.get("toLat", DEFAULT_DEMO_TO_LAT), "toLat"
            )
            to_lon = validate_coordinate(
                request.args.get("toLon", DEFAULT_DEMO_TO_LON), "toLon"
            )
            validate_lat_lon(from_lat, from_lon)
            validate_lat_lon(to_lat, to_lon)
        except ValueError:
            return jsonify({"error": INVALID_COORDS_ERROR}), 400

        graph, _, _ = get_road_graph()
        start_node = nearest_node_id(graph, from_lat, from_lon, app_state["ox"])
        end_node = nearest_node_id(graph, to_lat, to_lon, app_state["ox"])
        payload = run_insider_comparison(
            graph,
            start_node,
            end_node,
            to_lat,
            to_lon,
            traffic_penalty_for_point,
            rain_penalty_for_point,
            obstacle_penalty_for_point,
        )
        payload["from"] = {"lat": from_lat, "lon": from_lon}
        payload["to"] = {"lat": to_lat, "lon": to_lon}
        return jsonify(payload)

    @app.route("/api/classical/compare")
    def classical_compare():
        try:
            from_lat = validate_coordinate(
                request.args.get("fromLat", DEFAULT_DEMO_FROM_LAT), "fromLat"
            )
            from_lon = validate_coordinate(
                request.args.get("fromLon", DEFAULT_DEMO_FROM_LON), "fromLon"
            )
            to_lat = validate_coordinate(
                request.args.get("toLat", DEFAULT_DEMO_TO_LAT), "toLat"
            )
            to_lon = validate_coordinate(
                request.args.get("toLon", DEFAULT_DEMO_TO_LON), "toLon"
            )
            validate_lat_lon(from_lat, from_lon)
            validate_lat_lon(to_lat, to_lon)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        graph, _, _ = get_road_graph()
        start_node = nearest_node_id(graph, from_lat, from_lon, app_state["ox"])
        end_node = nearest_node_id(graph, to_lat, to_lon, app_state["ox"])
        payload = compare_classical_algorithms(
            graph, start_node, end_node, to_lat, to_lon
        )
        payload["from"] = {"lat": from_lat, "lon": from_lon, "nodeId": start_node}
        payload["to"] = {"lat": to_lat, "lon": to_lon, "nodeId": end_node}
        payload["note"] = CLASSICAL_COMPARE_NOTE
        return jsonify(payload)
