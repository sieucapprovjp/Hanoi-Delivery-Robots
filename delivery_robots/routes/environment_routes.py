import time

import networkx as nx
from flask import jsonify, request

from ..core.event_bus import Event, EventType
from ..config import (
    DEFAULT_LOG_LEVEL,
    DEFAULT_LOG_SOURCE,
    DEFAULT_LOGS_LIMIT,
    DEFAULT_OBSTACLE_RADIUS,
    DEFAULT_OBSTACLE_SEVERITY,
    DEFAULT_OBSTACLE_TYPE,
    DEFAULT_RAIN_MAX_RADIUS,
    DEFAULT_RAIN_MIN_RADIUS,
    DEFAULT_RAIN_RADIUS,
    DEFAULT_RAIN_SEVERITY,
    DEFAULT_RANDOMIZE_OBSTACLE_COUNT,
    DEFAULT_RANDOMIZE_RAIN_COUNT,
    DEFAULT_RANDOMIZE_TRAFFIC_COUNT,
    DEFAULT_TRAFFIC_SEVERITY,
    DEFAULT_WEATHER_RAIN_SEVERITY,
    LOGS_LIMIT_MAX,
    LOGS_LIMIT_MIN,
    OBSTACLE_NAME_PREFIX,
    RAIN_ZONE_NAME_PREFIX,
    RANDOM_TRAFFIC_LAT_MAX,
    RANDOM_TRAFFIC_LAT_MIN,
    RANDOM_TRAFFIC_LON_MAX,
    RANDOM_TRAFFIC_LON_MIN,
    RANDOM_TRAFFIC_PATH_POINT_COUNT,
    RANDOM_TRAFFIC_SEVERITY_MAX,
    RANDOM_TRAFFIC_SEVERITY_MIN,
    TIMESTAMP_MS_MULTIPLIER,
    TRAFFIC_ROUTE_NAME_PREFIX,
    TRAFFIC_SEGMENT_STRENGTH_THRESHOLD,
    TRAFFIC_SEVERITY_CLAMP_MAX,
    TRAFFIC_SEVERITY_CLAMP_MIN,
)


