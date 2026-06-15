import networkx as nx
import numpy as np
from sklearn.neighbors import BallTree
from typing import Dict, Tuple, Any


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
        start_node = nearest_node_id(graph, start_lat, start_lon, state["ox"])
        end_node = nearest_node_id(graph, end_lat, end_lon, state["ox"])
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
            import os

            center = state["graph_center"]
            dist = state["graph_dist_meters"]
            network_type = state["graph_network_type"]
            graph_filename = f"cache/road_graph_{center[0]}_{center[1]}_{dist}_{network_type}.graphml"

            if os.path.exists(graph_filename):
                print(f"Loading graph from {graph_filename}...")
                state["road_graph"] = state["ox"].load_graphml(graph_filename)
            else:
                print(f"Fetching graph from osmnx and saving to {graph_filename}...")
                os.makedirs("cache", exist_ok=True)
                state["road_graph"] = state["ox"].graph_from_point(
                    state["graph_center"],
                    dist=state["graph_dist_meters"],
                    network_type=state["graph_network_type"],
                    simplify=True,
                )
                state["ox"].save_graphml(state["road_graph"], graph_filename)
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

            # Initialize spatial index (BallTree) for fast nearest neighbor lookups
            nodes_data = list(state["road_graph"].nodes(data=True))
            state["spatial_node_ids"] = np.array([node[0] for node in nodes_data])
            coords = np.array(
                [
                    (np.radians(data["y"]), np.radians(data["x"]))
                    for _, data in nodes_data
                ]
            )
            state["spatial_tree"] = BallTree(coords, metric="haversine")

    return state["road_graph"], state["projected_road_graph"], state["traffic_routes"]


class GraphSnapshot(nx.MultiDiGraph):
    """An immutable snapshot of the road network graph at a specific planning time.

    This class subclasses networkx.MultiDiGraph to ensure 100% compatibility with
    NetworkX algorithms and utility functions. It computes dynamic edge
    weights on-demand at a specific simulated/real timestamp.
    """

    def __init__(
        self,
        graph: nx.MultiDiGraph,
        planning_time: float,
        snap_state: dict,
    ) -> None:
        """Initializes the GraphSnapshot.

        Args:
            graph (nx.MultiDiGraph): The live source road graph to share structure with.
            planning_time (float): The timestamp when the planning occurred.
            snap_state (dict): Copied environmental state elements to calculate weights.
        """
        # Shallow copy of the graph dictionary to avoid copying the entire structural data (extremely fast)
        self.__dict__.update(graph.__dict__)
        self.planning_time: float = planning_time
        self.snap_state: dict = snap_state
        self.neighbor_ordering_policy: str = snap_state.get(
            "neighbor_ordering_policy", "id"
        )
        # Lock and cache to store lazy computed weights
        import threading

        self._weight_lock: threading.Lock = threading.Lock()
        self._weight_cache: Dict[Tuple[int, int, Any], float] = {}

        # Freeze structural mutations (raises error on add_node, add_edge, etc.)
        nx.freeze(self)

    def get_edge_weight(self, u: int, v: int, edge_data: dict) -> float:
        """Retrieves the dynamic weight for an edge or a dictionary of parallel edges.

        Args:
            u (int): The source node ID.
            v (int): The destination node ID.
            edge_data (dict): The edge attribute dictionary, or dict of parallel edges.

        Returns:
            float: The lazy-computed or cached dynamic edge weight.
        """
        from ..config import DEFAULT_EDGE_LENGTH

        # If it's a MultiDiGraph parallel edge mapping (key -> edge_attributes_dict)
        if "length" not in edge_data:
            min_w = float("inf")
            for key, data in edge_data.items():
                w = self._get_single_edge_weight(u, v, key, data)
                if w < min_w:
                    min_w = w
            return min_w if min_w != float("inf") else DEFAULT_EDGE_LENGTH

        # Otherwise it's a single edge attributes dictionary
        cache_key = (u, v, id(edge_data))
        with self._weight_lock:
            if cache_key in self._weight_cache:
                return self._weight_cache[cache_key]

        from .environment import edge_weight_with_traffic

        weight = edge_weight_with_traffic(self.snap_state, u, v, edge_data)

        with self._weight_lock:
            self._weight_cache[cache_key] = weight
        return weight

    def _get_single_edge_weight(self, u: int, v: int, key: Any, data: dict) -> float:
        """Helper to get or compute weight for a single edge with a key.

        Args:
            u (int): The source node ID.
            v (int): The destination node ID.
            key (Any): The parallel edge key.
            data (dict): The edge attribute dictionary.

        Returns:
            float: The computed weight of the edge.
        """
        cache_key = (u, v, key)
        with self._weight_lock:
            if cache_key in self._weight_cache:
                return self._weight_cache[cache_key]

        from .environment import edge_weight_with_traffic

        weight = edge_weight_with_traffic(self.snap_state, u, v, data)

        with self._weight_lock:
            self._weight_cache[cache_key] = weight
        return weight
