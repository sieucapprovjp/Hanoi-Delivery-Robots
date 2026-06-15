import unittest
from typing import Any

import networkx as nx

from delivery_robots.algorithms.astar import AStarSearch
from delivery_robots.algorithms.base import AlgoResult, AssignmentInput, SearchInput
from delivery_robots.algorithms.dispatch import run_assignment_with_csp_xai
from delivery_robots.algorithms.dispatch.vrp_solver import check_precedence


class MockRobot:
    def __init__(
        self,
        robot_id: int,
        name: str,
        lat: float,
        lon: float,
        battery: float = 100.0,
        status: str = "idle",
        capacity: int | None = None,
        current_load: int = 0,
    ):
        self.robot_id = robot_id
        self.name = name
        self.lat = lat
        self.lon = lon
        self.battery = battery
        self.status = status
        self.capacity = capacity
        self.currentLoad = current_load
        self.task_queue = []
        self.current_task = None


def build_graph():
    graph = nx.MultiDiGraph()
    graph.add_node(1, x=105.000, y=21.000)
    graph.add_node(2, x=105.000, y=21.001)
    graph.add_node(3, x=105.000, y=21.002)
    graph.add_node(4, x=105.010, y=21.010)

    graph.add_edge(1, 2, length=120.0)
    graph.add_edge(2, 3, length=120.0)
    graph.add_edge(4, 2, length=600.0)
    graph.add_edge(1, 4, length=1000.0)
    graph.add_edge(4, 3, length=700.0)
    return graph