def register_environment_routes(app, ctx):
    app_state = ctx["app_state"]
    get_road_graph = ctx["get_road_graph"]
    build_metrics_payload = ctx["build_metrics_payload"]
    build_route_response = ctx["build_route_response"]
    nearest_node_id = ctx["nearest_node_id"]

    validate_coordinate = ctx["validate_coordinate"]
    validate_lat_lon = ctx["validate_lat_lon"]
    validate_non_negative_int = ctx["validate_non_negative_int"]
    validate_positive_number = ctx["validate_positive_number"]

    traffic_penalty_for_point = ctx["traffic_penalty_for_point"]
    rain_penalty_for_point = ctx["rain_penalty_for_point"]
    obstacle_penalty_for_point = ctx["obstacle_penalty_for_point"]
    edge_weight_with_traffic = ctx["edge_weight_with_traffic"]

    traffic_period_seconds = ctx["traffic_period_seconds"]

    rain_zones = ctx["rain_zones"]
    dynamic_traffic_lock = ctx["dynamic_traffic_lock"]
    dynamic_traffic_routes = ctx["dynamic_traffic_routes"]
    obstacles_lock = ctx["obstacles_lock"]
    obstacles = ctx["obstacles"]
    metrics = ctx["metrics"]
    api_logs = ctx["api_logs"]
    api_logs_lock = ctx["api_logs_lock"]
    get_ox = ctx["get_ox"]
    event_bus = ctx["event_bus"]

    @app.route("/api/dispatch/model", methods=["GET"])
    def get_dispatch_model():
        model = app_state.get("dispatch_model", "nearest_idle")
        return jsonify({"model": model}), 200

    @app.route("/api/dispatch/select", methods=["POST"])
    def set_dispatch_model():
        payload = request.get_json(silent=True) or {}
        model = payload.get("model")
        valid_models = [
            "nearest_idle",
            "nearest_feasible",
            "weighted_cost",
            "hungarian",
        ]
        if not model or model not in valid_models:
            return jsonify(
                {"error": f"Invalid model. Must be one of {valid_models}"}
            ), 400
        app_state["dispatch_model"] = model
        return jsonify({"status": "ok", "model": model}), 200

    @app.route("/api/routing/neighbor-policy", methods=["GET"])
    def get_neighbor_policy():
        policy = app_state.get("neighbor_ordering_policy", "id")
        return jsonify({"policy": policy}), 200

    @app.route("/api/routing/neighbor-policy", methods=["POST"])
    def set_neighbor_policy():
        payload = request.get_json(silent=True) or {}
        policy = payload.get("policy")
        valid_policies = ["id", "bearing"]
        if not policy or policy not in valid_policies:
            return jsonify(
                {"error": f"Invalid policy. Must be one of {valid_policies}"}
            ), 400
        app_state["neighbor_ordering_policy"] = policy
        return jsonify({"status": "ok", "policy": policy}), 200

    @app.route("/api/logs", methods=["GET", "POST"])
    def api_logs_endpoint():
        if request.method == "POST":
            payload = request.get_json(silent=True) or {}
            message = str(payload.get("message", "")).strip()
            if not message:
                return jsonify({"error": "message is required"}), 400

            entry = {
                "ts": payload.get("ts") or round(time.time() * TIMESTAMP_MS_MULTIPLIER),
                "message": message,
                "level": str(payload.get("level", DEFAULT_LOG_LEVEL)),
                "source": str(payload.get("source", DEFAULT_LOG_SOURCE)),
            }
            with api_logs_lock:
                api_logs.append(entry)
            return jsonify({"status": "ok"}), 200

        limit = (
            request.args.get("limit", default=DEFAULT_LOGS_LIMIT, type=int)
            or DEFAULT_LOGS_LIMIT
        )
        limit = max(LOGS_LIMIT_MIN, min(limit, LOGS_LIMIT_MAX))
        with api_logs_lock:
            logs = list(api_logs)
        logs.reverse()
        return jsonify({"logs": logs[:limit], "count": min(limit, len(logs))})

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.route("/api/traffic")
    def traffic():
        now = time.time()
        roads = []

        _, _, traffic_routes = get_road_graph()
        all_routes = list(traffic_routes or [])
        with dynamic_traffic_lock:
            all_routes.extend(dynamic_traffic_routes)

        for road in all_routes:
            if len(road["path"]) < 2:
                roads.append({"name": road["name"], "segments": []})
                continue

            progress = (now / traffic_period_seconds + road["severity"]) % 1
            active_segment = progress * (len(road["path"]) - 1)
            segments = []

            for idx in range(len(road["path"]) - 1):
                strength = max(0.0, 1 - abs(idx - active_segment))
                if strength < TRAFFIC_SEGMENT_STRENGTH_THRESHOLD:
                    continue

                segments.append(
                    {
                        "points": [
                            [road["path"][idx]["lat"], road["path"][idx]["lon"]],
                            [
                                road["path"][idx + 1]["lat"],
                                road["path"][idx + 1]["lon"],
                            ],
                        ],
                        "severity": round(road["severity"] * strength, 3),
                    }
                )

            roads.append({"name": road["name"], "segments": segments})

        return jsonify({"roads": roads, "updatedAt": now})

    @app.route("/api/weather")
    def weather():
        return jsonify(
            {
                "rainZones": [
                    {
                        "name": zone["name"],
                        "center": {"lat": zone["center"][0], "lon": zone["center"][1]},
                        "radius": zone["radius"],
                        "multiplier": round(
                            1 + zone.get("severity", DEFAULT_WEATHER_RAIN_SEVERITY), 2
                        ),
                    }
                    for zone in rain_zones
                ]
            }
        )

    @app.route("/api/metrics")
    def get_metrics():
        include_static = request.args.get("static", "false").lower() == "true"
        return jsonify(
            build_metrics_payload(
                metrics,
                ctx["road_graph_getter"](),
                len(rain_zones),
                len(dynamic_traffic_routes),
                len(obstacles),
                include_static=include_static,
            )
        )

    @app.route("/api/rain/list")
    def list_rain():
        return jsonify(
            {
                "rainZones": [
                    {
                        "name": z["name"],
                        "center": {"lat": z["center"][0], "lon": z["center"][1]},
                        "radius": z["radius"],
                    }
                    for z in rain_zones
                ]
            }
        )

    @app.route("/api/rain/add", methods=["POST"])
    def add_rain():
        d = request.get_json(silent=True) or {}
        try:
            lat = validate_coordinate(d.get("lat"), "lat")
            lon = validate_coordinate(d.get("lon"), "lon")
            radius = validate_positive_number(
                d.get("radius", DEFAULT_RAIN_RADIUS), "radius"
            )
            validate_lat_lon(lat, lon)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        event_bus.publish(
            Event(
                EventType.RAIN_ADDED,
                {
                    "lat": lat,
                    "lon": lon,
                    "radius": radius,
                    "severity": DEFAULT_RAIN_SEVERITY,
                },
            )
        )
        return jsonify(
            {
                "message": "Added",
                "rainZone": {
                    "name": f"{RAIN_ZONE_NAME_PREFIX}{len(rain_zones)}",
                    "center": {"lat": lat, "lon": lon},
                    "radius": radius,
                },
            }
        )

    @app.route("/api/rain/randomize", methods=["POST"])
    def randomize_rain():

        d = request.get_json(silent=True) or {}
        try:
            count = validate_non_negative_int(
                d.get("count", DEFAULT_RANDOMIZE_RAIN_COUNT), "count"
            )
            min_radius = validate_positive_number(
                d.get("minRadius", DEFAULT_RAIN_MIN_RADIUS), "minRadius"
            )
            max_radius = validate_positive_number(
                d.get("maxRadius", DEFAULT_RAIN_MAX_RADIUS), "maxRadius"
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        if min_radius > max_radius:
            return jsonify(
                {"error": "minRadius must be less than or equal to maxRadius"}
            ), 400

        event_bus.publish(
            Event(
                EventType.RAIN_RANDOMIZED,
                {
                    "count": count,
                    "minRadius": min_radius,
                    "maxRadius": max_radius,
                },
            )
        )
        return jsonify(
            {
                "message": f"Added {count}",
                "rainZones": [
                    {
                        "name": z["name"],
                        "center": {"lat": z["center"][0], "lon": z["center"][1]},
                        "radius": z["radius"],
                    }
                    for z in rain_zones
                ],
            }
        )

    @app.route("/api/rain/clear", methods=["POST"])
    def clear_rain():
        event_bus.publish(Event(EventType.RAIN_CLEARED))
        return jsonify({"message": "Cleared"})

    @app.route("/api/traffic/list")
    def list_traffic_routes():
        with dynamic_traffic_lock:
            return jsonify({"routes": list(dynamic_traffic_routes)})

    @app.route("/api/traffic/add", methods=["POST"])
    def add_traffic_route():
        d = request.get_json(silent=True) or {}

        try:
            start_lat = validate_coordinate(d.get("startLat"), "startLat")
            start_lon = validate_coordinate(d.get("startLon"), "startLon")
            end_lat = validate_coordinate(d.get("endLat"), "endLat")
            end_lon = validate_coordinate(d.get("endLon"), "endLon")
            validate_lat_lon(start_lat, start_lon)
            validate_lat_lon(end_lat, end_lon)
            severity = float(d.get("severity", DEFAULT_TRAFFIC_SEVERITY))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        if start_lat == end_lat and start_lon == end_lon:
            return jsonify({"error": "Traffic start and end must be different"}), 400

        severity = max(
            TRAFFIC_SEVERITY_CLAMP_MIN, min(TRAFFIC_SEVERITY_CLAMP_MAX, severity)
        )

        graph, _, _ = get_road_graph()
        ox = get_ox()
        start_node = nearest_node_id(graph, start_lat, start_lon, ox)
        end_node = nearest_node_id(graph, end_lat, end_lon, ox)
        route_nodes = nx.shortest_path(graph, start_node, end_node, weight="length")
        route_payload = build_route_response(
            graph,
            route_nodes,
            traffic_penalty_for_point,
            rain_penalty_for_point,
            obstacle_penalty_for_point,
            include_cost_breakdown=False,
        )

        route_name = (
            d.get("name")
            or f"{TRAFFIC_ROUTE_NAME_PREFIX}{len(dynamic_traffic_routes) + 1}"
        )
        event_bus.publish(
            Event(
                EventType.TRAFFIC_ADDED,
                {
                    "name": route_name,
                    "severity": severity,
                    "path": route_payload["path"],
                },
            )
        )

        with dynamic_traffic_lock:
            route = dynamic_traffic_routes[-1]
            routes_list = list(dynamic_traffic_routes)

        return jsonify({"message": "Added", "route": route, "routes": routes_list})

    @app.route("/api/traffic/randomize", methods=["POST"])
    def randomize_traffic():
        import random

        d = request.get_json(silent=True) or {}
        try:
            count = validate_non_negative_int(
                d.get("count", DEFAULT_RANDOMIZE_TRAFFIC_COUNT), "count"
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        routes = []
        for i in range(count):
            routes.append(
                {
                    "name": f"{TRAFFIC_ROUTE_NAME_PREFIX}{i + 1}",
                    "severity": random.uniform(
                        RANDOM_TRAFFIC_SEVERITY_MIN, RANDOM_TRAFFIC_SEVERITY_MAX
                    ),
                    "path": [
                        {
                            "lat": random.uniform(
                                RANDOM_TRAFFIC_LAT_MIN, RANDOM_TRAFFIC_LAT_MAX
                            ),
                            "lon": random.uniform(
                                RANDOM_TRAFFIC_LON_MIN, RANDOM_TRAFFIC_LON_MAX
                            ),
                        }
                        for _ in range(RANDOM_TRAFFIC_PATH_POINT_COUNT)
                    ],
                }
            )
        event_bus.publish(Event(EventType.TRAFFIC_RANDOMIZED, {"count": count}))
        with dynamic_traffic_lock:
            routes = list(dynamic_traffic_routes)
        return jsonify({"message": f"Added {count}", "routes": routes})

    @app.route("/api/traffic/clear", methods=["POST"])
    def clear_traffic():
        event_bus.publish(Event(EventType.TRAFFIC_CLEARED))
        return jsonify({"message": "Cleared"})

    @app.route("/api/obstacle/list")
    def list_obstacles():
        with obstacles_lock:
            return jsonify(
                {
                    "obstacles": [
                        {
                            "name": o["name"],
                            "center": {"lat": o["center"][0], "lon": o["center"][1]},
                            "radius": o["radius"],
                            "severity": o["severity"],
                            "type": o["type"],
                        }
                        for o in obstacles
                    ]
                }
            )

    @app.route("/api/obstacle/add", methods=["POST"])
    def add_obstacle():
        d = request.get_json(silent=True) or {}
        try:
            lat = validate_coordinate(d.get("lat"), "lat")
            lon = validate_coordinate(d.get("lon"), "lon")
            radius = validate_positive_number(
                d.get("radius", DEFAULT_OBSTACLE_RADIUS), "radius"
            )
            severity = validate_positive_number(
                d.get("severity", DEFAULT_OBSTACLE_SEVERITY), "severity"
            )
            validate_lat_lon(lat, lon)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        obstacle_name = d.get("name") or f"{OBSTACLE_NAME_PREFIX}{len(obstacles) + 1}"
        event_bus.publish(
            Event(
                EventType.OBSTACLE_ADDED,
                {
                    "name": obstacle_name,
                    "lat": lat,
                    "lon": lon,
                    "radius": radius,
                    "severity": severity,
                    "type": d.get("type", DEFAULT_OBSTACLE_TYPE),
                },
            )
        )

        with obstacles_lock:
            obstacle = obstacles[-1]

        return jsonify(
            {
                "message": "Added",
                "obstacle": {
                    "name": obstacle["name"],
                    "center": {"lat": lat, "lon": lon},
                    "radius": obstacle["radius"],
                    "severity": obstacle["severity"],
                    "type": obstacle["type"],
                },
            }
        )

    @app.route("/api/obstacle/randomize", methods=["POST"])
    def randomize_obstacles():

        d = request.get_json(silent=True) or {}
        try:
            count = validate_non_negative_int(
                d.get("count", DEFAULT_RANDOMIZE_OBSTACLE_COUNT), "count"
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        event_bus.publish(Event(EventType.OBSTACLE_RANDOMIZED, {"count": count}))
        with obstacles_lock:
            obs_list = [
                {
                    "name": o["name"],
                    "center": {"lat": o["center"][0], "lon": o["center"][1]},
                    "radius": o["radius"],
                    "severity": o["severity"],
                    "type": o["type"],
                }
                for o in obstacles
            ]
        return jsonify(
            {
                "message": f"Added {count}",
                "obstacles": obs_list,
            }
        )

    @app.route("/api/obstacle/clear", methods=["POST"])
    def clear_obstacles():
        event_bus.publish(Event(EventType.OBSTACLE_CLEARED))
        return jsonify({"message": "Cleared"})

    @app.route("/api/route", methods=["GET"])
    def get_route_breakdown():
        try:
            from_lat = validate_coordinate(request.args.get("fromLat"), "fromLat")
            from_lon = validate_coordinate(request.args.get("fromLon"), "fromLon")
            to_lat = validate_coordinate(request.args.get("toLat"), "toLat")
            to_lon = validate_coordinate(request.args.get("toLon"), "toLon")
            validate_lat_lon(from_lat, from_lon)
            validate_lat_lon(to_lat, to_lon)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        graph, _, _ = get_road_graph()
        ox = get_ox()
        try:
            start_node = nearest_node_id(graph, from_lat, from_lon, ox)
            end_node = nearest_node_id(graph, to_lat, to_lon, ox)
            route_nodes = nx.shortest_path(
                graph, start_node, end_node, weight=edge_weight_with_traffic
            )
            route_payload = build_route_response(
                graph,
                route_nodes,
                traffic_penalty_for_point,
                rain_penalty_for_point,
                obstacle_penalty_for_point,
                include_cost_breakdown=True,
            )
            return jsonify(route_payload), 200
        except nx.NetworkXNoPath:
            return jsonify(
                {"error": "No path found between the specified coordinates"}
            ), 404
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500
