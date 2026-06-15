import numpy as np

from ..config import (
    DEFAULT_EDGE_LENGTH,
    DEFAULT_ROUTE_DISTANCE,
    ESTIMATED_SPEED_METERS_PER_MINUTE,
)
from .geo import haversine_distance


def nearest_node_id(graph, lat, lon, state):
    """
    Find the nearest node in the graph to the given coordinates.
    Uses the BallTree from state if available for O(log N) lookup.
    """
    spatial_tree = state.get("spatial_tree")
    spatial_node_ids = state.get("spatial_node_ids")
    ox = state.get("ox")
    if spatial_tree is not None and spatial_node_ids is not None:
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


def road_memory_key(graph, from_node, to_node):
    from_data = graph.nodes[from_node]
    to_data = graph.nodes[to_node]
    return (
        f"{from_data['y']:.4f},{from_data['x']:.4f}->"
        f"{to_data['y']:.4f},{to_data['x']:.4f}"
    )


def build_memory_weight_fn(
    graph,
    base_weight_fn,
    road_memory,
    default_penalty,
    memory_key_cache=None,
):
    if not road_memory:
        return base_weight_fn

    key_cache = memory_key_cache if memory_key_cache is not None else {}

    def edge_weight_with_memory(from_node, to_node, edge_data):
        base_weight = base_weight_fn(from_node, to_node, edge_data)
        edge_key = (from_node, to_node)
        if edge_key not in key_cache:
            key_cache[edge_key] = road_memory_key(graph, from_node, to_node)
        return base_weight * road_memory.get(key_cache[edge_key], default_penalty)

    return edge_weight_with_memory


def attach_route_metadata(
    payload,
    graph,
    start_node,
    end_node,
    algorithm,
    calc_time_ms,
    nodes_explored,
):
    payload["start"] = {
        "lat": graph.nodes[start_node]["y"],
        "lon": graph.nodes[start_node]["x"],
    }
    payload["end"] = {
        "lat": graph.nodes[end_node]["y"],
        "lon": graph.nodes[end_node]["x"],
    }
    payload["algo"] = algorithm
    payload["timeMs"] = round(calc_time_ms, 2)
    payload["nodesExplored"] = nodes_explored
    payload["pathCost"] = payload.get("costBreakdown", {}).get(
        "totalCost", round(payload.get("distance", 0.0), 1)
    )
    return payload


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
    total_weighted_cost = 0.0
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
            rain_cost += edge_length * traffic_penalty * max(0, rain_penalty - 1)
            obstacle_cost += (
                edge_length
                * traffic_penalty
                * rain_penalty
                * max(0, obstacle_penalty - 1)
            )
            total_weighted_cost += (
                edge_length * traffic_penalty * rain_penalty * obstacle_penalty
            )

    response = {
        "path": route_path,
        "distance": route_distance,
    }

    if include_cost_breakdown:
        response["costBreakdown"] = {
            "baseDistance": round(route_distance, 1),
            "trafficPenalty": round(traffic_cost, 1),
            "rainPenalty": round(rain_cost, 1),
            "obstaclePenalty": round(obstacle_cost, 1),
            "totalCost": round(total_weighted_cost, 1),
            "estimatedMinutes": round(
                total_weighted_cost / ESTIMATED_SPEED_METERS_PER_MINUTE, 1
            ),
        }
    return response
