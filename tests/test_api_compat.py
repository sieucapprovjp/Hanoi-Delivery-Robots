import unittest

import networkx as nx
from flask import Flask

from delivery_robots.routes.main_routes import register_main_routes


def build_graph():
    graph = nx.MultiDiGraph()
    graph.add_node(1, y=21.000, x=105.000)
    graph.add_node(2, y=21.001, x=105.000)
    graph.add_node(3, y=21.002, x=105.000)
    graph.add_node(4, y=21.003, x=105.000)
    graph.add_node(5, y=21.004, x=105.000)
    graph.add_node(6, y=21.005, x=105.000)
    for node in range(1, 6):
        graph.add_edge(node, node + 1, length=100.0)
        graph.add_edge(node + 1, node, length=100.0)
    return graph


def nearest_node_id(graph, lat, lon):
    return min(
        graph.nodes,
        key=lambda node: abs(graph.nodes[node]["y"] - lat)
        + abs(graph.nodes[node]["x"] - lon),
    )


def edge_weight(_from_node, _to_node, edge_data):
    if "length" in edge_data:
        return edge_data["length"]
    return min(data.get("length", 1.0) for data in edge_data.values())


class ApiCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.graph = build_graph()
        self.app = Flask(__name__)
        state = {
            "charging_stations": [{"name": "Hub A", "lat": 21.0, "lon": 105.0}],
            "delivery_history": [],
            "history_lock": None,
            "dispatch_model": "nearest_idle",
        }
        ctx = {
            "app_state": state,
            "get_road_graph": lambda: (self.graph, None, []),
            "nearest_node_id": nearest_node_id,
            "validate_coordinate": lambda value, name: float(value),
            "validate_lat_lon": lambda lat, lon: None,
            "edge_weight_with_traffic": edge_weight,
        }
        register_main_routes(self.app, ctx)
        self.client = self.app.test_client()

    def test_snap_returns_nearest_node_coordinates(self):
        response = self.client.get("/api/snap?lat=21.0011&lon=105.0")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["nodeId"], 2)
        self.assertAlmostEqual(payload["lat"], 21.001)

    def test_dispatch_assign_returns_assignments_and_explanations(self):
        response = self.client.post(
            "/api/dispatch/assign",
            json={
                "robots": [
                    {
                        "id": "r1",
                        "name": "Robot 1",
                        "lat": 21.000,
                        "lon": 105.000,
                        "battery": 100,
                        "status": "idle",
                        "capacity": 3,
                    }
                ],
                "deliveries": [
                    {
                        "id": "o1",
                        "pickup": {"lat": 21.001, "lon": 105.000, "name": "P1"},
                        "destination": {
                            "lat": 21.002,
                            "lon": 105.000,
                            "name": "D1",
                        },
                    },
                    {
                        "id": "o2",
                        "pickup": {"lat": 21.003, "lon": 105.000, "name": "P2"},
                        "destination": {
                            "lat": 21.004,
                            "lon": 105.000,
                            "name": "D2",
                        },
                    },
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload["assignments"]), 1)
        self.assertEqual(payload["assignments"][0]["robotId"], "r1")
        self.assertEqual(payload["assignments"][0]["deliveryIds"], ["o1", "o2"])
        self.assertIn("orderSequence", payload["assignments"][0])
        self.assertEqual(len(payload["explanations"]), 1)
        self.assertEqual(payload["explanations"][0]["selectedRobotId"], "r1")

    def test_dispatch_assign_empty_payload_is_successful_noop(self):
        response = self.client.post("/api/dispatch/assign", json={})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"assignments": [], "explanations": []})


if __name__ == "__main__":
    unittest.main()
