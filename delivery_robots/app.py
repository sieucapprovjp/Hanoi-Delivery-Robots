from flask import Flask, jsonify, render_template, request
import math
import threading
import time

import networkx as nx


app = Flask(__name__)

GRAPH_CENTER = (21.0285, 105.8542)
GRAPH_DIST_METERS = 2200
GRAPH_NETWORK_TYPE = "bike"
TRAFFIC_ANCHORS = [
    {
        "name": "Le Thai To",
        "start": (21.0242, 105.8487),
        "end": (21.0249, 105.8527),
        "severity": 0.9,
    },
    {
        "name": "Dinh Tien Hoang",
        "start": (21.0321, 105.8525),
        "end": (21.0249, 105.8527),
        "severity": 0.75,
    },
    {
        "name": "Hai Ba Trung",
        "start": (21.0220, 105.8510),
        "end": (21.0299, 105.8531),
        "severity": 0.65,
    },
]
TRAFFIC_PERIOD_SECONDS = 36
RAIN_ZONES = [
    {"name": "South Lake Edge", "center": (21.0248, 105.8532), "radius": 155, "severity": 1.0},
    {"name": "East Corridor", "center": (21.0284, 105.8562), "radius": 140, "severity": 1.0},
]

_graph_lock = threading.Lock()
_road_graph = None
_projected_road_graph = None
_traffic_routes = None
_ox = None


def haversine_distance(lat1, lon1, lat2, lon2):
    radius = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_road_graph():
    global _road_graph, _projected_road_graph, _traffic_routes, _ox

    if _road_graph is not None and _projected_road_graph is not None and _traffic_routes is not None:
        return _road_graph, _projected_road_graph, _traffic_routes

    with _graph_lock:
        if _ox is None:
            import osmnx as ox

            _ox = ox

        if _road_graph is None:
            _road_graph = _ox.graph_from_point(
                GRAPH_CENTER,
                dist=GRAPH_DIST_METERS,
                network_type=GRAPH_NETWORK_TYPE,
                simplify=True,
            )
            _projected_road_graph = _ox.project_graph(_road_graph)
            _traffic_routes = build_traffic_routes(_road_graph)

    return _road_graph, _projected_road_graph, _traffic_routes


def validate_coordinate(value, name):
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {name}") from exc


def nearest_node_id(graph, lat, lon):
    best_node_id = None
    best_distance = float("inf")

    for node_id, node_data in graph.nodes(data=True):
        distance = haversine_distance(lat, lon, node_data["y"], node_data["x"])
        if distance < best_distance:
            best_distance = distance
            best_node_id = node_id

    return best_node_id


def build_traffic_routes(graph):
    routes = []

    for anchor in TRAFFIC_ANCHORS:
        start_lat, start_lon = anchor["start"]
        end_lat, end_lon = anchor["end"]
        start_node = nearest_node_id(graph, start_lat, start_lon)
        end_node = nearest_node_id(graph, end_lat, end_lon)
        route_nodes = nx.shortest_path(graph, start_node, end_node, weight="length")
        route_payload = build_route_response(graph, route_nodes, include_cost_breakdown=False)
        routes.append(
            {
                "name": anchor["name"],
                "severity": anchor["severity"],
                "path": route_payload["path"],
            }
        )

    return routes


def to_local_xy(lat, lon, origin_lat):
    meters_per_deg_lat = 111320
    meters_per_deg_lon = 111320 * math.cos(math.radians(origin_lat))
    return lon * meters_per_deg_lon, lat * meters_per_deg_lat


def point_to_segment_distance_meters(lat, lon, start_lat, start_lon, end_lat, end_lon):
    origin_lat = (lat + start_lat + end_lat) / 3
    px, py = to_local_xy(lat, lon, origin_lat)
    ax, ay = to_local_xy(start_lat, start_lon, origin_lat)
    bx, by = to_local_xy(end_lat, end_lon, origin_lat)
    abx = bx - ax
    aby = by - ay
    ab_len_sq = abx * abx + aby * aby

    if ab_len_sq == 0:
        return math.hypot(px - ax, py - ay)

    t = max(0, min(1, ((px - ax) * abx + (py - ay) * aby) / ab_len_sq))
    closest_x = ax + t * abx
    closest_y = ay + t * aby
    return math.hypot(px - closest_x, py - closest_y)


def traffic_penalty_for_point(lat, lon):
    penalty = 1.0
    now = time.time()
    if _traffic_routes is None:
        return penalty

    traffic_routes = _traffic_routes

    for road in traffic_routes:
        if len(road["path"]) < 2:
            continue

        progress = (now / TRAFFIC_PERIOD_SECONDS + road["severity"]) % 1
        active_segment = progress * (len(road["path"]) - 1)

        for idx in range(len(road["path"]) - 1):
            if abs(idx - active_segment) > 0.9:
                continue

            start = road["path"][idx]
            end = road["path"][idx + 1]
            distance = point_to_segment_distance_meters(
                lat, lon, start["lat"], start["lon"], end["lat"], end["lon"]
            )

            if distance <= 24:
                segment_strength = max(0.35, 1 - abs(idx - active_segment))
                penalty = max(penalty, 1 + road["severity"] * segment_strength * 3.2)

    return penalty


