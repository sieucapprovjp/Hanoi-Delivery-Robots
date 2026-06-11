"""Module responsible for dynamically dispatching route searches to plugins."""

from typing import Tuple, List, Callable, Dict
import networkx as nx
from .base import SearchContract, SearchInput
from .dijkstra import DijkstraSearch
from .gbfs import GBFSSearch
from .astar import AStarSearch
from .dfs import DFSSearch
from .bfs import BFSSearch
from ..utils import profile_time

ALGORITHMS: Dict[str, SearchContract[SearchInput, Tuple[List[int], int]]] = {
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
    searcher: SearchContract[SearchInput, Tuple[List[int], int]] = ALGORITHMS.get(
        algorithm, ALGORITHMS["astar"]
    )
    context: SearchInput = SearchInput(
        graph=graph,
        start_node=start_node,
        end_node=end_node,
        weight_fn=weight_fn,
        goal_lat=goal_lat,
        goal_lon=goal_lon,
    )
    return searcher.execute(context)
