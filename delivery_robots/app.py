from flask import Flask, jsonify, render_template, request
import math
import threading
import time
import random

import networkx as nx


app = Flask(__name__)

GRAPH_CENTER = (21.0285, 105.8542)
GRAPH_DIST_METERS = 2200
GRAPH_NETWORK_TYPE = "bike"

# Hoan Kiem district boundaries (approximate bounding box)
HOAN_KIEM_BOUNDS = {
    "north": 21.0380,
    "south": 21.0180,
    "east": 105.8650,
    "west": 105.8430,
}

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

# Dynamic traffic and rain zones - thread-safe management
_rain_zones_lock = threading.Lock()
_traffic_lock = threading.Lock()
_obstacles_lock = threading.Lock()
TRAFFIC_PERIOD_SECONDS = 36
DYNAMIC_TRAFFIC_ROUTES = []  # Will be populated from TRAFFIC_ANCHORS
RAIN_ZONES = [
    {"name": "South Lake Edge", "center": (21.0248, 105.8532), "radius": 155, "severity": 1.0},
    {"name": "East Corridor", "center": (21.0284, 105.8562), "radius": 140, "severity": 1.0},
]
DYNAMIC_OBSTACLES = []  # Roadblocks, construction zones, accidents

_graph_lock = threading.Lock()
_road_graph = None
_projected_road_graph = None
_traffic_routes = None
_ox = None

# Pathfinding metrics tracking
_pathfinding_metrics_lock = threading.Lock()
_pathfinding_metrics = {
    "totalCalculations": 0,
    "avgCalculationTime": 0,
    "lastCalculationTime": 0,
    "minCalculationTime": float('inf'),
    "maxCalculationTime": 0,
    "avgNodesExplored": 0,
    "totalNodesExplored": 0,
    "pathLengths": [],
    "algorithmDecisions": [],
}


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
            # Use bounding box for Hoan Kiem district to optimize resource usage
            print("Loading OpenStreetMap road graph for Hoan Kiem district (optimized)...")
            bbox = (
                HOAN_KIEM_BOUNDS["west"],
                HOAN_KIEM_BOUNDS["south"],
                HOAN_KIEM_BOUNDS["east"],
                HOAN_KIEM_BOUNDS["north"],
            )
            _road_graph = _ox.graph_from_bbox(
                bbox,
                network_type=GRAPH_NETWORK_TYPE,
                simplify=True,
            )
            _projected_road_graph = _ox.project_graph(_road_graph)
            _traffic_routes = build_traffic_routes(_road_graph)
            print(f"Loaded graph with {_road_graph.number_of_nodes()} nodes and {_road_graph.number_of_edges()} edges")

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
    global DYNAMIC_TRAFFIC_ROUTES
    routes = []

    for anchor in TRAFFIC_ANCHORS:
        start_lat, start_lon = anchor["start"]
        end_lat, end_lon = anchor["end"]
        start_node = nearest_node_id(graph, start_lat, start_lon)
        end_node = nearest_node_id(graph, end_lat, end_lon)
        try:
            route_nodes = nx.shortest_path(graph, start_node, end_node, weight="length")
            route_payload = build_route_response(graph, route_nodes, include_cost_breakdown=False)
            routes.append(
                {
                    "name": anchor["name"],
                    "severity": anchor["severity"],
                    "path": route_payload["path"],
                }
            )
        except Exception:
            pass  # Skip routes that can't be computed
    
    with _traffic_lock:
        DYNAMIC_TRAFFIC_ROUTES = routes[:]
    
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
    _, _, static_routes = get_road_graph()
    
    with _traffic_lock:
        dynamic_routes = DYNAMIC_TRAFFIC_ROUTES[:]
    
    all_routes = static_routes + dynamic_routes

    for road in all_routes:
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


def obstacle_penalty_for_point(lat, lon):
    """Returns a high penalty if point is inside an obstacle zone."""
    penalty = 1.0
    
    with _obstacles_lock:
        obstacles = DYNAMIC_OBSTACLES[:]
    
    for obstacle in obstacles:
        center_lat, center_lon = obstacle["center"]
        distance = haversine_distance(lat, lon, center_lat, center_lon)
        if distance <= obstacle["radius"]:
            penalty = max(penalty, obstacle.get("severity", 10.0))
    
    return penalty


