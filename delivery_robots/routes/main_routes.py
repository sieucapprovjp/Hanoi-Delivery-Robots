import json
import time

import networkx as nx
from flask import jsonify, render_template, request

from ..algorithms import (
    compare_classical_algorithms,
    run_astep_demo,
    run_insider_comparison,
    run_weighted_route_search,
)
from ..algorithms.dispatch.allocation import assign_deliveries
from ..core.environment import (
    edge_weight_for_snapshot,
    obstacle_penalty_for_snapshot,
    rain_penalty_for_snapshot,
    traffic_penalty_for_snapshot,
)
from ..core.hubs import append_delivery_points, compute_optimized_hubs, snap_hubs_to_graph
from ..utils.geo import haversine_distance
from ..utils.persistent_log import append_delivery_history
from ..utils.route_analysis import attach_route_metadata, build_memory_weight_fn
from ..config import (
    CLASSICAL_COMPARE_NOTE,
    DEFAULT_DEMO_FROM_LAT,
    DEFAULT_DEMO_FROM_LON,
    DEFAULT_DEMO_TO_LAT,
    DEFAULT_DEMO_TO_LON,
    DEFAULT_HUB_CLUSTER_COUNT,
    DEFAULT_ROAD_MEMORY_PENALTY,
    DEFAULT_ROUTING_ALGORITHM,
    INVALID_ALGORITHM_ERROR,
    INVALID_COORDS_ERROR,
    ROUTING_ALGORITHM_ALIASES,
    TIMESTAMP_MS_MULTIPLIER,
    VALID_ROUTING_ALGORITHMS,
)


