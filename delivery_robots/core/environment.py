import math
import time

from ..utils.geo import haversine_distance, point_to_segment_distance_meters
from ..config import (
    DEFAULT_EDGE_LENGTH,
    DEFAULT_OBSTACLE_PENALTY,
    DEFAULT_OBSTACLE_SEVERITY,
    DEFAULT_RAIN_PENALTY,
    DEFAULT_RAIN_SEVERITY,
    DEFAULT_RUSH_HOUR_LABEL,
    DEFAULT_RUSH_HOUR_MULTIPLIER,
    DEFAULT_TRAFFIC_PENALTY,
    OBSTACLE_MIN_CLOSENESS_FACTOR,
    OBSTACLE_SEVERITY_DIVISOR,
    SECONDS_PER_DAY,
    SECONDS_PER_HOUR,
    SECONDS_PER_MINUTE,
    SIMULATION_START_OFFSET_SECONDS,
    TRAFFIC_ACTIVE_SEGMENT_THRESHOLD,
    TRAFFIC_INFLUENCE_RADIUS_METERS,
    TRAFFIC_MIN_SEGMENT_STRENGTH,
    TRAFFIC_SEVERITY_SCALING_FACTOR,
)


def get_simulation_time(state):
    elapsed_real = time.time() - state["simulation_start_time"]
    elapsed_simulated = elapsed_real * state["simulation_speed"]
    sim_seconds_from_midnight = SIMULATION_START_OFFSET_SECONDS + elapsed_simulated
    sim_seconds_from_midnight %= SECONDS_PER_DAY
    hours = int(sim_seconds_from_midnight // SECONDS_PER_HOUR)
    minutes = int((sim_seconds_from_midnight % SECONDS_PER_HOUR) // SECONDS_PER_MINUTE)
    seconds = int(sim_seconds_from_midnight % SECONDS_PER_MINUTE)
    return hours, minutes, seconds


def get_rush_hour_multiplier(state):
    hours, minutes, _ = get_simulation_time(state)
    current_hour = hours + minutes / 60.0

    for rush in state["rush_hours"]:
        if rush["start"] <= current_hour < rush["end"]:
            progress = (current_hour - rush["start"]) / (rush["end"] - rush["start"])
            multiplier = 1 + (rush["multiplier"] - 1) * math.sin(progress * math.pi)
            return multiplier, rush["name"]

    return DEFAULT_RUSH_HOUR_MULTIPLIER, DEFAULT_RUSH_HOUR_LABEL


def _current_traffic_routes(state):
    traffic_routes = list(state["traffic_routes"] or [])
    with state["dynamic_traffic_lock"]:
        traffic_routes.extend(state["dynamic_traffic_routes"])
    return traffic_routes


def _traffic_penalty_for_routes(
    traffic_routes, rush_multiplier, now, traffic_period_seconds, lat, lon
):
    penalty = DEFAULT_TRAFFIC_PENALTY
    if not traffic_routes:
        return penalty

    penalty *= rush_multiplier

    for road in traffic_routes:
        if len(road["path"]) < 2:
            continue

        progress = (now / traffic_period_seconds + road["severity"]) % 1
        active_segment = progress * (len(road["path"]) - 1)

        for idx in range(len(road["path"]) - 1):
            if abs(idx - active_segment) > TRAFFIC_ACTIVE_SEGMENT_THRESHOLD:
                continue
            start = road["path"][idx]
            end = road["path"][idx + 1]
            distance = point_to_segment_distance_meters(
                lat, lon, start["lat"], start["lon"], end["lat"], end["lon"]
            )

            if distance <= TRAFFIC_INFLUENCE_RADIUS_METERS:
                segment_strength = max(TRAFFIC_MIN_SEGMENT_STRENGTH, 1 - abs(idx - active_segment))
                penalty = max(penalty, 1 + road["severity"] * segment_strength * TRAFFIC_SEVERITY_SCALING_FACTOR)

    return penalty


def traffic_penalty_for_point(state, lat, lon):
    rush_multiplier, _ = get_rush_hour_multiplier(state)
    return _traffic_penalty_for_routes(
        _current_traffic_routes(state),
        rush_multiplier,
        time.time(),
        state["traffic_period_seconds"],
        lat,
        lon,
    )


def _rain_penalty_for_zones(rain_zones, lat, lon):
    penalty = DEFAULT_RAIN_PENALTY
    for zone in rain_zones:
        center_lat, center_lon = zone["center"]
        distance = haversine_distance(lat, lon, center_lat, center_lon)
        if distance <= zone["radius"]:
            penalty = max(penalty, 1 + zone.get("severity", DEFAULT_RAIN_SEVERITY))
    return penalty


def rain_penalty_for_point(state, lat, lon):
    return _rain_penalty_for_zones(state["rain_zones"], lat, lon)


def _obstacle_penalty_for_obstacles(obstacles, lat, lon):
    penalty = DEFAULT_OBSTACLE_PENALTY
    for obstacle in obstacles:
        center_lat, center_lon = obstacle["center"]
        distance = haversine_distance(lat, lon, center_lat, center_lon)
        radius = obstacle["radius"]
        if distance > radius:
            continue
        closeness = 1 - (distance / radius if radius else 1)
        severity = obstacle.get("severity", DEFAULT_OBSTACLE_SEVERITY)
        penalty = max(penalty, 1 + (severity / OBSTACLE_SEVERITY_DIVISOR) * max(OBSTACLE_MIN_CLOSENESS_FACTOR, closeness))

    return penalty


def obstacle_penalty_for_point(state, lat, lon):
    with state["obstacles_lock"]:
        obstacles = list(state["obstacles"])
    return _obstacle_penalty_for_obstacles(obstacles, lat, lon)


def build_environment_snapshot(state):
    rush_multiplier, rush_name = get_rush_hour_multiplier(state)
    with state["obstacles_lock"]:
        obstacles = list(state["obstacles"])

    return {
        "road_graph": state["road_graph"],
        "traffic_routes": _current_traffic_routes(state),
        "traffic_period_seconds": state["traffic_period_seconds"],
        "rain_zones": list(state["rain_zones"]),
        "obstacles": obstacles,
        "rush_multiplier": rush_multiplier,
        "rush_name": rush_name,
        "now": time.time(),
    }


def traffic_penalty_for_snapshot(snapshot, lat, lon):
    return _traffic_penalty_for_routes(
        snapshot["traffic_routes"],
        snapshot["rush_multiplier"],
        snapshot["now"],
        snapshot["traffic_period_seconds"],
        lat,
        lon,
    )


def rain_penalty_for_snapshot(snapshot, lat, lon):
    return _rain_penalty_for_zones(snapshot["rain_zones"], lat, lon)


def obstacle_penalty_for_snapshot(snapshot, lat, lon):
    return _obstacle_penalty_for_obstacles(snapshot["obstacles"], lat, lon)


def edge_weight_with_traffic(state, from_node, to_node, edge_data):
    from_data = state["road_graph"].nodes[from_node]
    to_data = state["road_graph"].nodes[to_node]
    midpoint_lat = (from_data["y"] + to_data["y"]) / 2
    midpoint_lon = (from_data["x"] + to_data["x"]) / 2

    penalty = traffic_penalty_for_point(state, midpoint_lat, midpoint_lon)
    penalty *= rain_penalty_for_point(state, midpoint_lat, midpoint_lon)
    penalty *= obstacle_penalty_for_point(state, midpoint_lat, midpoint_lon)

    if "length" in edge_data:
        return edge_data.get("length", DEFAULT_EDGE_LENGTH) * penalty

    best_length = min(data.get("length", float("inf")) for data in edge_data.values())
    return best_length * penalty


def edge_weight_for_snapshot(snapshot, from_node, to_node, edge_data):
    graph = snapshot["road_graph"]
    from_data = graph.nodes[from_node]
    to_data = graph.nodes[to_node]
    midpoint_lat = (from_data["y"] + to_data["y"]) / 2
    midpoint_lon = (from_data["x"] + to_data["x"]) / 2

    penalty = traffic_penalty_for_snapshot(snapshot, midpoint_lat, midpoint_lon)
    penalty *= rain_penalty_for_snapshot(snapshot, midpoint_lat, midpoint_lon)
    penalty *= obstacle_penalty_for_snapshot(snapshot, midpoint_lat, midpoint_lon)

    if "length" in edge_data:
        return edge_data.get("length", DEFAULT_EDGE_LENGTH) * penalty

    best_length = min(data.get("length", float("inf")) for data in edge_data.values())
    return best_length * penalty