def edge_weight_with_traffic(from_node, to_node, edge_data):
    from_data = _road_graph.nodes[from_node]
    to_data = _road_graph.nodes[to_node]
    midpoint_lat = (from_data["y"] + to_data["y"]) / 2
    midpoint_lon = (from_data["x"] + to_data["x"]) / 2
    penalty = traffic_penalty_for_point(midpoint_lat, midpoint_lon)
    penalty *= rain_penalty_for_point(midpoint_lat, midpoint_lon)
    penalty *= obstacle_penalty_for_point(midpoint_lat, midpoint_lon)

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


@app.route("/rain-control")
def rain_control():
    return render_template("rain_control.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/traffic")
def traffic():
    now = time.time()
    roads = []

    _, _, traffic_routes = get_road_graph()
    
    with _traffic_lock:
        dynamic_routes = DYNAMIC_TRAFFIC_ROUTES[:]
    
    # Combine static and dynamic routes
    all_routes = traffic_routes + dynamic_routes

    for road in all_routes:
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
            ],
            "hoanKiemBounds": HOAN_KIEM_BOUNDS,
        }
    )


@app.route("/api/route")
def route():
    start_time = time.time()
    
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
                "metrics": {"calculationTime": 0, "nodesExplored": 0}
            }
        )

    try:
        graph, projected_graph, _ = get_road_graph()
        start_node = nearest_node_id(graph, from_lat, from_lon)
        end_node = nearest_node_id(graph, to_lat, to_lon)
        
        # Track nodes explored (approximation)
        nodes_explored = 0
        class MetricsWrapper:
            def __init__(self, weight_func):
                self.weight_func = weight_func
                self.nodes_explored = 0
            
            def __call__(self, u, v, d):
                self.nodes_explored += 1
                return self.weight_func(u, v, d)
        
        weight_wrapper = MetricsWrapper(edge_weight_with_traffic)
        route_nodes = nx.shortest_path(graph, start_node, end_node, weight=weight_wrapper)
        nodes_explored = weight_wrapper.nodes_explored
        
        payload = build_route_response(graph, route_nodes)
        payload["start"] = {"lat": graph.nodes[start_node]["y"], "lon": graph.nodes[start_node]["x"]}
        payload["end"] = {"lat": graph.nodes[end_node]["y"], "lon": graph.nodes[end_node]["x"]}
        
        # Calculate time
        calc_time = (time.time() - start_time) * 1000  # Convert to ms
        
        # Update metrics
        with _pathfinding_metrics_lock:
            metrics = _pathfinding_metrics
            metrics["totalCalculations"] += 1
            metrics["lastCalculationTime"] = calc_time
            metrics["minCalculationTime"] = min(metrics["minCalculationTime"], calc_time)
            metrics["maxCalculationTime"] = max(metrics["maxCalculationTime"], calc_time)
            metrics["totalCalculationTime"] = metrics.get("totalCalculationTime", 0) + calc_time
            metrics["avgCalculationTime"] = metrics["totalCalculationTime"] / metrics["totalCalculations"]
            metrics["totalNodesExplored"] += nodes_explored
            metrics["avgNodesExplored"] = metrics["totalNodesExplored"] / metrics["totalCalculations"]
            metrics["pathLengths"].append(len(route_nodes))
            if len(metrics["pathLengths"]) > 100:
                metrics["pathLengths"] = metrics["pathLengths"][-100:]
        
        payload["metrics"] = {
            "calculationTime": round(calc_time, 2),
            "nodesExplored": nodes_explored,
            "pathLength": len(route_nodes),
        }
        
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


