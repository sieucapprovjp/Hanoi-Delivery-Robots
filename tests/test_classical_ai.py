import unittest

import networkx as nx

from delivery_robots import compare_classical_algorithms


def build_graph():
    graph = nx.MultiDiGraph()
    graph.add_node(1, y=21.0000, x=105.0000)
    graph.add_node(2, y=21.0010, x=105.0010)
    graph.add_node(3, y=21.0020, x=105.0020)
    graph.add_edge(1, 2, length=100.0)
    graph.add_edge(2, 3, length=120.0)
    graph.add_edge(1, 3, length=260.0)
    graph.add_edge(2, 1, length=100.0)
    graph.add_edge(3, 2, length=120.0)
    graph.add_edge(3, 1, length=260.0)
    return graph


class ClassicalAiTests(unittest.TestCase):
    def test_compare_returns_all_algorithms(self):
        graph = build_graph()
        result = compare_classical_algorithms(graph, 1, 3, 21.0020, 105.0020)
        algorithms = result["algorithms"]

        self.assertIn("Dijkstra", algorithms)
        self.assertIn("A*", algorithms)
        self.assertIn("Greedy Best-First", algorithms)
        self.assertIn("BFS", algorithms)
        self.assertEqual(result["bestPathCost"], 220.0)
        self.assertTrue(algorithms["Dijkstra"]["found"])
        self.assertTrue(algorithms["A*"]["found"])


if __name__ == "__main__":
    unittest.main()
