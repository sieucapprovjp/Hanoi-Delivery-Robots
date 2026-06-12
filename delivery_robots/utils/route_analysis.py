from typing import Any, List
import numpy as np

from ..config import (
    DEFAULT_EDGE_LENGTH,
    DEFAULT_ROUTE_DISTANCE,
    SPEED_METERS_PER_SECOND,
)
from .geo import haversine_distance
from .profiler import profile_time


@profile_time(label="nearest_node_id")
def nearest_node_id(graph, lat, lon, state):
    """
    Find the nearest node in the graph to the given coordinates.
    Uses the BallTree from state if available for O(log N) lookup.
    """
    spatial_tree = state.get("spatial_tree")
    spatial_node_ids = state.get("spatial_node_ids")
    ox = state.get("ox")
    if spatial_tree is not None and spatial_node_ids.size > 0:
        query_coord = np.array([[np.radians(lat), np.radians(lon)]])
        _, indices = spatial_tree.query(query_coord, k=1)
        return spatial_node_ids[indices[0][0]]

    if ox:
        return ox.nearest_nodes(graph, lon, lat)

    nodes = graph.nodes(data=True)
    best_node_id = None
    best_distance = float("inf")
    for node_id, node_data in nodes:
        distance = haversine_distance(lat, lon, node_data["y"], node_data["x"])
        if distance < best_distance:
            best_distance = distance
            best_node_id = node_id
    return best_node_id


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


def build_geometry_path(graph, route_nodes):
    """
    Build a flat list of geometry coordinates for an entire route.
    Used by the frontend to draw an accurate polyline on the map.
    Each edge may contain intermediate shape points from OSM geometry.
    """
    route_path = []
    for idx in range(len(route_nodes) - 1):
        from_node = route_nodes[idx]
        to_node = route_nodes[idx + 1]
        edge_options = graph.get_edge_data(from_node, to_node)
        edge_data = min(
            edge_options.values(),
            key=lambda e: e.get("length", float("inf")),
        )
        segment_pts = edge_geometry_coordinates(graph, from_node, to_node, edge_data)
        if route_path and segment_pts:
            segment_pts = segment_pts[1:]  # avoid duplicating junction point
        route_path.extend(segment_pts)
    return route_path


def build_segment_geometry(graph, route_nodes):
    """
    Build a per-node-segment geometry list for proportional interpolation.
    Returns a list where index i contains the geometry points for the
    edge from route_nodes[i] to route_nodes[i+1].
    The frontend uses this to interpolate position within each segment
    at a speed proportional to sub-segment length.
    """
    segments = []
    for idx in range(len(route_nodes) - 1):
        from_node = route_nodes[idx]
        to_node = route_nodes[idx + 1]
        edge_options = graph.get_edge_data(from_node, to_node)
        edge_data = min(
            edge_options.values(),
            key=lambda e: e.get("length", float("inf")),
        )
        seg_pts = edge_geometry_coordinates(graph, from_node, to_node, edge_data)
        segments.append(seg_pts)
    return segments


def build_route_response(
    graph,
    route_nodes,
    traffic_penalty_for_point,
    rain_penalty_for_point,
    obstacle_penalty_for_point,
    include_cost_breakdown=True,
):
    route_path = []
    route_distance = DEFAULT_ROUTE_DISTANCE
    traffic_cost = 0.0
    rain_cost = 0.0
    obstacle_cost = 0.0
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
        edge_length = edge_data.get("length", DEFAULT_EDGE_LENGTH)
        route_distance += edge_length

        if include_cost_breakdown:
            from_data = graph.nodes[from_node]
            to_data = graph.nodes[to_node]
            midpoint_lat = (from_data["y"] + to_data["y"]) / 2
            midpoint_lon = (from_data["x"] + to_data["x"]) / 2
            traffic_penalty = traffic_penalty_for_point(midpoint_lat, midpoint_lon)
            rain_penalty = rain_penalty_for_point(midpoint_lat, midpoint_lon)
            obstacle_penalty = obstacle_penalty_for_point(midpoint_lat, midpoint_lon)
            traffic_cost += edge_length * max(0, traffic_penalty - 1)
            rain_cost += edge_length * max(0, rain_penalty - 1)
            obstacle_cost += edge_length * max(0, obstacle_penalty - 1)

    response = {
        "path": route_path,
        "distance": route_distance,
    }

    if include_cost_breakdown:
        total_cost = route_distance + traffic_cost + rain_cost + obstacle_cost
        response["costBreakdown"] = {
            "baseDistance": round(route_distance, 1),
            "trafficPenalty": round(traffic_cost, 1),
            "rainPenalty": round(rain_cost, 1),
            "obstaclePenalty": round(obstacle_cost, 1),
            "totalCost": round(total_cost, 1),
            "estimatedMinutes": round(total_cost / SPEED_METERS_PER_SECOND / 60.0, 1),
        }
    return response


