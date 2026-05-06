import osmnx as ox


from ..config import (
    DEFAULT_EDGE_LENGTH,
    DEFAULT_ROUTE_DISTANCE,
    SPEED_METERS_PER_SECOND,
)


def nearest_node_id(graph, lat, lon, state=None):
    """
    Find the nearest node in the graph to the given coordinates using OSMnx.
    """
    return ox.distance.nearest_nodes(graph, lon, lat)


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
