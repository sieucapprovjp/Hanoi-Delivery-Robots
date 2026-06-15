import heapq

import networkx as nx

from ..utils.geo import haversine_distance


def _reconstruct_node_path(came_from, current):
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path

def run_weighted_route_search(
    graph,
    start_node,
    end_node,
    goal_lat,
    goal_lon,
    weight_fn,
    algorithm,
):
    g_score = {start_node: 0.0}
    came_from = {}
    visited = set()
    nodes_explored = 0

    start_h = haversine_distance(
        graph.nodes[start_node]["y"],
        graph.nodes[start_node]["x"],
        goal_lat,
        goal_lon,
    )

    if algorithm == "dijkstra":
        open_set = [(0.0, start_node)]
    elif algorithm == "gbfs":
        open_set = [(start_h, start_node)]
    else:
        open_set = [(start_h, start_node)]

    while open_set:
        _, current = heapq.heappop(open_set)
        if current in visited:
            continue

        visited.add(current)
        nodes_explored += 1

        if current == end_node:
            return _reconstruct_node_path(came_from, current), nodes_explored

        for neighbor in graph.neighbors(current):
            if neighbor in visited:
                continue

            edge_data = graph[current][neighbor]
            tentative_g = g_score[current] + weight_fn(current, neighbor, edge_data)
            if tentative_g >= g_score.get(neighbor, float("inf")):
                continue

            came_from[neighbor] = current
            g_score[neighbor] = tentative_g

            h_neighbor = haversine_distance(
                graph.nodes[neighbor]["y"],
                graph.nodes[neighbor]["x"],
                goal_lat,
                goal_lon,
            )

            if algorithm == "dijkstra":
                priority = tentative_g
            elif algorithm == "gbfs":
                priority = h_neighbor
            else:
                priority = tentative_g + h_neighbor

            heapq.heappush(open_set, (priority, neighbor))

    raise nx.NetworkXNoPath
