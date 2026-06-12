"""Module containing the Breadth-First Search (BFS) algorithm implementation."""

from collections import deque
from typing import Tuple, Dict, Set, Optional
import networkx as nx
from .base import (
    SearchContract,
    SearchInput,
    reconstruct_node_path,
    AlgoResult,
    get_ordered_neighbors,
)
from ..utils import intercept_measure


class BFSSearch(SearchContract[SearchInput, AlgoResult]):
    """Implementation of Breadth-First Search routing algorithm."""

    @intercept_measure
    def execute(self, context: SearchInput) -> AlgoResult:
        import time

        start_time = time.perf_counter()
        """Executes Breadth-First Search to find a path.

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

        queue: deque[Tuple[int, Optional[int]]] = deque([(start_node, None)])
        visited: Set[int] = set()
        came_from: Dict[int, int] = {}
        nodes_explored: int = 0

        while queue:
            current, parent = queue.popleft()
            if current in visited:
                continue

            if parent is not None:
                came_from[current] = parent

            visited.add(current)
            nodes_explored += 1

            if current == end_node:
                path = reconstruct_node_path(came_from, current)
                weight_fn = getattr(context, "weight_fn", None)
                planned_cost = 0.0
                if weight_fn:
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

            policy = getattr(context, "neighbor_ordering_policy", "id")
            for neighbor in get_ordered_neighbors(graph, current, end_node, policy):
                if neighbor not in visited:
                    queue.append((neighbor, current))

        raise nx.NetworkXNoPath
