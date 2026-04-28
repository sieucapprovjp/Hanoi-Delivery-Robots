import unittest

from delivery_robots import build_route_response


class FakeGraph:
    def __init__(self):
        self._nodes = {
            1: {"y": 21.0, "x": 105.0},
            2: {"y": 21.001, "x": 105.001},
        }
        self._edges = {
            (1, 2): {0: {"length": 100.0}},
        }

    @property
    def nodes(self):
        return self._nodes

    def get_edge_data(self, from_node, to_node):
        return self._edges[(from_node, to_node)]


class RouteAnalysisTests(unittest.TestCase):
    def test_build_route_response_includes_obstacle_penalty(self):
        graph = FakeGraph()
        payload = build_route_response(
            graph,
            [1, 2],
            traffic_penalty_for_point=lambda lat, lon: 1.5,
            rain_penalty_for_point=lambda lat, lon: 2.0,
            obstacle_penalty_for_point=lambda lat, lon: 1.2,
        )

        self.assertEqual(payload["costBreakdown"]["baseDistance"], 100.0)
        self.assertEqual(payload["costBreakdown"]["trafficPenalty"], 50.0)
        self.assertEqual(payload["costBreakdown"]["rainPenalty"], 100.0)
        self.assertEqual(payload["costBreakdown"]["obstaclePenalty"], 20.0)
        self.assertEqual(payload["costBreakdown"]["totalCost"], 270.0)


if __name__ == "__main__":
    unittest.main()
