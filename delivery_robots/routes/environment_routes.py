import time

import networkx as nx
from flask import jsonify, request

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
    OBSTACLE_RANDOMIZE_NAME_PREFIX,
    OBSTACLE_TYPES,
    RAIN_ZONE_NAME_PREFIX,
    RANDOM_LAT_MAX,
    RANDOM_LAT_MIN,
    RANDOM_LON_MAX,
    RANDOM_LON_MIN,
    RANDOM_OBSTACLE_RADIUS_MAX,
    RANDOM_OBSTACLE_RADIUS_MIN,
    RANDOM_OBSTACLE_SEVERITY_MAX,
    RANDOM_OBSTACLE_SEVERITY_MIN,
    RANDOM_TRAFFIC_LAT_MAX,
    RANDOM_TRAFFIC_LAT_MIN,
    RANDOM_TRAFFIC_LON_MAX,
    RANDOM_TRAFFIC_LON_MIN,
    RANDOM_TRAFFIC_PATH_POINT_COUNT,
    RANDOM_TRAFFIC_SEVERITY_MAX,
    RANDOM_TRAFFIC_SEVERITY_MIN,
    RUSH_HOUR_INACTIVE_LABEL,
    TIMESTAMP_MS_MULTIPLIER,
    TRAFFIC_ROUTE_NAME_PREFIX,
    TRAFFIC_SEGMENT_STRENGTH_THRESHOLD,
    TRAFFIC_SEVERITY_CLAMP_MAX,
    TRAFFIC_SEVERITY_CLAMP_MIN,
)


