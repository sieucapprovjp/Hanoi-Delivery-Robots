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

# Simulation clock and rush hour configuration
_simulation_start_time = time.time()
_simulation_speed = 60  # 1 real second = 1 simulation minute (60x speed)
RUSH_HOURS = [
    {"name": "Morning Rush", "start": 7, "end": 9, "multiplier": 2.5},
    {"name": "Lunch Traffic", "start": 11, "end": 13, "multiplier": 1.3},
    {"name": "Evening Rush", "start": 17, "end": 19, "multiplier": 3.0},
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


def get_simulation_time():
    """Returns simulated time based on real elapsed time and simulation speed."""
    elapsed_real = time.time() - _simulation_start_time
    elapsed_simulated = elapsed_real * _simulation_speed
    # Start at 6:00 AM (21600 seconds from midnight)
    sim_seconds_from_midnight = 21600 + elapsed_simulated
    sim_seconds_from_midnight = sim_seconds_from_midnight % 86400  # Wrap at 24h
    hours = int(sim_seconds_from_midnight // 3600)
    minutes = int((sim_seconds_from_midnight % 3600) // 60)
    seconds = int(sim_seconds_from_midnight % 60)
    return hours, minutes, seconds


def get_rush_hour_multiplier():
    """Returns traffic multiplier based on current simulated time."""
    hours, minutes, seconds = get_simulation_time()
    current_hour = hours + minutes / 60.0
    
    for rush in RUSH_HOURS:
        if rush["start"] <= current_hour < rush["end"]:
            # Smooth transition: ramp up at start, ramp down at end
            progress = (current_hour - rush["start"]) / (rush["end"] - rush["start"])
            # Peak in the middle
            multiplier = 1 + (rush["multiplier"] - 1) * math.sin(progress * math.pi)
            return multiplier, rush["name"]
    
    return 1.0, "Normal"


def traffic_penalty_for_point(lat, lon):
    penalty = 1.0
    now = time.time()
    if _traffic_routes is None:
        return penalty

    traffic_routes = _traffic_routes
    
    # Apply rush hour multiplier
    rush_multiplier, _ = get_rush_hour_multiplier()
    penalty *= rush_multiplier

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


@app.route("/api/clock")
def get_clock():
    """Get current simulation time and rush hour status."""
    hours, minutes, seconds = get_simulation_time()
    rush_multiplier, rush_name = get_rush_hour_multiplier()
    
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
            "schedule": RUSH_HOURS,
        },
        "simulationSpeed": _simulation_speed,
    })


@app.route("/api/route")
def route():
    start_t = time.time()
    try:
        from_lat = validate_coordinate(request.args.get("fromLat"), "fromLat")
        from_lon = validate_coordinate(request.args.get("fromLon"), "fromLon")
        to_lat = validate_coordinate(request.args.get("toLat"), "toLat")
        to_lon = validate_coordinate(request.args.get("toLon"), "toLon")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if from_lat == to_lat and from_lon == to_lon:
        return jsonify({"path": [{"lat": from_lat, "lon": from_lon}], "distance": 0})

    # Parse robot memory (optional — falls back to empty dict)
    import json
    try:
        road_memory = json.loads(request.args.get("memory", "{}"))
    except Exception:
        road_memory = {}

    try:
        graph, projected_graph, _ = get_road_graph()
        start_node = nearest_node_id(graph, from_lat, from_lon)
        end_node = nearest_node_id(graph, to_lat, to_lon)

        def edge_weight_with_memory(from_node, to_node, edge_data):
            base = edge_weight_with_traffic(from_node, to_node, edge_data)
            # Look up memory penalty for this segment
            fn = graph.nodes[from_node]
            tn = graph.nodes[to_node]
            key = f"{fn['y']:.4f},{fn['x']:.4f}->{tn['y']:.4f},{tn['x']:.4f}"
            memory_penalty = road_memory.get(key, 1.0)
            return base * memory_penalty

        weight_fn = edge_weight_with_memory if road_memory else edge_weight_with_traffic
        route_nodes = nx.shortest_path(graph, start_node, end_node, weight=weight_fn)
        payload = build_route_response(graph, route_nodes)
        payload["start"] = {"lat": graph.nodes[start_node]["y"], "lon": graph.nodes[start_node]["x"]}
        payload["end"] = {"lat": graph.nodes[end_node]["y"], "lon": graph.nodes[end_node]["x"]}
        
        # Track metrics
        calc_time = (time.time() - start_t) * 1000
        _metrics["totalCalculations"] += 1
        _metrics["lastCalculationTime"] = calc_time
        _metrics["minCalculationTime"] = min(_metrics["minCalculationTime"], calc_time)
        _metrics["maxCalculationTime"] = max(_metrics["maxCalculationTime"], calc_time)
        _metrics["totalCalculationTime"] += calc_time
        _metrics["avgCalculationTime"] = _metrics["totalCalculationTime"] / _metrics["totalCalculations"]
        nodes_explored = len(route_nodes) * 5  # approximate
        _metrics["totalNodesExplored"] += nodes_explored
        _metrics["avgNodesExplored"] = _metrics["totalNodesExplored"] / _metrics["totalCalculations"]
        _metrics["pathLengths"].append(len(route_nodes))
        if len(_metrics["pathLengths"]) > 100:
            _metrics["pathLengths"] = _metrics["pathLengths"][-100:]
        
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


