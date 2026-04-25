import threading
import time
import math
import networkx as nx
from .geo_utils import haversine_distance, point_to_segment_distance_meters
from .route_analysis import build_route_response, nearest_node_id

class EnvironmentManager:
    """Manages environment state like traffic, rain, and obstacles."""
    
    TRAFFIC_ANCHORS = []
    TRAFFIC_PERIOD_SECONDS = 36
    RUSH_HOURS = [
        {"name": "Morning Rush", "start": 7, "end": 9, "multiplier": 2.5},
        {"name": "Lunch Traffic", "start": 11, "end": 13, "multiplier": 1.3},
        {"name": "Evening Rush", "start": 17, "end": 19, "multiplier": 3.0},
    ]

    def __init__(self, map_manager):
        self.map_manager = map_manager
        self.rain_zones = []
        
        self._simulation_start_time = time.time()
        self._simulation_speed = 60
        
        self._dynamic_traffic_lock = threading.Lock()
        self._dynamic_traffic_routes = []
        self._traffic_routes = None
        
        self._obstacles_lock = threading.Lock()
        self._obstacles = []

    def get_simulation_time(self):
        """Returns simulated time based on real elapsed time and simulation speed."""
        elapsed_real = time.time() - self._simulation_start_time
        elapsed_simulated = elapsed_real * self._simulation_speed
        sim_seconds_from_midnight = 21600 + elapsed_simulated
        sim_seconds_from_midnight = sim_seconds_from_midnight % 86400
        hours = int(sim_seconds_from_midnight // 3600)
        minutes = int((sim_seconds_from_midnight % 3600) // 60)
        seconds = int(sim_seconds_from_midnight % 60)
        return hours, minutes, seconds

    def get_rush_hour_multiplier(self):
        """Returns traffic multiplier based on current simulated time."""
        hours, minutes, seconds = self.get_simulation_time()
        current_hour = hours + minutes / 60.0

        for rush in self.RUSH_HOURS:
            if rush["start"] <= current_hour < rush["end"]:
                progress = (current_hour - rush["start"]) / (rush["end"] - rush["start"])
                multiplier = 1 + (rush["multiplier"] - 1) * math.sin(progress * math.pi)
                return multiplier, rush["name"]

        return 1.0, "Normal"

    def initialize_traffic_routes(self):
        """Builds initial traffic routes from anchors."""
        if self._traffic_routes is not None:
            return

        graph, _, _ = self.map_manager.get_road_graph()
        self._traffic_routes = []

        for anchor in self.TRAFFIC_ANCHORS:
            start_lat, start_lon = anchor["start"]
            end_lat, end_lon = anchor["end"]
            start_node = nearest_node_id(graph, start_lat, start_lon, self.map_manager._ox)
            end_node = nearest_node_id(graph, end_lat, end_lon, self.map_manager._ox)
            route_nodes = nx.shortest_path(graph, start_node, end_node, weight="length")
            route_payload = build_route_response(
                graph,
                route_nodes,
                self.traffic_penalty_for_point,
                self.rain_penalty_for_point,
                self.obstacle_penalty_for_point,
                include_cost_breakdown=False,
            )
            self._traffic_routes.append(
                {
                    "name": anchor["name"],
                    "severity": anchor["severity"],
                    "path": route_payload["path"],
                }
            )

    def traffic_penalty_for_point(self, lat, lon):
        """Calculates traffic penalty at a given point."""
        penalty = 1.0
        now = time.time()
        
        if self._traffic_routes is None:
            self.initialize_traffic_routes()
            
        if self._traffic_routes is None and not self._dynamic_traffic_routes:
            return penalty

        traffic_routes = list(self._traffic_routes or [])
        with self._dynamic_traffic_lock:
            traffic_routes.extend(self._dynamic_traffic_routes)

        rush_multiplier, _ = self.get_rush_hour_multiplier()
        penalty *= rush_multiplier

        for road in traffic_routes:
            if len(road["path"]) < 2:
                continue

            progress = (now / self.TRAFFIC_PERIOD_SECONDS + road["severity"]) % 1
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

    def rain_penalty_for_point(self, lat, lon):
        """Calculates rain penalty at a given point."""
        penalty = 1.0

        for zone in self.rain_zones:
            center_lat, center_lon = zone["center"]
            distance = haversine_distance(lat, lon, center_lat, center_lon)
            if distance <= zone["radius"]:
                penalty = max(penalty, 1 + zone.get("severity", 1.0))

        return penalty

    def obstacle_penalty_for_point(self, lat, lon):
        """Calculates obstacle penalty at a given point."""
        penalty = 1.0

        with self._obstacles_lock:
            obstacles = list(self._obstacles)

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

    def edge_weight_with_traffic(self, from_node, to_node, edge_data, graph):
        """Calculates total weight of an edge including all penalties."""
        from_data = graph.nodes[from_node]
        to_data = graph.nodes[to_node]
        midpoint_lat = (from_data["y"] + to_data["y"]) / 2
        midpoint_lon = (from_data["x"] + to_data["x"]) / 2
        penalty = self.traffic_penalty_for_point(midpoint_lat, midpoint_lon)
        penalty *= self.rain_penalty_for_point(midpoint_lat, midpoint_lon)
        penalty *= self.obstacle_penalty_for_point(midpoint_lat, midpoint_lon)

        if "length" in edge_data:
            return edge_data.get("length", 0.0) * penalty

        best_length = min(data.get("length", float("inf")) for data in edge_data.values())
        return best_length * penalty
