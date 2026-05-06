import networkx as nx


def _build_traffic_routes(
    graph,
    state,
    nearest_node_id,
    build_route_response,
    traffic_penalty_for_point,
    rain_penalty_for_point,
    obstacle_penalty_for_point,
):
    routes = []
    for anchor in state["traffic_anchors"]:
        start_lat, start_lon = anchor["start"]
        end_lat, end_lon = anchor["end"]
        start_node = nearest_node_id(graph, start_lat, start_lon)
        end_node = nearest_node_id(graph, end_lat, end_lon)
        route_nodes = nx.shortest_path(graph, start_node, end_node, weight="length")
        route_payload = build_route_response(
            graph,
            route_nodes,
            traffic_penalty_for_point,
            rain_penalty_for_point,
            obstacle_penalty_for_point,
            include_cost_breakdown=False,
        )
        routes.append(
            {
                "name": anchor["name"],
                "severity": anchor["severity"],
                "path": route_payload["path"],
            }
        )
    return routes


def get_road_graph(
    state,
    nearest_node_id,
    build_route_response,
    traffic_penalty_for_point,
    rain_penalty_for_point,
    obstacle_penalty_for_point,
):
    if (
        state["road_graph"]
        and state["projected_road_graph"]
        and state["traffic_routes"]
    ):
        return (
            state["road_graph"],
            state["projected_road_graph"],
            state["traffic_routes"],
        )

    with state["graph_lock"]:
        if state["ox"] is None:
            import osmnx as ox

            state["ox"] = ox

        if not state["road_graph"]:
            state["road_graph"] = state["ox"].graph_from_point(
                state["graph_center"],
                dist=state["graph_dist_meters"],
                network_type=state["graph_network_type"],
                simplify=True,
            )
            state["projected_road_graph"] = state["ox"].project_graph(
                state["road_graph"]
            )
            state["traffic_routes"] = _build_traffic_routes(
                state["road_graph"],
                state,
                nearest_node_id,
                build_route_response,
                traffic_penalty_for_point,
                rain_penalty_for_point,
                obstacle_penalty_for_point,
            )

    return state["road_graph"], state["projected_road_graph"], state["traffic_routes"]