# ========== Rain/Weather Controls ==========
@app.route("/api/rain/list")
def list_rain():
    return jsonify({"rainZones": [{"name": z["name"], "center": {"lat": z["center"][0], "lon": z["center"][1]}, "radius": z["radius"]} for z in RAIN_ZONES]})

@app.route("/api/rain/add", methods=["POST"])
def add_rain():
    global RAIN_ZONES
    d = request.get_json(silent=True) or {}
    lat, lon, radius = float(d.get("lat",0)), float(d.get("lon",0)), float(d.get("radius",150))
    RAIN_ZONES.append({"name": f"Rain {len(RAIN_ZONES)+1}", "center": (lat,lon), "radius": radius, "severity": 1.0})
    return jsonify({"message": "Added", "rainZone": {"name": f"Rain {len(RAIN_ZONES)}", "center": {"lat": lat, "lon": lon}, "radius": radius}})

@app.route("/api/rain/randomize", methods=["POST"])
def randomize_rain():
    global RAIN_ZONES
    import random
    d = request.get_json(silent=True) or {}
    count = int(d.get("count", 3))
    RAIN_ZONES = [{"name": f"Rain {i+1}", "center": (random.uniform(21.0180,21.0380), random.uniform(105.8430,105.8650)), "radius": random.uniform(float(d.get("minRadius",100)), float(d.get("maxRadius",200))), "severity": 1.0} for i in range(count)]
    return jsonify({"message": f"Added {count}", "rainZones": [{"name": z["name"], "center": {"lat": z["center"][0], "lon": z["center"][1]}, "radius": z["radius"]} for z in RAIN_ZONES]})

@app.route("/api/rain/clear", methods=["POST"])
def clear_rain():
    global RAIN_ZONES
    RAIN_ZONES = []
    return jsonify({"message": "Cleared"})


# ========== Traffic Controls ==========
_dynamic_traffic_lock = threading.Lock()
_dynamic_traffic_routes = []

@app.route("/api/traffic/list")
def list_traffic_routes():
    with _dynamic_traffic_lock:
        return jsonify({"routes": _dynamic_traffic_routes[:]})

@app.route("/api/traffic/randomize", methods=["POST"])
def randomize_traffic():
    global _dynamic_traffic_routes
    import random, json
    d = request.get_json(silent=True) or {}
    count = int(d.get("count", 3))
    routes = []
    for i in range(count):
        routes.append({"name": f"Traffic {i+1}", "severity": random.uniform(0.4,0.9), "path": [{"lat": random.uniform(21.0200,21.0350), "lon": random.uniform(105.8450,105.8600)} for _ in range(10)]})
    with _dynamic_traffic_lock:
        _dynamic_traffic_routes = routes
    return jsonify({"message": f"Added {count}", "routes": routes})

