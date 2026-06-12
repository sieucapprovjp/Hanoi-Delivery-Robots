import unittest
import networkx as nx

from delivery_robots.utils.route_analysis import classify_query_difficulty
from delivery_robots.utils.metrics import (
    create_metrics,
    record_route_metrics,
    build_metrics_payload,
)


class TestQueryStratification(unittest.TestCase):
    def setUp(self) -> None:
        # Create a basic networkx MultiDiGraph for testing
        self.graph = nx.MultiDiGraph()

        # Add a set of nodes
        for i in range(1, 11):
            self.graph.add_node(i, y=21.0 + i * 0.001, x=105.0 + i * 0.001)

    def test_classify_short_path(self) -> None:
        # Path under 500m
        # Add bidirectional edges
        self.graph.add_edge(1, 2, key=0, length=100.0)
        self.graph.add_edge(2, 1, key=0, length=100.0)
        self.graph.add_edge(2, 3, key=0, length=150.0)
        self.graph.add_edge(3, 2, key=0, length=150.0)

        path = [1, 2, 3]  # total length = 250m
        difficulty = classify_query_difficulty(self.graph, path)
        self.assertEqual(difficulty, "short")

    def test_classify_medium_path(self) -> None:
        # Path between 500m and 2000m
        self.graph.add_edge(1, 2, key=0, length=400.0)
        self.graph.add_edge(2, 1, key=0, length=400.0)
        self.graph.add_edge(2, 3, key=0, length=400.0)
        self.graph.add_edge(3, 2, key=0, length=400.0)

        path = [1, 2, 3]  # total length = 800m
        difficulty = classify_query_difficulty(self.graph, path)
        self.assertEqual(difficulty, "medium")

    def test_classify_long_path(self) -> None:
        # Path over 2000m
        self.graph.add_edge(1, 2, key=0, length=1200.0)
        self.graph.add_edge(2, 1, key=0, length=1200.0)
        self.graph.add_edge(2, 3, key=0, length=1000.0)
        self.graph.add_edge(3, 2, key=0, length=1000.0)

        path = [1, 2, 3]  # total length = 2200m
        difficulty = classify_query_difficulty(self.graph, path)
        self.assertEqual(difficulty, "long")

    def test_classify_topologically_hard_one_way(self) -> None:
        # Add a path with high one-way ratio (all edges are one-way)
        self.graph.add_edge(1, 2, key=0, length=100.0)
        self.graph.add_edge(2, 3, key=0, length=100.0)
        # Note: No reverse edges from 2 -> 1 or 3 -> 2, so one_way_ratio = 100%

        path = [1, 2, 3]
        difficulty = classify_query_difficulty(self.graph, path)
        self.assertEqual(difficulty, "topologically_hard")

    def test_classify_topologically_hard_dead_end(self) -> None:
        # Node 3 is a dead end (out-degree == 0)
        self.graph.add_edge(1, 2, key=0, length=100.0)
        self.graph.add_edge(2, 1, key=0, length=100.0)
        self.graph.add_edge(2, 3, key=0, length=100.0)
        # 3 has out-degree 0

        path = [1, 2, 3]
        difficulty = classify_query_difficulty(self.graph, path)
        self.assertEqual(difficulty, "topologically_hard")

    def test_classify_topologically_hard_node_outside_largest_scc(self) -> None:
        # Create two separate SCCs:
        # SCC 1 (largest): 1 <-> 2 <-> 3 <-> 4 <-> 1
        self.graph.add_edge(1, 2, key=0, length=50.0)
        self.graph.add_edge(2, 1, key=0, length=50.0)
        self.graph.add_edge(2, 3, key=0, length=50.0)
        self.graph.add_edge(3, 2, key=0, length=50.0)
        self.graph.add_edge(3, 4, key=0, length=50.0)
        self.graph.add_edge(4, 3, key=0, length=50.0)
        self.graph.add_edge(4, 1, key=0, length=50.0)
        self.graph.add_edge(1, 4, key=0, length=50.0)

        # SCC 2 (size 1): 5 (not connected back to the main component)
        # If we routing to node 5, it is a dead end
        self.graph.add_edge(4, 5, key=0, length=50.0)

        path = [3, 4, 5]
        difficulty = classify_query_difficulty(self.graph, path)
        self.assertEqual(difficulty, "topologically_hard")

    def test_record_route_metrics_by_strata(self) -> None:
        # Test that metrics are recorded under the correct stratum
        metrics = create_metrics()

        # Setup a short path
        self.graph.add_edge(1, 2, key=0, length=100.0)
        self.graph.add_edge(2, 1, key=0, length=100.0)
        self.graph.add_edge(2, 3, key=0, length=100.0)
        self.graph.add_edge(3, 2, key=0, length=100.0)
        path = [1, 2, 3]

        # Record a run for short path
        record_route_metrics(
            metrics,
            calc_time_ms=10.0,
            nodes_explored=15,
            path_length=3,
            memory_bytes=1024,
            optimality_ratio=1.0,
            heuristic_effectiveness=1.0,
            graph=self.graph,
            path=path,
        )

        self.assertEqual(metrics["strata"]["short"]["total_calculations"], 1)
        self.assertEqual(metrics["strata"]["short"]["avg_calculation_time"], 10.0)
        self.assertEqual(metrics["strata"]["short"]["avg_nodes_explored"], 15.0)
        self.assertEqual(metrics["strata"]["short"]["avg_optimality_ratio"], 1.0)

        # Setup a medium path
        self.graph.add_edge(3, 4, key=0, length=600.0)
        self.graph.add_edge(4, 3, key=0, length=600.0)
        medium_path = [2, 3, 4]  # length = 100m + 600m = 700m

        # Record a run for medium path
        record_route_metrics(
            metrics,
            calc_time_ms=25.0,
            nodes_explored=40,
            path_length=3,
            memory_bytes=2048,
            optimality_ratio=1.1,
            heuristic_effectiveness=0.85,
            graph=self.graph,
            path=medium_path,
        )

        self.assertEqual(metrics["strata"]["medium"]["total_calculations"], 1)
        self.assertEqual(metrics["strata"]["medium"]["avg_calculation_time"], 25.0)
        self.assertEqual(metrics["strata"]["medium"]["avg_nodes_explored"], 40.0)
        self.assertEqual(metrics["strata"]["medium"]["avg_optimality_ratio"], 1.1)
        self.assertEqual(
            metrics["strata"]["medium"]["avg_heuristic_effectiveness"], 0.85
        )

        # Check payload serialization
        payload = build_metrics_payload(metrics, self.graph, 0, 0, 0)
        self.assertIn("strata", payload)
        self.assertEqual(payload["strata"]["short"]["total_calculations"], 1)
        self.assertEqual(payload["strata"]["medium"]["total_calculations"], 1)
        self.assertEqual(payload["strata"]["long"]["total_calculations"], 0)


if __name__ == "__main__":
    unittest.main()
