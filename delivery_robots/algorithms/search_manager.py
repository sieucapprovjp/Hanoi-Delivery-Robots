"""Module responsible for dynamically dispatching route searches to plugins."""

from typing import Tuple, List, Callable, Dict
import networkx as nx
import dataclasses
from .base import SearchContract, SearchInput, AlgoResult
from .dijkstra import DijkstraSearch
from .gbfs import GBFSSearch
from .astar import AStarSearch
from .dfs import DFSSearch
from .bfs import BFSSearch
from ..utils import profile_time

ALGORITHMS: Dict[str, SearchContract[SearchInput, AlgoResult]] = {
    "dijkstra": DijkstraSearch(),
    "gbfs": GBFSSearch(),
    "astar": AStarSearch(),
    "dfs": DFSSearch(),
    "bfs": BFSSearch(),
}


@profile_time(label="run_weighted_route_search")
def run_weighted_route_search(
    graph: nx.MultiDiGraph,
    start_node: int,
    end_node: int,
    goal_lat: float,
    goal_lon: float,
    weight_fn: Callable[[int, int, dict], float],
    algorithm: str,
) -> Tuple[List[int], int]:
    """Dispatches the route search query to the selected algorithm contract.

    Args:
        graph (nx.MultiDiGraph): The road network graph.
        start_node (int): The starting node ID.
        end_node (int): The destination node ID.
        goal_lat (float): Latitude of the goal node.
        goal_lon (float): Longitude of the goal node.
        weight_fn (Callable[[int, int, dict], float]): Function to calculate edge weight.
        algorithm (str): Identifier of the routing algorithm to use.

    Returns:
        Tuple[List[int], int]: A tuple containing the path list and nodes explored count.

    Raises:
        nx.NetworkXNoPath: If no path exists.
    """
    from ..config import NEIGHBOR_ORDERING_POLICY

    policy = NEIGHBOR_ORDERING_POLICY
    if hasattr(graph, "neighbor_ordering_policy"):
        policy = getattr(graph, "neighbor_ordering_policy")
    elif hasattr(graph, "snap_state") and graph.snap_state:
        policy = graph.snap_state.get("neighbor_ordering_policy", policy)

    searcher: SearchContract[SearchInput, AlgoResult] = ALGORITHMS.get(
        algorithm, ALGORITHMS["astar"]
    )
    context: SearchInput = SearchInput(
        graph=graph,
        start_node=start_node,
        end_node=end_node,
        weight_fn=weight_fn,
        goal_lat=goal_lat,
        goal_lon=goal_lon,
        neighbor_ordering_policy=policy,
    )
    algo_result = searcher.execute(context)

    # Recalculate cost for BFS and DFS to ensure correct weights at t_planning are used
    cost_algo = algo_result.planned_cost
    if algorithm in ("dfs", "bfs"):
        path = algo_result.path
        recalculated_cost = 0.0
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            recalculated_cost += weight_fn(u, v, graph[u][v])
        cost_algo = recalculated_cost
        algo_result = dataclasses.replace(algo_result, planned_cost=recalculated_cost)

    # Calculate optimal baseline using Dijkstra Oracle
    if algorithm == "dijkstra":
        optimality_ratio = 1.0
    else:
        try:
            dijkstra_searcher = ALGORITHMS["dijkstra"]
            dijkstra_result = dijkstra_searcher.execute(context)
            cost_optimal = dijkstra_result.planned_cost
            if cost_optimal > 0:
                optimality_ratio = cost_algo / cost_optimal
            else:
                optimality_ratio = 1.0
        except nx.NetworkXNoPath:
            optimality_ratio = 1.0

    algo_result = dataclasses.replace(algo_result, optimality_ratio=optimality_ratio)
    return algo_result
