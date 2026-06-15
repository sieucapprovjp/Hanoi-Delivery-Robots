import json
import unittest

import networkx as nx
import numpy as np

from delivery_robots.algorithms.insider import run_astep_demo


def flat_penalty(lat, lon):
    return 1.0


class InsiderAlgorithmTests(unittest.TestCase):
    def test_astep_demo_returns_json_safe_node_ids(self):
        graph = nx.MultiDiGraph()
        start = np.int64(10)
        mid = np.int64(20)
        end = np.int64(30)
        graph.add_node(start, y=21.0000, x=105.0000)
        graph.add_node(mid, y=21.0010, x=105.0010)
        graph.add_node(end, y=21.0020, x=105.0020)
        graph.add_edge(start, mid, length=100.0)
        graph.add_edge(mid, end, length=100.0)

        payload = run_astep_demo(
            graph,
            start,
            end,
            21.0020,
            105.0020,
            flat_penalty,
            flat_penalty,
            flat_penalty,
        )

        json.dumps(payload)
        self.assertEqual(payload["startNode"], 10)
        self.assertEqual(payload["endNode"], 30)
        self.assertIsInstance(payload["steps"][0]["currentNode"], int)


if __name__ == "__main__":
    unittest.main()