class CspXaiAssignmentTests(unittest.TestCase):
    def setUp(self):
        self.graph = build_graph()
        self.nearest_node_fn = lambda g, lat, lon: min(
            g.nodes,
            key=lambda n: abs(g.nodes[n]["y"] - lat) + abs(g.nodes[n]["x"] - lon),
        )
        self.weight_fn = lambda u, v, d: (
            d.get("length", 1.0)
            if "length" in d
            else min(edge.get("length", 1.0) for edge in d.values())
        )

        def route_search(
            graph: nx.MultiDiGraph,
            start_node: int,
            end_node: int,
            goal_lat: float,
            goal_lon: float,
            weight_fn: Any,
            algorithm: str,
        ) -> AlgoResult:
            context = SearchInput(
                graph=graph,
                start_node=start_node,
                end_node=end_node,
                weight_fn=weight_fn,
                goal_lat=goal_lat,
                goal_lon=goal_lon,
            )
            return AStarSearch().execute(context)

        self.route_search = route_search
        self.order = {
            "id": "ORDER-1",
            "pickup": {"lat": 21.001, "lon": 105.000, "name": "Pickup"},
            "dropoff": {"lat": 21.002, "lon": 105.000, "name": "Dropoff"},
        }

    def build_context(self, robots):
        return AssignmentInput(
            graph=self.graph,
            robots=robots,
            orders=[self.order],
            nearest_node_fn=self.nearest_node_fn,
            weight_fn=self.weight_fn,
            run_route_search_fn=self.route_search,
        )

    def build_multi_order_context(self, robots):
        graph = nx.MultiDiGraph()
        coords = {
            1: (21.000, 105.000),
            2: (21.001, 105.000),
            3: (21.002, 105.000),
            4: (21.003, 105.000),
            5: (21.004, 105.000),
            6: (21.005, 105.000),
            7: (21.006, 105.000),
            8: (21.007, 105.000),
            9: (21.008, 105.000),
        }
        for node, (lat, lon) in coords.items():
            graph.add_node(node, x=lon, y=lat)
        for node in range(1, 9):
            graph.add_edge(node, node + 1, length=100.0)
            graph.add_edge(node + 1, node, length=100.0)

        orders = []
        for idx in range(4):
            pickup_node = 2 + idx * 2
            dropoff_node = pickup_node + 1
            pickup_lat, pickup_lon = coords[pickup_node]
            dropoff_lat, dropoff_lon = coords[dropoff_node]
            orders.append(
                {
                    "id": f"ORDER-{idx + 1}",
                    "pickup": {
                        "lat": pickup_lat,
                        "lon": pickup_lon,
                        "name": f"Pickup {idx + 1}",
                    },
                    "dropoff": {
                        "lat": dropoff_lat,
                        "lon": dropoff_lon,
                        "name": f"Dropoff {idx + 1}",
                    },
                }
            )

        nearest_node_fn = lambda g, lat, lon: min(
            g.nodes,
            key=lambda n: abs(g.nodes[n]["y"] - lat) + abs(g.nodes[n]["x"] - lon),
        )

        return AssignmentInput(
            graph=graph,
            robots=robots,
            orders=orders,
            nearest_node_fn=nearest_node_fn,
            weight_fn=self.weight_fn,
            run_route_search_fn=self.route_search,
        )

    def test_rejects_non_idle_robot_and_selects_idle_candidate(self):
        busy_near = MockRobot(1, "Busy", 21.000, 105.000, status="moving_to_pickup")
        idle_far = MockRobot(2, "Idle", 21.010, 105.010)

        result, explanations = run_assignment_with_csp_xai(
            "nearest_idle",
            self.build_context([busy_near, idle_far]),
            app_state={},
            current_time=10.0,
        )

        self.assertEqual(len(result.assignments), 1)
        self.assertEqual(result.assignments[0].robot.name, "Idle")
        explanation = explanations[0]
        rejected = next(c for c in explanation["candidates"] if c["robotName"] == "Busy")
        selected = next(c for c in explanation["candidates"] if c["robotName"] == "Idle")
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["rejectReasons"][0]["code"], "not_idle")
        self.assertEqual(selected["status"], "selected")
        self.assertEqual(explanation["selectedRobotName"], "Idle")

    def test_rejects_full_capacity_robot(self):
        full = MockRobot(1, "Full", 21.000, 105.000, capacity=1, current_load=1)
        open_robot = MockRobot(2, "Open", 21.010, 105.010, capacity=2)

        result, explanations = run_assignment_with_csp_xai(
            "nearest_idle",
            self.build_context([full, open_robot]),
            app_state={},
            current_time=10.0,
        )

        self.assertEqual(result.assignments[0].robot.name, "Open")
        rejected = next(c for c in explanations[0]["candidates"] if c["robotName"] == "Full")
        self.assertEqual(rejected["rejectReasons"][0]["code"], "capacity_full")

    def test_low_battery_robot_with_charging_hub_remains_feasible(self):
        low_battery = MockRobot(1, "Low Battery", 21.000, 105.000, battery=0.5)

        result, explanations = run_assignment_with_csp_xai(
            "nearest_idle",
            self.build_context([low_battery]),
            app_state={"charging_stations": [{"name": "Hub A"}]},
            current_time=10.0,
        )

        self.assertEqual(len(result.assignments), 1)
        self.assertEqual(result.assignments[0].robot.name, "Low Battery")
        candidate = explanations[0]["candidates"][0]
        self.assertEqual(candidate["status"], "selected")
        self.assertTrue(candidate["constraints"]["routeBatteryOk"])
        self.assertTrue(candidate["scores"]["requiresCharging"])

    def test_batches_up_to_robot_capacity_with_vrp_sequence(self):
        robot = MockRobot(1, "Batch Bot", 21.000, 105.000, capacity=3)

        result, explanations = run_assignment_with_csp_xai(
            "nearest_idle",
            self.build_multi_order_context([robot]),
            app_state={"charging_stations": [{"name": "Hub A"}]},
            current_time=10.0,
        )

        self.assertEqual(len(result.assignments), 1)
        task = result.assignments[0].order
        self.assertEqual(len(task["vrp_batch_orders"]), 3)
        self.assertEqual(len(task["vrp_sequence"]), 6)
        self.assertTrue(check_precedence(task["vrp_sequence"]))
        self.assertEqual(explanations[0]["vrp"]["orderCount"], 3)


if __name__ == "__main__":
    unittest.main()
