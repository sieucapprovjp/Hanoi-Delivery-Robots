import tempfile
import threading
import unittest
import json

import networkx as nx
import numpy as np

from delivery_robots.core.hubs import (
    compute_optimized_hubs,
    delivery_history_points_from_log,
    load_delivery_points_for_kmeans,
    snap_hubs_to_graph,
)
from delivery_robots.utils.persistent_log import append_delivery_history


def build_state(memory_points=None):
    return {
        "delivery_history": list(memory_points or []),
        "history_lock": threading.Lock(),
    }


class HubOptimizationTests(unittest.TestCase):
    def test_delivery_history_points_from_log_reads_pickup_and_dropoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            append_delivery_history(
                {
                    "deliveryId": 1,
                    "pickup": {"lat": 21.0, "lon": 105.0},
                    "dropoff": {"lat": 21.1, "lon": 105.1},
                },
                tmp,
            )

            points = delivery_history_points_from_log(tmp)

        self.assertEqual(points, [[21.0, 105.0], [21.1, 105.1]])

    def test_load_delivery_points_prefers_log_when_enough_points(self):
        state = build_state([[30.0, 120.0]] * 5)

        with tempfile.TemporaryDirectory() as tmp:
            for idx in range(3):
                append_delivery_history(
                    {
                        "deliveryId": idx,
                        "pickup": {"lat": 21.0 + idx, "lon": 105.0},
                        "dropoff": {"lat": 21.5 + idx, "lon": 105.5},
                    },
                    tmp,
                )

            points, source = load_delivery_points_for_kmeans(state, tmp)

        self.assertEqual(source, "log")
        self.assertEqual(len(points), 6)
        self.assertEqual(points[0], [21.0, 105.0])

    def test_load_delivery_points_falls_back_to_memory_when_log_is_short(self):
        state = build_state([[21.0 + idx, 105.0] for idx in range(5)])

        with tempfile.TemporaryDirectory() as tmp:
            append_delivery_history(
                {
                    "deliveryId": 1,
                    "pickup": {"lat": 30.0, "lon": 120.0},
                    "dropoff": {"lat": 30.1, "lon": 120.1},
                },
                tmp,
            )

            points, source = load_delivery_points_for_kmeans(state, tmp)

        self.assertEqual(source, "memory")
        self.assertEqual(points, state["delivery_history"])

    def test_compute_optimized_hubs_uses_file_log(self):
        state = build_state([])

        with tempfile.TemporaryDirectory() as tmp:
            for idx in range(3):
                append_delivery_history(
                    {
                        "deliveryId": idx,
                        "pickup": {"lat": 21.0 + idx * 0.001, "lon": 105.0},
                        "dropoff": {"lat": 21.1 + idx * 0.001, "lon": 105.1},
                    },
                    tmp,
                )

            hubs = compute_optimized_hubs(state, cluster_count=2, log_dir=tmp)

        self.assertEqual(len(hubs), 2)
        self.assertTrue(all("lat" in hub and "lon" in hub for hub in hubs))

    def test_snap_hubs_to_graph_moves_centroid_to_nearest_road_node(self):
        graph = nx.Graph()
        graph.add_node(np.int64(101), y=21.0, x=105.0)
        graph.add_node(np.int64(202), y=21.1, x=105.1)
        hubs = [{"id": 0, "lat": 21.02, "lon": 105.02, "name": "AI Hub A"}]

        def nearest_node(_graph, lat, lon, _ox=None):
            return min(
                _graph.nodes,
                key=lambda node_id: (
                    (_graph.nodes[node_id]["y"] - lat) ** 2
                    + (_graph.nodes[node_id]["x"] - lon) ** 2
                ),
            )

        snapped = snap_hubs_to_graph(hubs, graph, nearest_node)

        self.assertEqual(snapped[0]["lat"], 21.0)
        self.assertEqual(snapped[0]["lon"], 105.0)
        self.assertEqual(snapped[0]["centroidLat"], 21.02)
        self.assertEqual(snapped[0]["centroidLon"], 105.02)
        self.assertTrue(snapped[0]["snappedToRoad"])
        self.assertEqual(snapped[0]["roadNodeId"], "101")
        json.dumps(snapped)


if __name__ == "__main__":
    unittest.main()