def register_main_routes(app, ctx):
    get_road_graph = ctx["get_road_graph"]
    validate_coordinate = ctx["validate_coordinate"]
    validate_lat_lon = ctx["validate_lat_lon"]
    nearest_node_id = ctx["nearest_node_id"]
    build_route_response = ctx["build_route_response"]
    record_route_metrics = ctx["record_route_metrics"]
    metrics = ctx["metrics"]
    app_state = ctx["app_state"]
    get_environment_snapshot = ctx["get_environment_snapshot"]

    def snapshot_environment_functions():
        snapshot = get_environment_snapshot()
        return (
            lambda lat, lon: traffic_penalty_for_snapshot(snapshot, lat, lon),
            lambda lat, lon: rain_penalty_for_snapshot(snapshot, lat, lon),
            lambda lat, lon: obstacle_penalty_for_snapshot(snapshot, lat, lon),
            lambda from_node, to_node, edge_data: edge_weight_for_snapshot(
                snapshot, from_node, to_node, edge_data
            ),
        )

    def parse_route_coordinates(defaults=None):
        defaults = defaults or {}
        from_lat = validate_coordinate(
            request.args.get("fromLat", defaults.get("fromLat")), "fromLat"
        )
        from_lon = validate_coordinate(
            request.args.get("fromLon", defaults.get("fromLon")), "fromLon"
        )
        to_lat = validate_coordinate(
            request.args.get("toLat", defaults.get("toLat")), "toLat"
        )
        to_lon = validate_coordinate(
            request.args.get("toLon", defaults.get("toLon")), "toLon"
        )
        validate_lat_lon(from_lat, from_lon)
        validate_lat_lon(to_lat, to_lon)
        return from_lat, from_lon, to_lat, to_lon

    def demo_route_defaults():
        return {
            "fromLat": DEFAULT_DEMO_FROM_LAT,
            "fromLon": DEFAULT_DEMO_FROM_LON,
            "toLat": DEFAULT_DEMO_TO_LAT,
            "toLon": DEFAULT_DEMO_TO_LON,
        }

    def route_graph_context(from_lat, from_lon, to_lat, to_lon):
        graph, _, _ = get_road_graph()
        start_node = nearest_node_id(graph, from_lat, from_lon, app_state["ox"])
        end_node = nearest_node_id(graph, to_lat, to_lon, app_state["ox"])
        return graph, start_node, end_node

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/route")
    def route():
        start_t = time.time()
        try:
            from_lat, from_lon, to_lat, to_lon = parse_route_coordinates()
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        if from_lat == to_lat and from_lon == to_lon:
            return jsonify(
                {"path": [{"lat": from_lat, "lon": from_lon}], "distance": 0}
            )

        try:
            road_memory = json.loads(request.args.get("memory", "{}"))
        except Exception:
            road_memory = {}

        algo = (request.args.get("algo") or DEFAULT_ROUTING_ALGORITHM).strip().lower()
        algo = ROUTING_ALGORITHM_ALIASES.get(algo, algo)
        if algo not in VALID_ROUTING_ALGORITHMS:
            return jsonify({"error": INVALID_ALGORITHM_ERROR}), 400

        try:
            graph, start_node, end_node = route_graph_context(
                from_lat, from_lon, to_lat, to_lon
            )
            (
                traffic_penalty,
                rain_penalty,
                obstacle_penalty,
                edge_weight,
            ) = snapshot_environment_functions()
            weight_fn = build_memory_weight_fn(
                graph, edge_weight, road_memory, DEFAULT_ROAD_MEMORY_PENALTY
            )
            route_nodes, nodes_explored = run_weighted_route_search(
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
                traffic_penalty,
                rain_penalty,
                obstacle_penalty,
            )

            calc_time = (time.time() - start_t) * TIMESTAMP_MS_MULTIPLIER
            record_route_metrics(metrics, calc_time, nodes_explored, len(route_nodes))
            attach_route_metadata(
                payload,
                graph,
                start_node,
                end_node,
                algo,
                calc_time,
                nodes_explored,
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
            graph = get_road_graph()[0]
            node_id = nearest_node_id(graph, lat, lon)
            return jsonify(
                {"lat": graph.nodes[node_id]["y"], "lon": graph.nodes[node_id]["x"]}
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/log_delivery", methods=["POST"])
    def log_delivery():
        try:
            data = request.json
            pickup_lat = validate_coordinate(data.get("pickupLat"), "pickupLat")
            pickup_lon = validate_coordinate(data.get("pickupLon"), "pickupLon")
            dropoff_lat = validate_coordinate(data.get("dropoffLat"), "dropoffLat")
            dropoff_lon = validate_coordinate(data.get("dropoffLon"), "dropoffLon")
            append_delivery_points(
                app_state, pickup_lat, pickup_lon, dropoff_lat, dropoff_lon
            )
            append_delivery_history(
                {
                    "deliveryId": data.get("deliveryId"),
                    "pickup": {
                        "lat": pickup_lat,
                        "lon": pickup_lon,
                        "name": data.get("pickupName"),
                        "category": data.get("pickupCategory"),
                    },
                    "dropoff": {
                        "lat": dropoff_lat,
                        "lon": dropoff_lon,
                        "name": data.get("dropoffName"),
                        "category": data.get("dropoffCategory"),
                    },
                    "createdAt": data.get("createdAt"),
                }
            )
            return jsonify({"status": "success"}), 200
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/dispatch/assign", methods=["POST"])
    def dispatch_assign():
        try:
            data = request.json
            robots = data.get("robots", [])
            deliveries = data.get("deliveries", [])
            current_time_ms = data.get(
                "currentTime", int(time.time() * TIMESTAMP_MS_MULTIPLIER)
            )

            graph, _, _ = get_road_graph()
            (
                traffic_penalty,
                rain_penalty,
                obstacle_penalty,
                edge_weight,
            ) = snapshot_environment_functions()
            assignments = assign_deliveries(
                app_state,
                graph,
                robots,
                deliveries,
                current_time_ms,
                nearest_node_id,
                edge_weight,
                traffic_penalty,
                rain_penalty,
                obstacle_penalty,
                record_route_metrics,
                metrics,
                return_explanations=True,
            )
            return jsonify(assignments), 200
        except Exception as exc:
            import traceback

            traceback.print_exc()
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/optimize-hubs", methods=["POST"])
    def optimize_hubs():
        try:
            hubs = compute_optimized_hubs(
                app_state, cluster_count=DEFAULT_HUB_CLUSTER_COUNT
            )
            graph, _, _ = get_road_graph()
            hubs = snap_hubs_to_graph(hubs, graph, nearest_node_id, app_state["ox"])
            # Sync charging stations with optimized hubs (1:1 replace strategy)
            with app_state["charging_stations_lock"]:
                app_state["charging_stations"].clear()
                for idx, hub in enumerate(hubs, start=1):
                    app_state["charging_stations"].append(
                        {
                            "id": idx,
                            "lat": hub["lat"],
                            "lon": hub["lon"],
                            "name": hub["name"],
                            "spots": 2,
                        }
                    )
            return jsonify({"hubs": hubs}), 200
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/astep")
    def astep_demo():
        try:
            from_lat, from_lon, to_lat, to_lon = parse_route_coordinates(
                demo_route_defaults()
            )
        except ValueError:
            return jsonify({"error": INVALID_COORDS_ERROR}), 400

        graph, start_node, end_node = route_graph_context(
            from_lat, from_lon, to_lat, to_lon
        )
        traffic_penalty, rain_penalty, obstacle_penalty, _ = snapshot_environment_functions()
        payload = run_astep_demo(
            graph,
            start_node,
            end_node,
            to_lat,
            to_lon,
            traffic_penalty,
            rain_penalty,
            obstacle_penalty,
        )
        return jsonify(payload)

    @app.route("/api/insider")
    def insider_comparison():
        try:
            from_lat, from_lon, to_lat, to_lon = parse_route_coordinates(
                demo_route_defaults()
            )
        except ValueError:
            return jsonify({"error": INVALID_COORDS_ERROR}), 400

        graph, start_node, end_node = route_graph_context(
            from_lat, from_lon, to_lat, to_lon
        )
        traffic_penalty, rain_penalty, obstacle_penalty, _ = snapshot_environment_functions()
        payload = run_insider_comparison(
            graph,
            start_node,
            end_node,
            to_lat,
            to_lon,
            traffic_penalty,
            rain_penalty,
            obstacle_penalty,
        )
        payload["from"] = {"lat": from_lat, "lon": from_lon}
        payload["to"] = {"lat": to_lat, "lon": to_lon}
        return jsonify(payload)

    @app.route("/api/classical/compare")
    def classical_compare():
        try:
            from_lat, from_lon, to_lat, to_lon = parse_route_coordinates(
                demo_route_defaults()
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        graph, start_node, end_node = route_graph_context(
            from_lat, from_lon, to_lat, to_lon
        )
        payload = compare_classical_algorithms(
            graph, start_node, end_node, to_lat, to_lon
        )
        payload["from"] = {"lat": from_lat, "lon": from_lon, "nodeId": start_node}
        payload["to"] = {"lat": to_lat, "lon": to_lon, "nodeId": end_node}
        payload["note"] = CLASSICAL_COMPARE_NOTE
        return jsonify(payload)
