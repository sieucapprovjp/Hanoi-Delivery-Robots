"""Module containing the Dijkstra's Search algorithm implementation."""

import heapq
from typing import Tuple, List, Dict, Set, Callable, Any
import networkx as nx
from .base import SearchContract, SearchInput, reconstruct_node_path, AlgoResult
from ..utils import intercept_measure


class DijkstraSearch(SearchContract[SearchInput, AlgoResult]):
    """Implementation of Dijkstra's shortest path routing algorithm."""

    @intercept_measure
    def execute(self, context: SearchInput) -> AlgoResult:
        import time

        start_time = time.perf_counter()
        """Executes Dijkstra's search to find the shortest path.

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
        weight_fn: Callable[[int, int, dict], float] = context.weight_fn

        g_score: Dict[int, float] = {start_node: 0.0}
        came_from: Dict[int, int] = {}
        visited: Set[int] = set()
        nodes_explored: int = 0

        open_set: List[Tuple[float, int]] = [(0.0, start_node)]

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
                heapq.heappush(open_set, (tentative_g, neighbor))

        raise nx.NetworkXNoPath


def dijkstra_search(
    graph: nx.MultiDiGraph,
    start_node: int,
    end_node: int,
    weight_fn: Callable[[int, int, dict], float],
    **kwargs: Any,
) -> AlgoResult:
    """Helper function to execute Dijkstra's search for backward compatibility.

    Args:
        graph (nx.MultiDiGraph): The road network graph.
        start_node (int): The starting node ID.
        end_node (int): The destination node ID.
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
    )
    return DijkstraSearch().execute(context)
