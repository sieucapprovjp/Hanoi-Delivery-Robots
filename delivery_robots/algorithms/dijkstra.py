import heapq
import networkx as nx
from .base import reconstruct_node_path
from ..utils import profile_time

@profile_time(label="dijkstra_search")
def dijkstra_search(graph, start_node, end_node, weight_fn, **kwargs):
    g_score = {start_node: 0.0}
    came_from = {}
    visited = set()
    nodes_explored = 0

    open_set = [(0.0, start_node)]

    while open_set:
        _, current = heapq.heappop(open_set)
        if current in visited:
            continue

        visited.add(current)
        nodes_explored += 1

        if current == end_node:
            return reconstruct_node_path(came_from, current), nodes_explored

        for neighbor in graph.neighbors(current):
            if neighbor in visited:
                continue

            edge_data = graph[current][neighbor]
            tentative_g = g_score[current] + weight_fn(current, neighbor, edge_data)
            
            if tentative_g >= g_score.get(neighbor, float("inf")):
                continue

            came_from[neighbor] = current
            g_score[neighbor] = tentative_g
            heapq.heappush(open_set, (tentative_g, neighbor))

    raise nx.NetworkXNoPath