def rain_penalty_for_point(lat, lon):
    penalty = 1.0

    for zone in RAIN_ZONES:
        center_lat, center_lon = zone["center"]
        distance = haversine_distance(lat, lon, center_lat, center_lon)
        if distance <= zone["radius"]:
            penalty = max(penalty, 2.0)

    return penalty


def edge_weight_with_traffic(from_node, to_node, edge_data):
    from_data = _road_graph.nodes[from_node]
    to_data = _road_graph.nodes[to_node]
    midpoint_lat = (from_data["y"] + to_data["y"]) / 2
    midpoint_lon = (from_data["x"] + to_data["x"]) / 2
    penalty = traffic_penalty_for_point(midpoint_lat, midpoint_lon)
    penalty *= rain_penalty_for_point(midpoint_lat, midpoint_lon)

    if "length" in edge_data:
        return edge_data.get("length", 0.0) * penalty

    best_length = min(
        data.get("length", float("inf"))
        for data in edge_data.values()
    )
    return best_length * penalty


def edge_geometry_coordinates(graph, from_node, to_node, edge_data):
    geometry = edge_data.get("geometry")

    if geometry is None:
        start = graph.nodes[from_node]
        end = graph.nodes[to_node]
        return [
            {"lat": start["y"], "lon": start["x"]},
            {"lat": end["y"], "lon": end["x"]},
        ]

    return [{"lat": lat, "lon": lon} for lon, lat in geometry.coords]


def build_route_response(graph, route_nodes, include_cost_breakdown=True):
    route_path = []
    route_distance = 0.0
    traffic_cost = 0.0
    rain_cost = 0.0

    for idx in range(len(route_nodes) - 1):
        from_node = route_nodes[idx]
        to_node = route_nodes[idx + 1]
        edge_options = graph.get_edge_data(from_node, to_node)
        edge_data = min(
            edge_options.values(),
            key=lambda item: item.get("length", float("inf")),
        )
        segment_points = edge_geometry_coordinates(graph, from_node, to_node, edge_data)

        if route_path and segment_points:
            segment_points = segment_points[1:]

        route_path.extend(segment_points)
        edge_length = edge_data.get("length", 0.0)
        route_distance += edge_length

        if include_cost_breakdown:
            from_data = graph.nodes[from_node]
            to_data = graph.nodes[to_node]
            midpoint_lat = (from_data["y"] + to_data["y"]) / 2
            midpoint_lon = (from_data["x"] + to_data["x"]) / 2
            traffic_penalty = traffic_penalty_for_point(midpoint_lat, midpoint_lon)
            rain_penalty = rain_penalty_for_point(midpoint_lat, midpoint_lon)
            traffic_cost += edge_length * max(0, traffic_penalty - 1)
            rain_cost += edge_length * max(0, rain_penalty - 1)

    response = {
        "path": route_path,
        "distance": route_distance,
    }

    if include_cost_breakdown:
        response["costBreakdown"] = {
            "baseDistance": round(route_distance, 1),
            "trafficPenalty": round(traffic_cost, 1),
            "rainPenalty": round(rain_cost, 1),
            "totalCost": round(route_distance + traffic_cost + rain_cost, 1),
        }

    return response


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/traffic")
def traffic():
    now = time.time()
    roads = []

    _, _, traffic_routes = get_road_graph()

    for road in traffic_routes:
        if len(road["path"]) < 2:
            roads.append({"name": road["name"], "segments": []})
            continue

        progress = (now / TRAFFIC_PERIOD_SECONDS + road["severity"]) % 1
        active_segment = progress * (len(road["path"]) - 1)
        segments = []

        for idx in range(len(road["path"]) - 1):
            strength = max(0.0, 1 - abs(idx - active_segment))
            if strength < 0.15:
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
                    "multiplier": 2.0,
                }
                for zone in RAIN_ZONES
            ]
        }
    )


@app.route("/api/route")
def route():
    try:
        from_lat = validate_coordinate(request.args.get("fromLat"), "fromLat")
        from_lon = validate_coordinate(request.args.get("fromLon"), "fromLon")
        to_lat = validate_coordinate(request.args.get("toLat"), "toLat")
        to_lon = validate_coordinate(request.args.get("toLon"), "toLon")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if from_lat == to_lat and from_lon == to_lon:
        return jsonify(
            {
                "path": [{"lat": from_lat, "lon": from_lon}],
                "distance": 0,
            }
        )

    try:
        graph, projected_graph, _ = get_road_graph()
        start_node = nearest_node_id(graph, from_lat, from_lon)
        end_node = nearest_node_id(graph, to_lat, to_lon)
        route_nodes = nx.shortest_path(graph, start_node, end_node, weight=edge_weight_with_traffic)
        payload = build_route_response(graph, route_nodes)
        payload["start"] = {"lat": graph.nodes[start_node]["y"], "lon": graph.nodes[start_node]["x"]}
        payload["end"] = {"lat": graph.nodes[end_node]["y"], "lon": graph.nodes[end_node]["x"]}
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
        graph, projected_graph, _ = get_road_graph()
        node_id = nearest_node_id(graph, lat, lon)
        return jsonify(
            {
                "lat": graph.nodes[node_id]["y"],
                "lon": graph.nodes[node_id]["x"],
            }
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    print("Starting Hanoi Delivery Robots...")
    print("Loading OpenStreetMap road graph for Hoan Kiem...")
    get_road_graph()
    print("Open http://127.0.0.1:5000 in your browser")
    app.run(host="127.0.0.1", port=5000)