@app.route("/api/traffic/clear", methods=["POST"])
def clear_traffic():
    global _dynamic_traffic_routes
    with _dynamic_traffic_lock:
        _dynamic_traffic_routes = []
    return jsonify({"message": "Cleared"})


# ========== Obstacles Controls ==========
_obstacles_lock = threading.Lock()
_obstacles = []

@app.route("/api/obstacle/list")
def list_obstacles():
    with _obstacles_lock:
        return jsonify({"obstacles": [{"name": o["name"], "center": {"lat": o["center"][0], "lon": o["center"][1]}, "radius": o["radius"], "severity": o["severity"], "type": o["type"]} for o in _obstacles]})

@app.route("/api/obstacle/add", methods=["POST"])
def add_obstacle():
    global _obstacles
    d = request.get_json(silent=True) or {}
    lat, lon = float(d.get("lat",0)), float(d.get("lon",0))
    o = {"name": f"Obstacle {len(_obstacles)+1}", "center": (lat,lon), "radius": float(d.get("radius",80)), "severity": float(d.get("severity",10)), "type": d.get("type","roadblock")}
    with _obstacles_lock:
        _obstacles.append(o)
    return jsonify({"message": "Added", "obstacle": {"name": o["name"], "center": {"lat": lat, "lon": lon}, "radius": o["radius"], "severity": o["severity"], "type": o["type"]}})

@app.route("/api/obstacle/randomize", methods=["POST"])
def randomize_obstacles():
    global _obstacles
    import random
    d = request.get_json(silent=True) or {}
    count = int(d.get("count", 3))
    types = ["roadblock","construction","accident"]
    with _obstacles_lock:
        _obstacles = [{"name": f"Obs {i+1}", "center": (random.uniform(21.0180,21.0380), random.uniform(105.8430,105.8650)), "radius": random.uniform(50,120), "severity": random.uniform(5,50), "type": random.choice(types)} for i in range(count)]
    return jsonify({"message": f"Added {count}", "obstacles": [{"name": o["name"], "center": {"lat": o["center"][0], "lon": o["center"][1]}, "radius": o["radius"], "severity": o["severity"], "type": o["type"]} for o in _obstacles]})

@app.route("/api/obstacle/clear", methods=["POST"])
def clear_obstacles():
    global _obstacles
    with _obstacles_lock:
        _obstacles = []
    return jsonify({"message": "Cleared"})


# ========== Metrics ==========
_metrics = {"totalCalculations": 0, "avgCalculationTime": 0, "lastCalculationTime": 0, "minCalculationTime": 999, "maxCalculationTime": 0, "avgNodesExplored": 0, "totalCalculationTime": 0, "totalNodesExplored": 0, "pathLengths": []}

@app.route("/api/metrics")
def get_metrics():
    avg_path = sum(_metrics["pathLengths"])/len(_metrics["pathLengths"]) if _metrics["pathLengths"] else 0
    return jsonify({
        "pathfinding": {
            "totalCalculations": _metrics["totalCalculations"],
            "avgCalculationTime": round(_metrics["avgCalculationTime"],2),
            "lastCalculationTime": round(_metrics["lastCalculationTime"],2),
            "minCalculationTime": round(_metrics["minCalculationTime"],2) if _metrics["minCalculationTime"]<999 else 0,
            "maxCalculationTime": round(_metrics["maxCalculationTime"],2),
            "avgNodesExplored": round(_metrics["avgNodesExplored"],1),
            "avgPathLength": round(avg_path,1),
        },
        "graph": {"totalNodes": _road_graph.number_of_nodes() if _road_graph else 0, "totalEdges": _road_graph.number_of_edges() if _road_graph else 0},
        "activeFactors": {"rainZones": len(RAIN_ZONES), "trafficRoutes": len(_dynamic_traffic_routes), "obstacles": len(_obstacles)}
    })


