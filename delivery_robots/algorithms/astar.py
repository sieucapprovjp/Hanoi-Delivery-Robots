"""Module containing the A* Search algorithm implementation."""

import heapq
from typing import Tuple, List, Dict, Set, Callable, Any
import networkx as nx
from .base import SearchContract, SearchInput, reconstruct_node_path, AlgoResult
from ..utils.geo import haversine_distance
from ..utils import intercept_measure


def compute_reverse_dijkstra(
    graph: nx.MultiDiGraph,
    dest_node: int,
    weight_fn: Callable[[int, int, dict], float],
) -> Dict[int, float]:
    """Computes the shortest path cost from all nodes to dest_node using Reverse Dijkstra.

    Args:
        graph (nx.MultiDiGraph): The road network graph snapshot.
        dest_node (int): The destination node from which the reverse search starts.
        weight_fn (Callable[[int, int, dict], float]): Function to calculate edge weight.

    Returns:
        Dict[int, float]: A dictionary mapping node IDs to their optimal cost to dest_node.
    """
    dist: Dict[int, float] = {dest_node: 0.0}
    visited: Set[int] = set()
    pq: List[Tuple[float, int]] = [(0.0, dest_node)]

    while pq:
        d, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)

        for p in graph.predecessors(u):
            if p in visited:
                continue

            edge_data_dict = graph[p][u]
            min_w = float("inf")
            for key, edge_data in edge_data_dict.items():
                w = weight_fn(p, u, edge_data)
                if w < min_w:
                    min_w = w

            tentative = d + min_w
            if tentative < dist.get(p, float("inf")):
                dist[p] = tentative
                heapq.heappush(pq, (tentative, p))

    return dist


class AStarSearch(SearchContract[SearchInput, AlgoResult]):
    """Implementation of the A* routing algorithm using the Haversine heuristic."""

    @intercept_measure
    def execute(self, context: SearchInput) -> AlgoResult:
        import time

        start_time = time.perf_counter()
        """Executes A* search to find the shortest path between two nodes.

        Args:
            context (SearchInput): The context containing search parameters.

        Returns:
            AlgoResult: The pathfinding result including the path, nodes explored,
                planned cost, and planning time snapshot.

        Raises:
            nx.NetworkXNoPath: If no path exists between the start and end nodes.
        """
        graph: nx.MultiDiGraph = context.graph
        start_node: int = context.start_node
        end_node: int = context.end_node
        goal_lat: float = context.goal_lat
        goal_lon: float = context.goal_lon
        weight_fn: Callable[[int, int, dict], float] = context.weight_fn

        g_score: Dict[int, float] = {start_node: 0.0}
        came_from: Dict[int, int] = {}
        visited: Set[int] = set()
        nodes_explored: int = 0

        start_h: float = haversine_distance(
            graph.nodes[start_node]["y"],
            graph.nodes[start_node]["x"],
            goal_lat,
            goal_lon,
        )
        open_set: List[Tuple[float, int]] = [(start_h, start_node)]

        while open_set:
            _, current = heapq.heappop(open_set)
            if current in visited:
                continue

            visited.add(current)
            nodes_explored += 1

            if current == end_node:
                path = reconstruct_node_path(came_from, current)
                planned_cost = 0.0
                for i in range(len(path) - 1):
                    u, v = path[i], path[i + 1]
                    planned_cost += weight_fn(u, v, graph[u][v])

                # Calculate Heuristic Effectiveness Ratio using Reverse Dijkstra
                reverse_costs = compute_reverse_dijkstra(graph, end_node, weight_fn)
                total_ratio = 0.0
                ratio_count = 0
                for node in path:
                    if node == end_node:
                        continue
                    h_val = haversine_distance(
                        graph.nodes[node]["y"],
                        graph.nodes[node]["x"],
                        goal_lat,
                        goal_lon,
                    )
                    h_star_val = reverse_costs.get(node, 0.0)
                    if h_star_val > 0.0:
                        total_ratio += h_val / h_star_val
                        ratio_count += 1

                heuristic_effectiveness = (
                    total_ratio / ratio_count if ratio_count > 0 else 1.0
                )

                comp_time = time.perf_counter() - start_time
                return AlgoResult(
                    path=path,
                    explored_count=nodes_explored,
                    planned_cost=planned_cost,
                    planning_time=getattr(graph, "planning_time", 0.0),
                    computation_time=comp_time,
                    heuristic_effectiveness=heuristic_effectiveness,
                )

            for neighbor in graph.neighbors(current):
                if neighbor in visited:
                    continue

                edge_data: dict = graph[current][neighbor]
                tentative_g: float = g_score[current] + weight_fn(
                    current, neighbor, edge_data
                )

                if tentative_g >= g_score.get(neighbor, float("inf")):
                    continue

                came_from[neighbor] = current
                g_score[neighbor] = tentative_g

                h_neighbor: float = haversine_distance(
                    graph.nodes[neighbor]["y"],
                    graph.nodes[neighbor]["x"],
                    goal_lat,
                    goal_lon,
                )
                priority: float = tentative_g + h_neighbor
                heapq.heappush(open_set, (priority, neighbor))

        raise nx.NetworkXNoPath


def astar_search(
    graph: nx.MultiDiGraph,
    start_node: int,
    end_node: int,
    goal_lat: float,
    goal_lon: float,
    weight_fn: Callable[[int, int, dict], float],
    **kwargs: Any,
) -> AlgoResult:
    """Helper function to execute A* search for backward compatibility.

    Args:
        graph (nx.MultiDiGraph): The road network graph.
        start_node (int): The starting node ID.
        end_node (int): The destination node ID.
        goal_lat (float): Latitude of the goal node.
        goal_lon (float): Longitude of the goal node.
        weight_fn (Callable[[int, int, dict], float]): Function to calculate edge weight.
        **kwargs (Any): Additional keyword arguments.

    Returns:
        AlgoResult: The pathfinding result including the path, nodes explored,
            planned cost, and planning time snapshot.

    Raises:
        nx.NetworkXNoPath: If no path exists.
    """
    context: SearchInput = SearchInput(
        graph=graph,
        start_node=start_node,
        end_node=end_node,
        weight_fn=weight_fn,
        goal_lat=goal_lat,
        goal_lon=goal_lon,
    )
    return AStarSearch().execute(context)
