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
from ..core.hubs import append_delivery_points, compute_optimized_hubs
from ..utils.geo import haversine_distance


def register_main_routes(app, ctx):
    get_road_graph = ctx["get_road_graph"]
    validate_coordinate = ctx["validate_coordinate"]
    validate_lat_lon = ctx["validate_lat_lon"]
    nearest_node_id = ctx["nearest_node_id"]
    build_route_response = ctx["build_route_response"]
    edge_weight_with_traffic = ctx["edge_weight_with_traffic"]
    traffic_penalty_for_point = ctx["traffic_penalty_for_point"]
    rain_penalty_for_point = ctx["rain_penalty_for_point"]
    obstacle_penalty_for_point = ctx["obstacle_penalty_for_point"]
    record_route_metrics = ctx["record_route_metrics"]
    metrics = ctx["metrics"]
    app_state = ctx["app_state"]

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

        try:
            road_memory = json.loads(request.args.get("memory", "{}"))
        except Exception:
            road_memory = {}

        algo = (request.args.get("algo") or "astar").strip().lower()
        if algo not in {"astar", "gbfs", "dijkstra"}:
            return jsonify({"error": "Invalid algo. Use astar, gbfs, or dijkstra."}), 400

        try:
            graph, _, _ = get_road_graph()
            start_node = nearest_node_id(graph, from_lat, from_lon, app_state["ox"])
            end_node = nearest_node_id(graph, to_lat, to_lon, app_state["ox"])

            def edge_weight_with_memory(from_node, to_node, edge_data):
                base = edge_weight_with_traffic(from_node, to_node, edge_data)
                from_data = graph.nodes[from_node]
                to_data = graph.nodes[to_node]
                key = (
                    f"{from_data['y']:.4f},{from_data['x']:.4f}->"
                    f"{to_data['y']:.4f},{to_data['x']:.4f}"
                )
                memory_penalty = road_memory.get(key, 1.0)
                return base * memory_penalty

            weight_fn = edge_weight_with_memory if road_memory else edge_weight_with_traffic
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
                traffic_penalty_for_point,
                rain_penalty_for_point,
                obstacle_penalty_for_point,
            )
            payload["start"] = {"lat": graph.nodes[start_node]["y"], "lon": graph.nodes[start_node]["x"]}
            payload["end"] = {"lat": graph.nodes[end_node]["y"], "lon": graph.nodes[end_node]["x"]}
            payload["algo"] = algo

            calc_time = (time.time() - start_t) * 1000
            record_route_metrics(metrics, calc_time, nodes_explored, len(route_nodes))
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
                    "path": [{"lat": from_lat, "lon": from_lon}, {"lat": to_lat, "lon": to_lon}],
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
            graph, _, _ = get_road_graph()
            node_id = nearest_node_id(graph, lat, lon, app_state["ox"])
            return jsonify({"lat": graph.nodes[node_id]["y"], "lon": graph.nodes[node_id]["x"]})
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
            append_delivery_points(app_state, pickup_lat, pickup_lon, dropoff_lat, dropoff_lon)
            return jsonify({"status": "success"}), 200
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/optimize-hubs", methods=["POST"])
    def optimize_hubs():
        try:
            hubs = compute_optimized_hubs(app_state, cluster_count=5)
            return jsonify({"hubs": hubs}), 200
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/astep")
    def astep_demo():
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
            from_lat = validate_coordinate(request.args.get("fromLat", 21.0285), "fromLat")
            from_lon = validate_coordinate(request.args.get("fromLon", 105.8542), "fromLon")
            to_lat = validate_coordinate(request.args.get("toLat", 21.0355), "toLat")
            to_lon = validate_coordinate(request.args.get("toLon", 105.8516), "toLon")
            validate_lat_lon(from_lat, from_lon)
            validate_lat_lon(to_lat, to_lon)
        except ValueError:
            return jsonify({"error": "Invalid coords"}), 400

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
            from_lat = validate_coordinate(request.args.get("fromLat", 21.0285), "fromLat")
            from_lon = validate_coordinate(request.args.get("fromLon", 105.8542), "fromLon")
            to_lat = validate_coordinate(request.args.get("toLat", 21.0355), "toLat")
            to_lon = validate_coordinate(request.args.get("toLon", 105.8516), "toLon")
            validate_lat_lon(from_lat, from_lon)
            validate_lat_lon(to_lat, to_lon)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        graph, _, _ = get_road_graph()
        start_node = nearest_node_id(graph, from_lat, from_lon, app_state["ox"])
        end_node = nearest_node_id(graph, to_lat, to_lon, app_state["ox"])
        payload = compare_classical_algorithms(graph, start_node, end_node, to_lat, to_lon)
        payload["from"] = {"lat": from_lat, "lon": from_lon, "nodeId": start_node}
        payload["to"] = {"lat": to_lat, "lon": to_lon, "nodeId": end_node}
        payload["note"] = (
            "Classical AI compare uses base edge length only (no rain/traffic/obstacle penalties)."
        )
        return jsonify(payload)