@app.route("/api/rain/randomize", methods=["POST"])
def randomize_rain_zones():
    """Generate random rain zones within Hoan Kiem district bounds."""
    global RAIN_ZONES
    
    try:
        data = request.get_json(silent=True) or {}
        num_zones = int(data.get("count", 3))
        min_radius = int(data.get("minRadius", 100))
        max_radius = int(data.get("maxRadius", 200))
        
        if num_zones < 1 or num_zones > 10:
            return jsonify({"error": "Count must be between 1 and 10"}), 400
        
        with _rain_zones_lock:
            RAIN_ZONES = []
            for i in range(num_zones):
                lat = random.uniform(HOAN_KIEM_BOUNDS["south"], HOAN_KIEM_BOUNDS["north"])
                lon = random.uniform(HOAN_KIEM_BOUNDS["west"], HOAN_KIEM_BOUNDS["east"])
                radius = random.uniform(min_radius, max_radius)
                RAIN_ZONES.append({
                    "name": f"Rain Zone {i+1}",
                    "center": (lat, lon),
                    "radius": radius,
                    "severity": 1.0,
                })
        
        return jsonify({
            "message": f"Generated {num_zones} random rain zones",
            "rainZones": [
                {
                    "name": zone["name"],
                    "center": {"lat": zone["center"][0], "lon": zone["center"][1]},
                    "radius": zone["radius"],
                }
                for zone in RAIN_ZONES
            ]
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/rain/add", methods=["POST"])
def add_rain_zone():
    """Add a custom rain zone at specified coordinates."""
    global RAIN_ZONES
    
    try:
        data = request.get_json(silent=True) or {}
        lat = float(data.get("lat"))
        lon = float(data.get("lon"))
        radius = float(data.get("radius", 150))
        name = data.get("name", "Custom Rain Zone")
        
        # Validate coordinates are within Hoan Kiem bounds
        if not (HOAN_KIEM_BOUNDS["south"] <= lat <= HOAN_KIEM_BOUNDS["north"] and
                HOAN_KIEM_BOUNDS["west"] <= lon <= HOAN_KIEM_BOUNDS["east"]):
            return jsonify({
                "error": "Coordinates outside Hoan Kiem district bounds",
                "bounds": HOAN_KIEM_BOUNDS
            }), 400
        
        with _rain_zones_lock:
            RAIN_ZONES.append({
                "name": name,
                "center": (lat, lon),
                "radius": radius,
                "severity": 1.0,
            })
        
        return jsonify({
            "message": "Rain zone added successfully",
            "rainZone": {
                "name": name,
                "center": {"lat": lat, "lon": lon},
                "radius": radius,
            }
        })
    except (TypeError, ValueError) as exc:
        return jsonify({"error": "Invalid coordinates. Provide lat and lon as numbers"}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/rain/clear", methods=["POST"])
def clear_rain_zones():
    """Clear all rain zones."""
    global RAIN_ZONES
    
    with _rain_zones_lock:
        RAIN_ZONES = []
    
    return jsonify({"message": "All rain zones cleared"})


@app.route("/api/rain/list", methods=["GET"])
def list_rain_zones():
    """List all current rain zones."""
    return jsonify({
        "rainZones": [
            {
                "name": zone["name"],
                "center": {"lat": zone["center"][0], "lon": zone["center"][1]},
                "radius": zone["radius"],
                "severity": zone["severity"],
            }
            for zone in RAIN_ZONES
        ]
    })


# ========== Dynamic Traffic Management ==========

@app.route("/api/traffic/add", methods=["POST"])
def add_traffic_route():
    """Add a custom traffic congestion route."""
    global DYNAMIC_TRAFFIC_ROUTES
    
    try:
        data = request.get_json(silent=True) or {}
        start_lat = float(data.get("startLat"))
        start_lon = float(data.get("startLon"))
        end_lat = float(data.get("endLat"))
        end_lon = float(data.get("endLon"))
        severity = float(data.get("severity", 0.7))
        name = data.get("name", "Custom Traffic")
        
        if not (0 <= severity <= 1):
            return jsonify({"error": "Severity must be between 0 and 1"}), 400
        
        graph, _, _ = get_road_graph()
        start_node = nearest_node_id(graph, start_lat, start_lon)
        end_node = nearest_node_id(graph, end_lat, end_lon)
        
        try:
            route_nodes = nx.shortest_path(graph, start_node, end_node, weight="length")
            route_payload = build_route_response(graph, route_nodes, include_cost_breakdown=False)
            
            new_route = {
                "name": name,
                "severity": severity,
                "path": route_payload["path"],
            }
            
            with _traffic_lock:
                DYNAMIC_TRAFFIC_ROUTES.append(new_route)
            
            return jsonify({
                "message": "Traffic route added",
                "route": new_route
            })
        except nx.NetworkXNoPath:
            return jsonify({"error": "No path found between these points"}), 400
            
    except (TypeError, ValueError) as exc:
        return jsonify({"error": "Invalid coordinates. Provide numbers"}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/traffic/randomize", methods=["POST"])
def randomize_traffic_routes():
    """Generate random traffic routes within Hoan Kiem."""
    global DYNAMIC_TRAFFIC_ROUTES
    
    try:
        data = request.get_json(silent=True) or {}
        num_routes = int(data.get("count", 3))
        min_severity = float(data.get("minSeverity", 0.4))
        max_severity = float(data.get("maxSeverity", 0.9))
        
        if num_routes < 1 or num_routes > 8:
            return jsonify({"error": "Count must be between 1 and 8"}), 400
        
        graph, _, _ = get_road_graph()
        new_routes = []
        
        for i in range(num_routes):
            # Random start and end points within bounds
            start_lat = random.uniform(HOAN_KIEM_BOUNDS["south"], HOAN_KIEM_BOUNDS["north"])
            start_lon = random.uniform(HOAN_KIEM_BOUNDS["west"], HOAN_KIEM_BOUNDS["east"])
            end_lat = random.uniform(HOAN_KIEM_BOUNDS["south"], HOAN_KIEM_BOUNDS["north"])
            end_lon = random.uniform(HOAN_KIEM_BOUNDS["west"], HOAN_KIEM_BOUNDS["east"])
            severity = random.uniform(min_severity, max_severity)
            
            try:
                start_node = nearest_node_id(graph, start_lat, start_lon)
                end_node = nearest_node_id(graph, end_lat, end_lon)
                route_nodes = nx.shortest_path(graph, start_node, end_node, weight="length")
                route_payload = build_route_response(graph, route_nodes, include_cost_breakdown=False)
                
                new_routes.append({
                    "name": f"Traffic {i+1}",
                    "severity": severity,
                    "path": route_payload["path"],
                })
            except nx.NetworkXNoPath:
                pass  # Skip if no path
        
        with _traffic_lock:
            DYNAMIC_TRAFFIC_ROUTES = new_routes
        
        return jsonify({
            "message": f"Generated {len(new_routes)} random traffic routes",
            "routes": new_routes
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/traffic/clear", methods=["POST"])
def clear_traffic_routes():
    """Clear all dynamic traffic routes."""
    global DYNAMIC_TRAFFIC_ROUTES
    
    with _traffic_lock:
        DYNAMIC_TRAFFIC_ROUTES = []
    
    return jsonify({"message": "All traffic routes cleared"})


@app.route("/api/traffic/list", methods=["GET"])
def list_traffic_routes():
    """List all current traffic routes."""
    with _traffic_lock:
        routes = DYNAMIC_TRAFFIC_ROUTES[:]
    
    return jsonify({"routes": routes})


# ========== Dynamic Obstacles (Roadblocks, Construction, Accidents) ==========

@app.route("/api/obstacle/add", methods=["POST"])
def add_obstacle():
    """Add a dynamic obstacle (roadblock, construction, accident)."""
    global DYNAMIC_OBSTACLES
    
    try:
        data = request.get_json(silent=True) or {}
        lat = float(data.get("lat"))
        lon = float(data.get("lon"))
        radius = float(data.get("radius", 80))
        severity = float(data.get("severity", 10.0))
        obstacle_type = data.get("type", "roadblock")
        name = data.get("name", f"Obstacle {len(DYNAMIC_OBSTACLES)+1}")
        
        if not (0.5 <= severity <= 100):
            return jsonify({"error": "Severity must be between 0.5 and 100"}), 400
        
        if not (HOAN_KIEM_BOUNDS["south"] <= lat <= HOAN_KIEM_BOUNDS["north"] and
                HOAN_KIEM_BOUNDS["west"] <= lon <= HOAN_KIEM_BOUNDS["east"]):
            return jsonify({"error": "Coordinates outside Hoan Kiem bounds"}), 400
        
        obstacle = {
            "name": name,
            "center": (lat, lon),
            "radius": radius,
            "severity": severity,
            "type": obstacle_type,
            "timestamp": time.time(),
        }
        
        with _obstacles_lock:
            DYNAMIC_OBSTACLES.append(obstacle)
        
        return jsonify({
            "message": "Obstacle added",
            "obstacle": {
                "name": obstacle["name"],
                "center": {"lat": lat, "lon": lon},
                "radius": radius,
                "severity": severity,
                "type": obstacle_type,
            }
        })
    except (TypeError, ValueError) as exc:
        return jsonify({"error": "Invalid coordinates"}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/obstacle/randomize", methods=["POST"])
def randomize_obstacles():
    """Generate random obstacles within Hoan Kiem."""
    global DYNAMIC_OBSTACLES
    
    try:
        data = request.get_json(silent=True) or {}
        num_obstacles = int(data.get("count", 3))
        obstacle_types = data.get("types", ["roadblock", "construction", "accident"])
        
        if num_obstacles < 1 or num_obstacles > 10:
            return jsonify({"error": "Count must be between 1 and 10"}), 400
        
        type_icons = {
            "roadblock": "🚧",
            "construction": "🔨",
            "accident": "🚗",
        }
        
        new_obstacles = []
        for i in range(num_obstacles):
            lat = random.uniform(HOAN_KIEM_BOUNDS["south"], HOAN_KIEM_BOUNDS["north"])
            lon = random.uniform(HOAN_KIEM_BOUNDS["west"], HOAN_KIEM_BOUNDS["east"])
            radius = random.uniform(50, 120)
            severity = random.uniform(5.0, 50.0)
            obs_type = random.choice(obstacle_types)
            
            new_obstacles.append({
                "name": f"{type_icons.get(obs_type, '⚠️')} {obs_type.title()} {i+1}",
                "center": (lat, lon),
                "radius": radius,
                "severity": severity,
                "type": obs_type,
                "timestamp": time.time(),
            })
        
        with _obstacles_lock:
            DYNAMIC_OBSTACLES = new_obstacles
        
        return jsonify({
            "message": f"Generated {len(new_obstacles)} random obstacles",
            "obstacles": new_obstacles
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/obstacle/clear", methods=["POST"])
def clear_obstacles():
    """Clear all dynamic obstacles."""
    global DYNAMIC_OBSTACLES
    
    with _obstacles_lock:
        DYNAMIC_OBSTACLES = []
    
    return jsonify({"message": "All obstacles cleared"})


@app.route("/api/obstacle/list", methods=["GET"])
def list_obstacles():
    """List all current obstacles."""
    with _obstacles_lock:
        obstacles = DYNAMIC_OBSTACLES[:]
    
    return jsonify({"obstacles": obstacles})


@app.route("/api/metrics", methods=["GET"])
def get_metrics():
    """Get pathfinding and algorithm performance metrics."""
    with _pathfinding_metrics_lock:
        metrics = _pathfinding_metrics.copy()
    
    # Calculate average path length
    avg_path_length = 0
    if metrics.get("pathLengths"):
        avg_path_length = sum(metrics["pathLengths"]) / len(metrics["pathLengths"])
    
    return jsonify({
        "pathfinding": {
            "totalCalculations": metrics.get("totalCalculations", 0),
            "avgCalculationTime": round(metrics.get("avgCalculationTime", 0), 2),
            "lastCalculationTime": round(metrics.get("lastCalculationTime", 0), 2),
            "minCalculationTime": round(metrics.get("minCalculationTime", 0) if metrics.get("minCalculationTime") != float('inf') else 0, 2),
            "maxCalculationTime": round(metrics.get("maxCalculationTime", 0), 2),
            "avgNodesExplored": round(metrics.get("avgNodesExplored", 0), 1),
            "avgPathLength": round(avg_path_length, 1),
        },
        "graph": {
            "totalNodes": _road_graph.number_of_nodes() if _road_graph else 0,
            "totalEdges": _road_graph.number_of_edges() if _road_graph else 0,
        },
        "activeFactors": {
            "rainZones": len(RAIN_ZONES),
            "trafficRoutes": len(DYNAMIC_TRAFFIC_ROUTES),
            "obstacles": len(DYNAMIC_OBSTACLES),
        }
    })


if __name__ == "__main__":
    print("Starting Hanoi Delivery Robots...")
    print("Loading OpenStreetMap road graph for Hoan Kiem...")
    get_road_graph()
    print("Open http://127.0.0.1:5000 in your browser")
    app.run(host="127.0.0.1", port=5000)
