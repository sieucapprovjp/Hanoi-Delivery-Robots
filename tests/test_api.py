import unittest
import importlib

import networkx as nx

appcore = importlib.import_module("delivery_robots.app")


def build_test_graph():
    graph = nx.MultiDiGraph()
    graph.add_node(1, y=21.0000, x=105.0000)
    graph.add_node(2, y=21.0010, x=105.0010)
    graph.add_node(3, y=21.0020, x=105.0020)
    graph.add_edge(1, 2, length=100.0)
    graph.add_edge(2, 3, length=120.0)
    graph.add_edge(2, 1, length=100.0)
    graph.add_edge(3, 2, length=120.0)
    return graph


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.graph = build_test_graph()

        self._orig_get_road_graph = appcore.get_road_graph
        self._orig_road_graph = appcore._road_graph
        self._orig_projected_graph = appcore._projected_road_graph
        self._orig_ox = appcore._ox
        self._orig_rain_zones = list(appcore.RAIN_ZONES)
        self._orig_dynamic_routes = list(appcore._dynamic_traffic_routes)
        self._orig_obstacles = list(appcore._obstacles)

        appcore._ox = None
        appcore._road_graph = self.graph
        appcore._projected_road_graph = None
        appcore.RAIN_ZONES = []
        with appcore._dynamic_traffic_lock:
            appcore._dynamic_traffic_routes = []
        with appcore._obstacles_lock:
            appcore._obstacles = []

        def fake_get_road_graph():
            return self.graph, None, []

        appcore.get_road_graph = fake_get_road_graph
        self.client = appcore.app.test_client()

    def tearDown(self):
        appcore.get_road_graph = self._orig_get_road_graph
        appcore._road_graph = self._orig_road_graph
        appcore._projected_road_graph = self._orig_projected_graph
        appcore._ox = self._orig_ox
        appcore.RAIN_ZONES = self._orig_rain_zones
        with appcore._dynamic_traffic_lock:
            appcore._dynamic_traffic_routes = self._orig_dynamic_routes
        with appcore._obstacles_lock:
            appcore._obstacles = self._orig_obstacles

    def test_health(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["status"], "ok")

    def test_add_traffic_route(self):
        resp = self.client.post(
            "/api/traffic/add",
            json={
                "startLat": 21.0000,
                "startLon": 105.0000,
                "endLat": 21.0020,
                "endLon": 105.0020,
                "severity": 0.8,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("route", data)
        self.assertGreater(len(data["route"]["path"]), 1)
        self.assertAlmostEqual(data["route"]["severity"], 0.8, places=2)

        list_resp = self.client.get("/api/traffic/list")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(len(list_resp.get_json()["routes"]), 1)

    def test_add_traffic_route_rejects_same_point(self):
        resp = self.client.post(
            "/api/traffic/add",
            json={
                "startLat": 21.0000,
                "startLon": 105.0000,
                "endLat": 21.0000,
                "endLon": 105.0000,
            },
        )
        self.assertEqual(resp.status_code, 400)

    def test_route_includes_cost_breakdown(self):
        resp = self.client.get(
            "/api/route?fromLat=21.0000&fromLon=105.0000&toLat=21.0020&toLon=105.0020"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("costBreakdown", data)
        breakdown = data["costBreakdown"]
        self.assertIn("obstaclePenalty", breakdown)
        self.assertIn("estimatedMinutes", breakdown)

    def test_rain_add_validates_radius(self):
        resp = self.client.post(
            "/api/rain/add",
            json={"lat": 21.0, "lon": 105.0, "radius": 0},
        )
        self.assertEqual(resp.status_code, 400)

    def test_scenario_load_and_active_api(self):
        # Initial active scenario should be None
        resp_active = self.client.get("/api/scenario/active")
        self.assertEqual(resp_active.status_code, 200)
        self.assertIsNone(resp_active.get_json()["scenario"])

        # Load scenario via POST
        scenario_data = {
            "seed": 999,
            "params": {"dispatch_model": "hungarian"},
            "events": [
                {
                    "type": "RAIN_ADDED",
                    "data": {"lat": 21.0, "lon": 105.0, "radius": 150},
                    "sim_time": 50.0,
                }
            ],
        }
        resp_load = self.client.post("/api/scenario/load", json=scenario_data)
        self.assertEqual(resp_load.status_code, 200)
        self.assertEqual(resp_load.get_json()["status"], "ok")
        self.assertEqual(resp_load.get_json()["seed"], 999)

        # Active scenario should now be populated
        resp_active = self.client.get("/api/scenario/active")
        self.assertEqual(resp_active.status_code, 200)
        active_data = resp_active.get_json()["scenario"]
        self.assertIsNotNone(active_data)
        self.assertEqual(active_data["seed"], 999)
        self.assertEqual(active_data["params"]["dispatch_model"], "hungarian")
        self.assertEqual(len(active_data["events"]), 1)
        self.assertEqual(active_data["events"][0]["type"], "RAIN_ADDED")

        # Check that parameter was applied to app state
        self.assertEqual(appcore._app_state["dispatch_model"], "hungarian")


if __name__ == "__main__":
    unittest.main()
