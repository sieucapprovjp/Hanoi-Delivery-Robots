import threading

class MapManager:
    """Manages OpenStreetMap road graph."""
    
    GRAPH_CENTER = (21.0285, 105.8542)
    GRAPH_DIST_METERS = 2200
    GRAPH_NETWORK_TYPE = "bike"

    def __init__(self):
        self._graph_lock = threading.Lock()
        self._road_graph = None
        self._projected_road_graph = None
        self._ox = None

    def get_road_graph(self):
        """Returns the road graph and projected graph."""
        if self._road_graph is not None and self._projected_road_graph is not None:
            return self._road_graph, self._projected_road_graph

        with self._graph_lock:
            if self._ox is None:
                import osmnx as ox
                self._ox = ox

            if self._road_graph is None:
                self._road_graph = self._ox.graph_from_point(
                    self.GRAPH_CENTER,
                    dist=self.GRAPH_DIST_METERS,
                    network_type=self.GRAPH_NETWORK_TYPE,
                    simplify=True,
                )
                self._projected_road_graph = self._ox.project_graph(self._road_graph)

        return self._road_graph, self._projected_road_graph
