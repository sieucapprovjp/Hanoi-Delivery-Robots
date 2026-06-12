import math
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .graph import GraphSnapshot

from ..utils.geo import haversine_distance, point_to_segment_distance_meters
from .event_bus import Event, EventBus, EventType
from ..config import (
    DEFAULT_EDGE_LENGTH,
    DEFAULT_OBSTACLE_PENALTY,
    DEFAULT_OBSTACLE_SEVERITY,
    DEFAULT_OBSTACLE_TYPE,
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
    DEFAULT_RANDOMIZE_RAIN_COUNT,
    DEFAULT_RAIN_MIN_RADIUS,
    DEFAULT_RAIN_MAX_RADIUS,
    RAIN_ZONE_NAME_PREFIX,
    RANDOM_LAT_MIN,
    RANDOM_LAT_MAX,
    RANDOM_LON_MIN,
    RANDOM_LON_MAX,
    TRAFFIC_ROUTE_NAME_PREFIX,
    DEFAULT_RANDOMIZE_TRAFFIC_COUNT,
    RANDOM_TRAFFIC_SEVERITY_MIN,
    RANDOM_TRAFFIC_SEVERITY_MAX,
    RANDOM_TRAFFIC_LAT_MIN,
    RANDOM_TRAFFIC_LAT_MAX,
    RANDOM_TRAFFIC_LON_MIN,
    RANDOM_TRAFFIC_LON_MAX,
    RANDOM_TRAFFIC_PATH_POINT_COUNT,
    OBSTACLE_NAME_PREFIX,
    OBSTACLE_RANDOMIZE_NAME_PREFIX,
    DEFAULT_RANDOMIZE_OBSTACLE_COUNT,
    RANDOM_OBSTACLE_RADIUS_MIN,
    RANDOM_OBSTACLE_RADIUS_MAX,
    RANDOM_OBSTACLE_SEVERITY_MIN,
    RANDOM_OBSTACLE_SEVERITY_MAX,
    OBSTACLE_TYPES,
)


def get_simulation_time(state):
    elapsed_simulated = state.get("sim_now", 0)
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


def traffic_penalty_for_point(state: dict, lat: float, lon: float) -> float:
    penalty = DEFAULT_TRAFFIC_PENALTY
    now = state.get("snapshot_time", time.time())
    if not state["traffic_routes"] and not state["dynamic_traffic_routes"]:
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
            if abs(idx - active_segment) > TRAFFIC_ACTIVE_SEGMENT_THRESHOLD:
                continue
            start = road["path"][idx]
            end = road["path"][idx + 1]
            distance = point_to_segment_distance_meters(
                lat, lon, start["lat"], start["lon"], end["lat"], end["lon"]
            )

            if distance <= TRAFFIC_INFLUENCE_RADIUS_METERS:
                segment_strength = max(
                    TRAFFIC_MIN_SEGMENT_STRENGTH, 1 - abs(idx - active_segment)
                )
                penalty = max(
                    penalty,
                    1
                    + road["severity"]
                    * segment_strength
                    * TRAFFIC_SEVERITY_SCALING_FACTOR,
                )

    return penalty


def rain_penalty_for_point(state, lat, lon):
    penalty = DEFAULT_RAIN_PENALTY
    for zone in state["rain_zones"]:
        center_lat, center_lon = zone["center"]
        distance = haversine_distance(lat, lon, center_lat, center_lon)
        if distance <= zone["radius"]:
            penalty = max(penalty, 1 + zone.get("severity", DEFAULT_RAIN_SEVERITY))
    return penalty


def obstacle_penalty_for_point(state, lat, lon):
    penalty = DEFAULT_OBSTACLE_PENALTY

    with state["obstacles_lock"]:
        obstacles = list(state["obstacles"])

    for obstacle in obstacles:
        center_lat, center_lon = obstacle["center"]
        distance = haversine_distance(lat, lon, center_lat, center_lon)
        radius = obstacle["radius"]
        if distance > radius:
            continue
        closeness = 1 - (distance / radius if radius else 1)
        severity = obstacle.get("severity", DEFAULT_OBSTACLE_SEVERITY)
        penalty = max(
            penalty,
            1
            + (severity / OBSTACLE_SEVERITY_DIVISOR)
            * max(OBSTACLE_MIN_CLOSENESS_FACTOR, closeness),
        )

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
        return edge_data.get("length", DEFAULT_EDGE_LENGTH) * penalty

    best_length = min(data.get("length", float("inf")) for data in edge_data.values())
    return best_length * penalty


class SnapFactory:
    """Factory for creating GraphSnapshot instances from application state."""

    @staticmethod
    def create_snapshot(state: dict, t: float | None = None) -> "GraphSnapshot":
        """Creates a thread-safe immutable GraphSnapshot frozen at simulated time t.

        Args:
            state (dict): The live application state.
            t (float | None): The simulation timestamp to freeze at. If None,
                defaults to the current simulation time state["sim_now"].

        Returns:
            GraphSnapshot: The frozen graph snapshot.
        """
        import threading
        from .graph import GraphSnapshot

        # Determine snapshot planning times
        sim_time = t if t is not None else state.get("sim_now", 0)
        real_time_val = time.time()

        # Safely copy dynamic objects under their respective locks
        with state["graph_lock"]:
            graph_copy = state["road_graph"].copy()

        with state["obstacles_lock"]:
            obstacles_copy = [dict(obs) for obs in state["obstacles"]]

        with state["dynamic_traffic_lock"]:
            dynamic_traffic_copy = [dict(r) for r in state["dynamic_traffic_routes"]]

        # Non-locked configurations/state lists
        rain_zones_copy = [dict(z) for z in state["rain_zones"]]
        traffic_routes_copy = [dict(r) for r in state["traffic_routes"]]
        rush_hours_copy = [dict(rh) for rh in state["rush_hours"]]

        # Construct the frozen snapshot state dict
        snap_state = {
            "road_graph": graph_copy,
            "rain_zones": rain_zones_copy,
            "obstacles": obstacles_copy,
            "traffic_routes": traffic_routes_copy,
            "dynamic_traffic_routes": dynamic_traffic_copy,
            "rush_hours": rush_hours_copy,
            "sim_now": sim_time,
            "traffic_period_seconds": state.get("traffic_period_seconds", 30),
            "snapshot_time": real_time_val,
            "obstacles_lock": threading.Lock(),
            "dynamic_traffic_lock": threading.Lock(),
            "neighbor_ordering_policy": state.get("neighbor_ordering_policy", "id"),
        }

        return GraphSnapshot(graph_copy, sim_time, snap_state)


