import networkx as nx
import numpy as np
from sklearn.neighbors import BallTree


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
    NetworkX algorithms and utility functions. It computes and freezes dynamic edge
    weights at a specific simulated/real timestamp.
    """

    def __init__(
        self,
        graph: nx.MultiDiGraph,
        planning_time: float,
        snap_state: dict,
    ) -> None:
        """Initializes the GraphSnapshot.

        Args:
            graph (nx.MultiDiGraph): The live source road graph to copy structure from.
            planning_time (float): The timestamp when the planning occurred.
            snap_state (dict): Copied environmental state elements to calculate static weights.
        """
        # Shallow copy of structural data (nodes, edges, graph attributes)
        super().__init__(graph)
        self.planning_time: float = planning_time
        self.snap_state: dict = snap_state

        from .environment import edge_weight_with_traffic

        # Calculate and cache dynamic weight for all edges
        for u, v, key, data in self.edges(keys=True, data=True):
            weight = edge_weight_with_traffic(snap_state, u, v, data)
            data["weight"] = weight

        # Freeze structural mutations (raises error on add_node, add_edge, etc.)
        nx.freeze(self)

    def get_edge_weight(self, u: int, v: int, edge_data: dict) -> float:
        """Retrieves the frozen weight for an edge or a dictionary of parallel edges.

        Args:
            u (int): The source node ID.
            v (int): The destination node ID.
            edge_data (dict): The edge attribute dictionary, or dict of parallel edges.

        Returns:
            float: The cached static edge weight.
        """
        from ..config import DEFAULT_EDGE_LENGTH

        if "weight" in edge_data:
            return edge_data["weight"]

        # If it's a MultiDiGraph parallel edge mapping (key -> edge_attributes_dict)
        return min(
            data.get("weight", data.get("length", DEFAULT_EDGE_LENGTH))
            for data in edge_data.values()
        )