def register_environment_routes(app, ctx):
    get_road_graph = ctx["get_road_graph"]
    get_simulation_time = ctx["get_simulation_time"]
    get_rush_hour_multiplier = ctx["get_rush_hour_multiplier"]
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

    traffic_period_seconds = ctx["traffic_period_seconds"]
    rush_hours = ctx["rush_hours"]
    simulation_speed = ctx["simulation_speed"]

    rain_zones = ctx["rain_zones"]
    dynamic_traffic_lock = ctx["dynamic_traffic_lock"]
    dynamic_traffic_routes = ctx["dynamic_traffic_routes"]
    obstacles_lock = ctx["obstacles_lock"]
    obstacles = ctx["obstacles"]
    metrics = ctx["metrics"]
    api_logs = ctx["api_logs"]
    api_logs_lock = ctx["api_logs_lock"]
    get_ox = ctx["get_ox"]
    app_state = ctx["app_state"]

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

        limit = request.args.get("limit", default=DEFAULT_LOGS_LIMIT, type=int) or DEFAULT_LOGS_LIMIT
        limit = max(LOGS_LIMIT_MIN, min(limit, LOGS_LIMIT_MAX))
        with api_logs_lock:
            logs = list(api_logs)
        logs.reverse()
        return jsonify({"logs": logs[:limit], "count": min(limit, len(logs))})

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.route("/api/charging-stations", methods=["GET"])
    def list_charging_stations():
        with app_state["charging_stations_lock"]:
            stations = [
                {
                    "id": station["id"],
                    "lat": station["lat"],
                    "lon": station["lon"],
                    "name": station["name"],
                    "spots": station["spots"],
                }
                for station in app_state["charging_stations"]
            ]
        return jsonify({"stations": stations})

    @app.route("/api/charging-stations/<int:station_id>", methods=["PUT"])
    def update_charging_station(station_id):
        payload = request.get_json(silent=True) or {}
        try:
            lat = validate_coordinate(payload.get("lat"), "lat")
            lon = validate_coordinate(payload.get("lon"), "lon")
            validate_lat_lon(lat, lon)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        with app_state["charging_stations_lock"]:
            station = next(
                (
                    item
                    for item in app_state["charging_stations"]
                    if item["id"] == station_id
                ),
                None,
            )
            if station is None:
                return jsonify({"error": "Charging station not found"}), 404

            station["lat"] = lat
            station["lon"] = lon
            updated = dict(station)

        return jsonify({"status": "ok", "station": updated})

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
                            [road["path"][idx + 1]["lat"], road["path"][idx + 1]["lon"]],
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
                        "multiplier": round(1 + zone.get("severity", DEFAULT_WEATHER_RAIN_SEVERITY), 2),
                    }
                    for zone in rain_zones
                ]
            }
        )

    @app.route("/api/clock")
    def get_clock():
        hours, minutes, seconds = get_simulation_time()
        rush_multiplier, rush_name = get_rush_hour_multiplier()
        is_rush_hour = rush_name != RUSH_HOUR_INACTIVE_LABEL

        return jsonify(
            {
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
                    "schedule": rush_hours,
                },
                "simulationSpeed": simulation_speed,
            }
        )

    @app.route("/api/metrics")
    def get_metrics():
        graph = ctx["road_graph_getter"]()
        if graph is None:
            graph = get_road_graph()[0]
        return jsonify(
            build_metrics_payload(
                metrics,
                graph,
                len(rain_zones),
                len(dynamic_traffic_routes),
                len(obstacles),
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
            radius = validate_positive_number(d.get("radius", DEFAULT_RAIN_RADIUS), "radius")
            validate_lat_lon(lat, lon)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        rain_zones.append(
            {
                "name": f"{RAIN_ZONE_NAME_PREFIX}{len(rain_zones) + 1}",
                "center": (lat, lon),
                "radius": radius,
                "severity": DEFAULT_RAIN_SEVERITY,
            }
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
        import random

        d = request.get_json(silent=True) or {}
        try:
            count = validate_non_negative_int(d.get("count", DEFAULT_RANDOMIZE_RAIN_COUNT), "count")
            min_radius = validate_positive_number(d.get("minRadius", DEFAULT_RAIN_MIN_RADIUS), "minRadius")
            max_radius = validate_positive_number(d.get("maxRadius", DEFAULT_RAIN_MAX_RADIUS), "maxRadius")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        if min_radius > max_radius:
            return jsonify({"error": "minRadius must be less than or equal to maxRadius"}), 400

        rain_zones.clear()
        rain_zones.extend(
            [
                {
                    "name": f"{RAIN_ZONE_NAME_PREFIX}{i + 1}",
                    "center": (
                        random.uniform(RANDOM_LAT_MIN, RANDOM_LAT_MAX),
                        random.uniform(RANDOM_LON_MIN, RANDOM_LON_MAX),
                    ),
                    "radius": random.uniform(min_radius, max_radius),
                    "severity": DEFAULT_RAIN_SEVERITY,
                }
                for i in range(count)
            ]
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
        rain_zones.clear()
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

        severity = max(TRAFFIC_SEVERITY_CLAMP_MIN, min(TRAFFIC_SEVERITY_CLAMP_MAX, severity))

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

        with dynamic_traffic_lock:
            route_name = d.get("name") or f"{TRAFFIC_ROUTE_NAME_PREFIX}{len(dynamic_traffic_routes) + 1}"
            route = {"name": route_name, "severity": severity, "path": route_payload["path"]}
            dynamic_traffic_routes.append(route)

        return jsonify({"message": "Added", "route": route, "routes": list(dynamic_traffic_routes)})

    @app.route("/api/traffic/randomize", methods=["POST"])
    def randomize_traffic():
        import random

        d = request.get_json(silent=True) or {}
        try:
            count = validate_non_negative_int(d.get("count", DEFAULT_RANDOMIZE_TRAFFIC_COUNT), "count")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        routes = []
        for i in range(count):
            routes.append(
                {
                    "name": f"{TRAFFIC_ROUTE_NAME_PREFIX}{i + 1}",
                    "severity": random.uniform(RANDOM_TRAFFIC_SEVERITY_MIN, RANDOM_TRAFFIC_SEVERITY_MAX),
                    "path": [
                        {
                            "lat": random.uniform(RANDOM_TRAFFIC_LAT_MIN, RANDOM_TRAFFIC_LAT_MAX),
                            "lon": random.uniform(RANDOM_TRAFFIC_LON_MIN, RANDOM_TRAFFIC_LON_MAX),
                        }
                        for _ in range(RANDOM_TRAFFIC_PATH_POINT_COUNT)
                    ],
                }
            )
        with dynamic_traffic_lock:
            dynamic_traffic_routes.clear()
            dynamic_traffic_routes.extend(routes)
        return jsonify({"message": f"Added {count}", "routes": routes})

    @app.route("/api/traffic/clear", methods=["POST"])
    def clear_traffic():
        with dynamic_traffic_lock:
            dynamic_traffic_routes.clear()
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
            radius = validate_positive_number(d.get("radius", DEFAULT_OBSTACLE_RADIUS), "radius")
            severity = validate_positive_number(d.get("severity", DEFAULT_OBSTACLE_SEVERITY), "severity")
            validate_lat_lon(lat, lon)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        obstacle = {
            "name": f"{OBSTACLE_NAME_PREFIX}{len(obstacles) + 1}",
            "center": (lat, lon),
            "radius": radius,
            "severity": severity,
            "type": d.get("type", DEFAULT_OBSTACLE_TYPE),
        }
        with obstacles_lock:
            obstacles.append(obstacle)
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
        import random

        d = request.get_json(silent=True) or {}
        try:
            count = validate_non_negative_int(d.get("count", DEFAULT_RANDOMIZE_OBSTACLE_COUNT), "count")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        with obstacles_lock:
            obstacles.clear()
            obstacles.extend(
                [
                    {
                        "name": f"{OBSTACLE_RANDOMIZE_NAME_PREFIX}{i + 1}",
                        "center": (
                            random.uniform(RANDOM_LAT_MIN, RANDOM_LAT_MAX),
                            random.uniform(RANDOM_LON_MIN, RANDOM_LON_MAX),
                        ),
                        "radius": random.uniform(RANDOM_OBSTACLE_RADIUS_MIN, RANDOM_OBSTACLE_RADIUS_MAX),
                        "severity": random.uniform(RANDOM_OBSTACLE_SEVERITY_MIN, RANDOM_OBSTACLE_SEVERITY_MAX),
                        "type": random.choice(OBSTACLE_TYPES),
                    }
                    for i in range(count)
                ]
            )
        return jsonify(
            {
                "message": f"Added {count}",
                "obstacles": [
                    {
                        "name": o["name"],
                        "center": {"lat": o["center"][0], "lon": o["center"][1]},
                        "radius": o["radius"],
                        "severity": o["severity"],
                        "type": o["type"],
                    }
                    for o in obstacles
                ],
            }
        )

    @app.route("/api/obstacle/clear", methods=["POST"])
    def clear_obstacles():
        with obstacles_lock:
            obstacles.clear()
        return jsonify({"message": "Cleared"})