def register_environment_subscribers(event_bus: EventBus, state: dict) -> None:
    """Register subscribers on the event bus to handle environment events.

    Args:
        event_bus (EventBus): The event bus instance.
        state (dict): The global application state to be updated.
    """

    def handle_rain_added(event: Event) -> None:
        data = event.data
        name = (
            data.get("name") or f"{RAIN_ZONE_NAME_PREFIX}{len(state['rain_zones']) + 1}"
        )
        state["rain_zones"].append(
            {
                "name": name,
                "center": (data["lat"], data["lon"]),
                "radius": data["radius"],
                "severity": data.get("severity", DEFAULT_RAIN_SEVERITY),
            }
        )

    def handle_rain_cleared(event: Event) -> None:
        state["rain_zones"].clear()

    def handle_rain_randomized(event: Event) -> None:
        import random

        data = event.data
        count = data.get("count", DEFAULT_RANDOMIZE_RAIN_COUNT)
        min_radius = data.get("minRadius", DEFAULT_RAIN_MIN_RADIUS)
        max_radius = data.get("maxRadius", DEFAULT_RAIN_MAX_RADIUS)

        state["rain_zones"].clear()
        for i in range(count):
            state["rain_zones"].append(
                {
                    "name": f"{RAIN_ZONE_NAME_PREFIX}{i + 1}",
                    "center": (
                        random.uniform(RANDOM_LAT_MIN, RANDOM_LAT_MAX),
                        random.uniform(RANDOM_LON_MIN, RANDOM_LON_MAX),
                    ),
                    "radius": random.uniform(min_radius, max_radius),
                    "severity": DEFAULT_RAIN_SEVERITY,
                }
            )

    def handle_traffic_added(event: Event) -> None:
        data = event.data
        with state["dynamic_traffic_lock"]:
            route_name = (
                data.get("name")
                or f"{TRAFFIC_ROUTE_NAME_PREFIX}{len(state['dynamic_traffic_routes']) + 1}"
            )
            route = {
                "name": route_name,
                "severity": data["severity"],
                "path": data["path"],
            }
            state["dynamic_traffic_routes"].append(route)

    def handle_traffic_cleared(event: Event) -> None:
        with state["dynamic_traffic_lock"]:
            state["dynamic_traffic_routes"].clear()

    def handle_traffic_randomized(event: Event) -> None:
        import random

        data = event.data
        count = data.get("count", DEFAULT_RANDOMIZE_TRAFFIC_COUNT)
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
        with state["dynamic_traffic_lock"]:
            state["dynamic_traffic_routes"].clear()
            state["dynamic_traffic_routes"].extend(routes)

    def handle_obstacle_added(event: Event) -> None:
        data = event.data
        with state["obstacles_lock"]:
            name = (
                data.get("name")
                or f"{OBSTACLE_NAME_PREFIX}{len(state['obstacles']) + 1}"
            )
            obstacle = {
                "name": name,
                "center": (data["lat"], data["lon"]),
                "radius": data["radius"],
                "severity": data["severity"],
                "type": data.get("type", DEFAULT_OBSTACLE_TYPE),
            }
            state["obstacles"].append(obstacle)

    def handle_obstacle_cleared(event: Event) -> None:
        with state["obstacles_lock"]:
            state["obstacles"].clear()

    def handle_obstacle_randomized(event: Event) -> None:
        import random

        data = event.data
        count = data.get("count", DEFAULT_RANDOMIZE_OBSTACLE_COUNT)
        new_obstacles = []
        for i in range(count):
            new_obstacles.append(
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
            )
        with state["obstacles_lock"]:
            state["obstacles"].clear()
            state["obstacles"].extend(new_obstacles)

    event_bus.subscribe(EventType.RAIN_ADDED, handle_rain_added)
    event_bus.subscribe(EventType.RAIN_CLEARED, handle_rain_cleared)
    event_bus.subscribe(EventType.RAIN_RANDOMIZED, handle_rain_randomized)
    event_bus.subscribe(EventType.TRAFFIC_ADDED, handle_traffic_added)
    event_bus.subscribe(EventType.TRAFFIC_CLEARED, handle_traffic_cleared)
    event_bus.subscribe(EventType.TRAFFIC_RANDOMIZED, handle_traffic_randomized)
    event_bus.subscribe(EventType.OBSTACLE_ADDED, handle_obstacle_added)
    event_bus.subscribe(EventType.OBSTACLE_CLEARED, handle_obstacle_cleared)
    event_bus.subscribe(EventType.OBSTACLE_RANDOMIZED, handle_obstacle_randomized)
