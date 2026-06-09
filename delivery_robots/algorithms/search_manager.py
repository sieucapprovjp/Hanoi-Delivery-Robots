from .dijkstra import dijkstra_search
from .gbfs import gbfs_search
from .astar import astar_search
from ..utils import profile_time

ALGORITHMS = {
    "dijkstra": dijkstra_search,
    "gbfs": gbfs_search,
    "astar": astar_search,
}

@profile_time(label="run_weighted_route_search")
def run_weighted_route_search(
    graph,
    start_node,
    end_node,
    goal_lat,
    goal_lon,
    weight_fn,
    algorithm,
):
    """
    Dispatches the route search to the specified algorithm.
    """
    search_fn = ALGORITHMS.get(algorithm, astar_search)
    return search_fn(
        graph=graph,
        start_node=start_node,
        end_node=end_node,
        goal_lat=goal_lat,
        goal_lon=goal_lon,
        weight_fn=weight_fn
    )