def classify_query_difficulty(graph: Any, path: List[int]) -> str:
    """Classifies the difficulty of a query path into one of the four strata.

    Args:
        graph: The road network graph (networkx.MultiDiGraph).
        path (List[int]): List of node IDs representing the path.

    Returns:
        str: One of "short", "medium", "long", or "topologically_hard".
    """
    import networkx as nx
    from ..config import (
        DIFFICULTY_SHORT_MAX_METERS,
        DIFFICULTY_MEDIUM_MAX_METERS,
        DIFFICULTY_ONE_WAY_THRESHOLD,
        DEFAULT_EDGE_LENGTH,
    )

    if not path or len(path) < 2:
        return "short"

    # 1. Topological Hardness Checks
    # Cache largest SCC on the graph object for efficiency, validating by node/edge counts
    if (
        "largest_scc" not in graph.graph
        or graph.graph.get("largest_scc_nodes_count") != graph.number_of_nodes()
        or graph.graph.get("largest_scc_edges_count") != graph.number_of_edges()
    ):
        sccs = list(nx.strongly_connected_components(graph))
        graph.graph["largest_scc"] = max(sccs, key=len) if sccs else set()
        graph.graph["largest_scc_nodes_count"] = graph.number_of_nodes()
        graph.graph["largest_scc_edges_count"] = graph.number_of_edges()
    largest_scc = graph.graph["largest_scc"]

    # Check for nodes outside largest SCC
    has_node_outside_largest_scc = any(node not in largest_scc for node in path)

    # Check for dead-ends (out_degree == 0) on the path or 1-hop neighbors
    has_dead_end_nearby = False
    for node in path:
        if graph.out_degree(node) == 0:
            has_dead_end_nearby = True
            break
        for neighbor in graph.neighbors(node):
            if graph.out_degree(neighbor) == 0:
                has_dead_end_nearby = True
                break
        if has_dead_end_nearby:
            break

    # Check one-way streets ratio
    one_way_count = 0
    for idx in range(len(path) - 1):
        u = path[idx]
        v = path[idx + 1]
        # Structurally one-way if there is no reverse edge
        if not graph.has_edge(v, u):
            one_way_count += 1
    one_way_ratio = one_way_count / (len(path) - 1)

    if (
        has_node_outside_largest_scc
        or has_dead_end_nearby
        or one_way_ratio >= DIFFICULTY_ONE_WAY_THRESHOLD
    ):
        return "topologically_hard"

    # 2. Distance-based classification
    # Calculate path length in meters
    route_distance = 0.0
    for idx in range(len(path) - 1):
        u = path[idx]
        v = path[idx + 1]
        edge_options = graph.get_edge_data(u, v)
        if edge_options:
            edge_data = min(
                edge_options.values(),
                key=lambda item: item.get("length", float("inf")),
            )
            route_distance += edge_data.get("length", DEFAULT_EDGE_LENGTH)

    if route_distance < DIFFICULTY_SHORT_MAX_METERS:
        return "short"
    elif route_distance <= DIFFICULTY_MEDIUM_MAX_METERS:
        return "medium"
    else:
        return "long"
