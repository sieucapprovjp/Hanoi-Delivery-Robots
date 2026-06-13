import random
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
from ..utils.persistent_log import append_app_event


def serialize_center_item(item):
    return {
        "name": item["name"],
        "center": {"lat": item["center"][0], "lon": item["center"][1]},
        "radius": item["radius"],
    }


def serialize_weather_rain_zone(zone):
    payload = serialize_center_item(zone)
    payload["multiplier"] = round(
        1 + zone.get("severity", DEFAULT_WEATHER_RAIN_SEVERITY), 2
    )
    return payload


def serialize_obstacle(obstacle):
    payload = serialize_center_item(obstacle)
    payload["severity"] = obstacle["severity"]
    payload["type"] = obstacle["type"]
    return payload


def serialize_charging_station(station):
    return {
        "id": station["id"],
        "lat": station["lat"],
        "lon": station["lon"],
        "name": station["name"],
        "spots": station["spots"],
    }


def parse_lat_lon(payload, validate_coordinate, validate_lat_lon, lat_key="lat", lon_key="lon"):
    lat = validate_coordinate(payload.get(lat_key), lat_key)
    lon = validate_coordinate(payload.get(lon_key), lon_key)
    validate_lat_lon(lat, lon)
    return lat, lon


def clamp_number(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def build_random_rain_zones(count, min_radius, max_radius):
    return [
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


def build_random_traffic_routes(count):
    return [
        {
            "name": f"{TRAFFIC_ROUTE_NAME_PREFIX}{i + 1}",
            "severity": random.uniform(
                RANDOM_TRAFFIC_SEVERITY_MIN, RANDOM_TRAFFIC_SEVERITY_MAX
            ),
            "path": [
                {
                    "lat": random.uniform(RANDOM_TRAFFIC_LAT_MIN, RANDOM_TRAFFIC_LAT_MAX),
                    "lon": random.uniform(RANDOM_TRAFFIC_LON_MIN, RANDOM_TRAFFIC_LON_MAX),
                }
                for _ in range(RANDOM_TRAFFIC_PATH_POINT_COUNT)
            ],
        }
        for i in range(count)
    ]


def build_random_obstacles(count):
    return [
        {
            "name": f"{OBSTACLE_RANDOMIZE_NAME_PREFIX}{i + 1}",
            "center": (
                random.uniform(RANDOM_LAT_MIN, RANDOM_LAT_MAX),
                random.uniform(RANDOM_LON_MIN, RANDOM_LON_MAX),
            ),
            "radius": random.uniform(
                RANDOM_OBSTACLE_RADIUS_MIN, RANDOM_OBSTACLE_RADIUS_MAX
            ),
            "severity": random.uniform(
                RANDOM_OBSTACLE_SEVERITY_MIN, RANDOM_OBSTACLE_SEVERITY_MAX
            ),
            "type": random.choice(OBSTACLE_TYPES),
        }
        for i in range(count)
    ]


def build_active_traffic_roads(traffic_routes, now, traffic_period_seconds):
    roads = []
    for road in traffic_routes:
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
    return roads


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

    metrics = ctx["metrics"]
    api_logs = ctx["api_logs"]
    api_logs_lock = ctx["api_logs_lock"]
    get_ox = ctx["get_ox"]
    app_state = ctx["app_state"]

    def get_rain_zones():
        return app_state["rain_zones"]

    def get_dynamic_traffic_routes():
        return app_state["dynamic_traffic_routes"]

    def get_obstacles():
        return app_state["obstacles"]

    def get_dynamic_traffic_lock():
        return app_state["dynamic_traffic_lock"]

    def get_obstacles_lock():
        return app_state["obstacles_lock"]

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
            append_app_event(entry)
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
                serialize_charging_station(station)
                for station in app_state["charging_stations"]
            ]
        return jsonify({"stations": stations})

    @app.route("/api/charging-stations/<int:station_id>", methods=["PUT"])
    def update_charging_station(station_id):
        payload = request.get_json(silent=True) or {}
        try:
            lat, lon = parse_lat_lon(payload, validate_coordinate, validate_lat_lon)
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

        _, _, traffic_routes = get_road_graph()
        all_routes = list(traffic_routes or [])
        with get_dynamic_traffic_lock():
            all_routes.extend(get_dynamic_traffic_routes())

        roads = build_active_traffic_roads(all_routes, now, traffic_period_seconds)
        return jsonify({"roads": roads, "updatedAt": now})

    @app.route("/api/weather")
    def weather():
        return jsonify(
            {
                "rainZones": [
                    serialize_weather_rain_zone(zone)
                    for zone in get_rain_zones()
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
                len(get_rain_zones()),
                len(get_dynamic_traffic_routes()),
                len(get_obstacles()),
            )
        )

    @app.route("/api/rain/list")
    def list_rain():
        return jsonify(
            {
                "rainZones": [
                    serialize_center_item(z)
                    for z in get_rain_zones()
                ]
            }
        )

    @app.route("/api/rain/add", methods=["POST"])
    def add_rain():
        d = request.get_json(silent=True) or {}
        try:
            lat, lon = parse_lat_lon(d, validate_coordinate, validate_lat_lon)
            radius = validate_positive_number(d.get("radius", DEFAULT_RAIN_RADIUS), "radius")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        rain_zones = get_rain_zones()
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
                "rainZone": serialize_center_item(rain_zones[-1]),
            }
        )

    @app.route("/api/rain/randomize", methods=["POST"])
    def randomize_rain():
        d = request.get_json(silent=True) or {}
        try:
            count = validate_non_negative_int(d.get("count", DEFAULT_RANDOMIZE_RAIN_COUNT), "count")
            min_radius = validate_positive_number(d.get("minRadius", DEFAULT_RAIN_MIN_RADIUS), "minRadius")
            max_radius = validate_positive_number(d.get("maxRadius", DEFAULT_RAIN_MAX_RADIUS), "maxRadius")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        if min_radius > max_radius:
            return jsonify({"error": "minRadius must be less than or equal to maxRadius"}), 400

        rain_zones = get_rain_zones()
        rain_zones.clear()
        rain_zones.extend(build_random_rain_zones(count, min_radius, max_radius))
        return jsonify(
            {
                "message": f"Added {count}",
                "rainZones": [
                    serialize_center_item(z)
                    for z in rain_zones
                ],
            }
        )

    @app.route("/api/rain/clear", methods=["POST"])
    def clear_rain():
        get_rain_zones().clear()
        return jsonify({"message": "Cleared"})

    @app.route("/api/traffic/list")
    def list_traffic_routes():
        with get_dynamic_traffic_lock():
            return jsonify({"routes": list(get_dynamic_traffic_routes())})

    @app.route("/api/traffic/add", methods=["POST"])
    def add_traffic_route():
        d = request.get_json(silent=True) or {}

        try:
            start_lat, start_lon = parse_lat_lon(
                d, validate_coordinate, validate_lat_lon, "startLat", "startLon"
            )
            end_lat, end_lon = parse_lat_lon(
                d, validate_coordinate, validate_lat_lon, "endLat", "endLon"
            )
            severity = float(d.get("severity", DEFAULT_TRAFFIC_SEVERITY))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        if start_lat == end_lat and start_lon == end_lon:
            return jsonify({"error": "Traffic start and end must be different"}), 400

        severity = clamp_number(
            severity, TRAFFIC_SEVERITY_CLAMP_MIN, TRAFFIC_SEVERITY_CLAMP_MAX
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

        with get_dynamic_traffic_lock():
            dynamic_traffic_routes = get_dynamic_traffic_routes()
            route_name = d.get("name") or f"{TRAFFIC_ROUTE_NAME_PREFIX}{len(dynamic_traffic_routes) + 1}"
            route = {"name": route_name, "severity": severity, "path": route_payload["path"]}
            dynamic_traffic_routes.append(route)

        return jsonify({"message": "Added", "route": route, "routes": list(dynamic_traffic_routes)})

    @app.route("/api/traffic/randomize", methods=["POST"])
    def randomize_traffic():
        d = request.get_json(silent=True) or {}
        try:
            count = validate_non_negative_int(d.get("count", DEFAULT_RANDOMIZE_TRAFFIC_COUNT), "count")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        routes = build_random_traffic_routes(count)
        with get_dynamic_traffic_lock():
            dynamic_traffic_routes = get_dynamic_traffic_routes()
            dynamic_traffic_routes.clear()
            dynamic_traffic_routes.extend(routes)
        return jsonify({"message": f"Added {count}", "routes": routes})

    @app.route("/api/traffic/clear", methods=["POST"])
    def clear_traffic():
        with get_dynamic_traffic_lock():
            get_dynamic_traffic_routes().clear()
        return jsonify({"message": "Cleared"})

    @app.route("/api/obstacle/list")
    def list_obstacles():
        with get_obstacles_lock():
            return jsonify(
                {
                    "obstacles": [
                        serialize_obstacle(o)
                        for o in get_obstacles()
                    ]
                }
            )

    @app.route("/api/obstacle/add", methods=["POST"])
    def add_obstacle():
        d = request.get_json(silent=True) or {}
        try:
            lat, lon = parse_lat_lon(d, validate_coordinate, validate_lat_lon)
            radius = validate_positive_number(d.get("radius", DEFAULT_OBSTACLE_RADIUS), "radius")
            severity = validate_positive_number(d.get("severity", DEFAULT_OBSTACLE_SEVERITY), "severity")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        with get_obstacles_lock():
            obstacles = get_obstacles()
            obstacle = {
                "name": f"{OBSTACLE_NAME_PREFIX}{len(obstacles) + 1}",
                "center": (lat, lon),
                "radius": radius,
                "severity": severity,
                "type": d.get("type", DEFAULT_OBSTACLE_TYPE),
            }
            obstacles.append(obstacle)
        return jsonify(
            {
                "message": "Added",
                "obstacle": serialize_obstacle(obstacle),
            }
        )

    @app.route("/api/obstacle/randomize", methods=["POST"])
    def randomize_obstacles():
        d = request.get_json(silent=True) or {}
        try:
            count = validate_non_negative_int(d.get("count", DEFAULT_RANDOMIZE_OBSTACLE_COUNT), "count")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        with get_obstacles_lock():
            obstacles = get_obstacles()
            obstacles.clear()
            obstacles.extend(build_random_obstacles(count))
        return jsonify(
            {
                "message": f"Added {count}",
                "obstacles": [
                    serialize_obstacle(o)
                    for o in obstacles
                ],
            }
        )

    @app.route("/api/obstacle/clear", methods=["POST"])
    def clear_obstacles():
        with get_obstacles_lock():
            get_obstacles().clear()
        return jsonify({"message": "Cleared"})