@app.route("/api/astep")
def astep_demo():
    """Visual A* step-by-step demo for presentation."""
    import heapq
    start_t = time.time()
    
    try:
        from_lat = float(request.args.get("fromLat", 21.0285))
        from_lon = float(request.args.get("fromLon", 105.8542))
        to_lat = float(request.args.get("toLat", 21.0355))
        to_lon = float(request.args.get("toLon", 105.8516))
    except:
        return jsonify({"error": "Invalid coords"}), 400
    
    graph, _, _ = get_road_graph()
    start_node = nearest_node_id(graph, from_lat, from_lon)
    end_node = nearest_node_id(graph, to_lat, to_lon)
    
    # A* with step tracking
    open_set = [(0, start_node)]
    came_from = {}
    g_score = {start_node: 0}
    h_score = {start_node: haversine_distance(
        graph.nodes[start_node]["y"], graph.nodes[start_node]["x"], to_lat, to_lon
    )}
    f_score = {start_node: h_score[start_node]}
    closed_set = set()
    steps = []
    max_steps = 30  # Limit for visualization
    
    step_count = 0
    while open_set and step_count < max_steps:
        step_count += 1
        current_f, current = heapq.heappop(open_set)
        
        if current == end_node:
            # Reconstruct path
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            
            path_coords = [{"lat": graph.nodes[n]["y"], "lon": graph.nodes[n]["x"]} for n in path]
            
            return jsonify({
                "success": True,
                "path": path_coords,
                "pathLength": len(path),
                "steps": steps,
                "totalSteps": step_count,
                "calcTime": round((time.time() - start_t) * 1000, 2),
                "startNode": start_node,
                "endNode": end_node,
                "openSetSize": len(open_set),
                "closedSetSize": len(closed_set),
            })
        
        if current in closed_set:
            continue
        closed_set.add(current)
        
        # Record step
        current_lat = graph.nodes[current]["y"]
        current_lon = graph.nodes[current]["x"]
        h_current = haversine_distance(current_lat, current_lon, to_lat, to_lon)
        
        steps.append({
            "step": step_count,
            "currentNode": current,
            "currentCoords": {"lat": round(current_lat, 5), "lon": round(current_lon, 5)},
            "g": round(g_score.get(current, 0), 1),
            "h": round(h_current, 1),
            "f": round(f_score.get(current, 0), 1),
            "openSetSize": len(open_set),
            "closedSetSize": len(closed_set),
            "formula": f"f(n) = {g_score.get(current, 0):.0f} + {h_current:.0f} = {f_score.get(current, 0):.0f}"
        })
        
        for neighbor in graph.neighbors(current):
            if neighbor in closed_set:
                continue
            
            edge_data = graph[current][neighbor]
            edge_length = min(d.get("length", 10) for d in edge_data.values())
            
            # Apply penalties
            mid_lat = (graph.nodes[current]["y"] + graph.nodes[neighbor]["y"]) / 2
            mid_lon = (graph.nodes[current]["x"] + graph.nodes[neighbor]["x"]) / 2
            traffic_pen = traffic_penalty_for_point(mid_lat, mid_lon)
            rain_pen = rain_penalty_for_point(mid_lat, mid_lon)
            obs_pen = obstacle_penalty_for_point(mid_lat, mid_lon)
            total_weight = edge_length * traffic_pen * rain_pen * obs_pen
            
            tentative_g = g_score[current] + total_weight
            
            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                h_neighbor = haversine_distance(
                    graph.nodes[neighbor]["y"], graph.nodes[neighbor]["x"], to_lat, to_lon
                )
                h_score[neighbor] = h_neighbor
                f_score[neighbor] = tentative_g + h_neighbor
                heapq.heappush(open_set, (f_score[neighbor], neighbor))
    
    return jsonify({"success": False, "steps": steps, "totalSteps": step_count, "calcTime": round((time.time() - start_t) * 1000, 2)})


if __name__ == "__main__":
    print("Starting Hanoi Delivery Robots...")
    print("Loading OpenStreetMap road graph for Hoan Kiem...")
    get_road_graph()
    print("Open http://127.0.0.1:5000 in your browser")
    app.run(host="127.0.0.1", port=5000)
