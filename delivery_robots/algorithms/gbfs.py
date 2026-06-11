"""Module containing the Greedy Best-First Search (GBFS) algorithm implementation."""

import heapq
from typing import Tuple, List, Dict, Set, Callable, Any
import networkx as nx
from .base import SearchContract, SearchInput, reconstruct_node_path, AlgoResult
from ..utils.geo import haversine_distance
from ..utils import profile_time


class GBFSSearch(SearchContract[SearchInput, AlgoResult]):
    """Implementation of Greedy Best-First Search shortest path routing algorithm."""

    @profile_time(label="gbfs_search")
    def execute(self, context: SearchInput) -> AlgoResult:
        import time
        start_time = time.perf_counter()
        """Executes Greedy Best-First Search to find the route.

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
                comp_time = time.perf_counter() - start_time
                return AlgoResult(
                    path=path,
                    explored_count=nodes_explored,
                    planned_cost=planned_cost,
                    planning_time=getattr(graph, "planning_time", 0.0),
                    computation_time=comp_time,
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
                heapq.heappush(open_set, (h_neighbor, neighbor))

        raise nx.NetworkXNoPath


def gbfs_search(
    graph: nx.MultiDiGraph,
    start_node: int,
    end_node: int,
    goal_lat: float,
    goal_lon: float,
    weight_fn: Callable[[int, int, dict], float],
    **kwargs: Any,
) -> AlgoResult:
    """Helper function to execute GBFS search for backward compatibility.

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
    return GBFSSearch().execute(context)
