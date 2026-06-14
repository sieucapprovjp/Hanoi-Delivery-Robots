import time
from types import SimpleNamespace

from flask import jsonify, render_template, request

from ..algorithms import run_weighted_route_search
from ..algorithms.base import AssignmentInput
from ..algorithms.dispatch import run_assignment_with_csp_xai
from ..core.data import CHARGING_STATIONS, INITIAL_ROBOTS, LOCATIONS
from ..core.hubs import append_delivery_points, compute_optimized_hubs
from ..utils.persistent_log import append_delivery_history
from ..config import (
    DEFAULT_HUB_CLUSTER_COUNT,
    DEFAULT_OPTIMIZED_HUB_SPOTS,
    DISPATCH_ALPHA,
    DISPATCH_BETA,
    DISPATCH_GAMMA,
    DISPATCH_LAMBDA,
    TIMESTAMP_MS_MULTIPLIER,
    VRP_MAX_ORDERS_PER_ROBOT,
)


def register_main_routes(app, ctx):
    app_state = ctx["app_state"]
    get_road_graph = ctx["get_road_graph"]
    nearest_node_id = ctx["nearest_node_id"]
    validate_coordinate = ctx["validate_coordinate"]
    validate_lat_lon = ctx["validate_lat_lon"]
    edge_weight_with_traffic = ctx["edge_weight_with_traffic"]

    def route_search(graph, start_node, end_node, goal_lat, goal_lon, weight_fn, algo):
        return run_weighted_route_search(
            graph,
            start_node,
            end_node,
            goal_lat,
            goal_lon,
            weight_fn,
            algo,
        )

    def append_delivery_history_log(payload):
        log_dir = app_state.get("persistent_log_dir")
        if log_dir:
            return append_delivery_history(payload, log_dir=log_dir)
        return append_delivery_history(payload)

    def normalize_optimized_hubs(hubs):
        normalized = []
        for idx, hub in enumerate(hubs):
            normalized_hub = dict(hub)
            normalized_hub.setdefault("id", idx)
            normalized_hub.setdefault("spots", DEFAULT_OPTIMIZED_HUB_SPOTS)
            normalized.append(normalized_hub)
        return normalized

    def normalize_delivery_payload(delivery):
        dropoff = delivery.get("dropoff") or delivery.get("destination") or {}
        return {
            "id": delivery.get("id") or delivery.get("deliveryId") or delivery.get("orderId"),
            "pickup": delivery.get("pickup") or {},
            "dropoff": dropoff,
            "created_time": delivery.get("createdAt"),
            "theme": delivery.get("theme", {}),
        }

    def normalize_robot_payload(robot):
        return SimpleNamespace(
            robot_id=robot.get("id"),
            id=robot.get("id"),
            name=robot.get("name", robot.get("id")),
            lat=robot.get("lat"),
            lon=robot.get("lon"),
            battery=robot.get("battery", 100.0),
            status=robot.get("status", "idle"),
            capacity=robot.get("capacity", VRP_MAX_ORDERS_PER_ROBOT),
            currentLoad=robot.get("currentLoad", 0),
            task_queue=[],
            current_task=None,
        )

    def serialize_assignment(assignment):
        order = assignment.order
        robot = assignment.robot
        batch_orders = order.get("vrp_batch_orders") or [order]
        order_ids = [item.get("id") for item in batch_orders]
        payload = {
            "robotId": getattr(robot, "id", getattr(robot, "robot_id", None)),
            "robotName": getattr(robot, "name", ""),
            "deliveryId": order.get("id"),
            "deliveryIds": order_ids,
            "pickupName": order.get("pickup", {}).get("name", ""),
            "destinationName": order.get("dropoff", {}).get("name", ""),
            "route": {
                "pickupPathLength": len(assignment.pickup_path),
                "dropoffPathLength": len(assignment.dropoff_path),
                "pickupCost": round(assignment.pickup_cost, 1),
                "dropoffCost": round(assignment.dropoff_cost, 1),
            },
            "breakdown": {
                "pickupCost": round(assignment.pickup_cost, 1),
                "dropoffCost": round(assignment.dropoff_cost, 1),
                "totalCost": round(assignment.pickup_cost + assignment.dropoff_cost, 1),
            },
        }
        if order.get("vrp_sequence"):
            payload["orderSequence"] = order["vrp_sequence"]
            payload["routeSequence"] = order["vrp_sequence"]
            payload["vrpStats"] = order.get("vrp_stats")
            payload["vrpCost"] = round(order.get("vrp_cost", 0.0), 1)
            payload["vrpInitialCost"] = round(order.get("vrp_initial_cost", 0.0), 1)
            payload["vrpImprovementRatio"] = round(
                order.get("vrp_improvement_ratio", 0.0),
                4,
            )
        return payload

    @app.route("/api/data/locations")
    def get_locations():
        return jsonify({"locations": LOCATIONS})

    @app.route("/api/data/hubs")
    def get_hubs():
        return jsonify({"hubs": app_state.get("charging_stations", CHARGING_STATIONS)})

    @app.route("/api/data/robots")
    def get_robots():
        return jsonify({"robots": INITIAL_ROBOTS})

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/snap")
    def snap():
        try:
            lat = validate_coordinate(request.args.get("lat"), "lat")
            lon = validate_coordinate(request.args.get("lon"), "lon")
            validate_lat_lon(lat, lon)
            graph, _, _ = get_road_graph()
            node_id = nearest_node_id(graph, lat, lon)
            return jsonify(
                {
                    "lat": float(graph.nodes[node_id]["y"]),
                    "lon": float(graph.nodes[node_id]["x"]),
                    "nodeId": int(node_id),
                }
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/log_delivery", methods=["POST"])
    def log_delivery():
        try:
            data = request.json or {}
            pickup_lat = validate_coordinate(data.get("pickupLat"), "pickupLat")
            pickup_lon = validate_coordinate(data.get("pickupLon"), "pickupLon")
            dropoff_lat = validate_coordinate(data.get("dropoffLat"), "dropoffLat")
            dropoff_lon = validate_coordinate(data.get("dropoffLon"), "dropoffLon")

            append_delivery_points(
                app_state, pickup_lat, pickup_lon, dropoff_lat, dropoff_lon
            )
            append_delivery_history_log(
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
            data = request.get_json(silent=True) or {}
            robots = [normalize_robot_payload(robot) for robot in data.get("robots", [])]
            deliveries = [
                normalize_delivery_payload(delivery)
                for delivery in data.get("deliveries", [])
            ]
            if not robots or not deliveries:
                return jsonify({"assignments": [], "explanations": []}), 200

            graph, _, _ = get_road_graph()

            def weight_fn(from_node, to_node, edge_data):
                return edge_weight_with_traffic(from_node, to_node, edge_data)

            context = AssignmentInput(
                graph=graph,
                robots=robots,
                orders=deliveries,
                nearest_node_fn=nearest_node_id,
                weight_fn=weight_fn,
                run_route_search_fn=route_search,
                alpha=DISPATCH_ALPHA,
                beta=DISPATCH_BETA,
                gamma=DISPATCH_GAMMA,
                val_lambda=DISPATCH_LAMBDA,
            )
            policy = data.get("model") or app_state.get("dispatch_model", "nearest_idle")
            current_time = data.get("currentTime")
            if current_time is None:
                current_time = round(time.time() * TIMESTAMP_MS_MULTIPLIER)
            result, explanations = run_assignment_with_csp_xai(
                policy,
                context,
                app_state=app_state,
                current_time=current_time,
            )
            payload = {
                "assignments": [
                    serialize_assignment(assignment)
                    for assignment in result.assignments
                ],
                "explanations": explanations,
            }
            return jsonify(payload), 200
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/optimize-hubs", methods=["POST"])
    def optimize_hubs():
        try:
            hubs = compute_optimized_hubs(
                app_state, cluster_count=DEFAULT_HUB_CLUSTER_COUNT
            )
            hubs = normalize_optimized_hubs(hubs)
            app_state["charging_stations"] = hubs
            return jsonify({"hubs": hubs}), 200
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500
