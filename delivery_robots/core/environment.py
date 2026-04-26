import math
import time

from ..utils.geo import haversine_distance, point_to_segment_distance_meters


def get_simulation_time(state):
    elapsed_real = time.time() - state["simulation_start_time"]
    elapsed_simulated = elapsed_real * state["simulation_speed"]
    sim_seconds_from_midnight = 21600 + elapsed_simulated
    sim_seconds_from_midnight %= 86400
    hours = int(sim_seconds_from_midnight // 3600)
    minutes = int((sim_seconds_from_midnight % 3600) // 60)
    seconds = int(sim_seconds_from_midnight % 60)
    return hours, minutes, seconds


def get_rush_hour_multiplier(state):
    hours, minutes, _ = get_simulation_time(state)
    current_hour = hours + minutes / 60.0

    for rush in state["rush_hours"]:
        if rush["start"] <= current_hour < rush["end"]:
            progress = (current_hour - rush["start"]) / (rush["end"] - rush["start"])
            multiplier = 1 + (rush["multiplier"] - 1) * math.sin(progress * math.pi)
            return multiplier, rush["name"]

    return 1.0, "Normal"


def traffic_penalty_for_point(state, lat, lon):
    penalty = 1.0
    now = time.time()
    if state["traffic_routes"] is None and not state["dynamic_traffic_routes"]:
        return penalty

    traffic_routes = list(state["traffic_routes"] or [])
    with state["dynamic_traffic_lock"]:
        traffic_routes.extend(state["dynamic_traffic_routes"])

    rush_multiplier, _ = get_rush_hour_multiplier(state)
    penalty *= rush_multiplier

    for road in traffic_routes:
        if len(road["path"]) < 2:
            continue

        progress = (now / state["traffic_period_seconds"] + road["severity"]) % 1
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


def rain_penalty_for_point(state, lat, lon):
    penalty = 1.0
    for zone in state["rain_zones"]:
        center_lat, center_lon = zone["center"]
        distance = haversine_distance(lat, lon, center_lat, center_lon)
        if distance <= zone["radius"]:
            penalty = max(penalty, 1 + zone.get("severity", 1.0))
    return penalty


def obstacle_penalty_for_point(state, lat, lon):
    penalty = 1.0

    with state["obstacles_lock"]:
        obstacles = list(state["obstacles"])

    for obstacle in obstacles:
        center_lat, center_lon = obstacle["center"]
        distance = haversine_distance(lat, lon, center_lat, center_lon)
        radius = obstacle["radius"]
        if distance > radius:
            continue
        closeness = 1 - (distance / radius if radius else 1)
        severity = obstacle.get("severity", 10.0)
        penalty = max(penalty, 1 + (severity / 10.0) * max(0.2, closeness))

    return penalty


def edge_weight_with_traffic(state, from_node, to_node, edge_data):
    from_data = state["road_graph"].nodes[from_node]
    to_data = state["road_graph"].nodes[to_node]
    midpoint_lat = (from_data["y"] + to_data["y"]) / 2
    midpoint_lon = (from_data["x"] + to_data["x"]) / 2

    penalty = traffic_penalty_for_point(state, midpoint_lat, midpoint_lon)
    penalty *= rain_penalty_for_point(state, midpoint_lat, midpoint_lon)
    penalty *= obstacle_penalty_for_point(state, midpoint_lat, midpoint_lon)

    if "length" in edge_data:
        return edge_data.get("length", 0.0) * penalty

    best_length = min(data.get("length", float("inf")) for data in edge_data.values())
    return best_length * penalty
