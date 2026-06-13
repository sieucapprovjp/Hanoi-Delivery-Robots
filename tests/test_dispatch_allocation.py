import math
import unittest
from unittest.mock import patch

import networkx as nx

from delivery_robots.algorithms.dispatch import allocation
from delivery_robots.config import DISPATCH_MAX_ROUTE_ETA_MINUTES


def build_dispatch_graph():
    graph = nx.MultiDiGraph()
    graph.add_node(1, y=21.0000, x=105.0000)
    graph.add_node(2, y=21.0005, x=105.0000)
    graph.add_node(3, y=21.0010, x=105.0000)
    graph.add_edge(2, 1, length=80.0)
    graph.add_edge(3, 1, length=100.0)
    return graph


def build_vrp_graph():
    graph = nx.MultiDiGraph()
    coords = {
        0: (21.0000, 105.0000),
        1: (21.0001, 105.0000),
        2: (21.0002, 105.0000),
        3: (21.0003, 105.0000),
        4: (21.0004, 105.0000),
        5: (21.0005, 105.0000),
        6: (21.0006, 105.0000),
    }
    for node_id, (lat, lon) in coords.items():
        graph.add_node(node_id, y=lat, x=lon)
    for from_id in coords:
        for to_id in coords:
            if from_id == to_id:
                continue
            graph.add_edge(from_id, to_id, length=10.0 + abs(from_id - to_id))
    return graph


def nearest_node_id(graph, lat, lon, ox=None):
    for node_id, data in graph.nodes(data=True):
        if data["y"] == lat and data["x"] == lon:
            return node_id
    raise ValueError("No matching node")


def edge_weight(graph, from_node, to_node, edge_data):
    if "length" in edge_data:
        return edge_data["length"]
    return min(data["length"] for data in edge_data.values())


def noop_record_metrics(metrics, calc_time, nodes_explored, path_length):
    metrics["calls"] = metrics.get("calls", 0) + 1


def flat_penalty(lat, lon):
    return 1.0


def build_delivery():
    return {
        "id": "delivery-1",
        "pickup": {"lat": 21.0000, "lon": 105.0000, "name": "Pickup"},
        "destination": {"lat": 21.0020, "lon": 105.0000, "name": "Dropoff"},
        "createdAt": 0,
        "theme": {"pickupCategory": "restaurant", "dropoffCategory": "residential"},
    }


def build_vrp_delivery(delivery_id, pickup_node, dropoff_node, graph):
    pickup = graph.nodes[pickup_node]
    dropoff = graph.nodes[dropoff_node]
    return {
        "id": delivery_id,
        "pickup": {
            "lat": pickup["y"],
            "lon": pickup["x"],
            "name": f"Pickup {delivery_id}",
        },
        "destination": {
            "lat": dropoff["y"],
            "lon": dropoff["x"],
            "name": f"Dropoff {delivery_id}",
        },
        "createdAt": 0,
        "theme": {"pickupCategory": "restaurant", "dropoffCategory": "residential"},
    }


class DispatchAllocationTests(unittest.TestCase):
    def test_assign_deliveries_accounts_for_battery_risk(self):
        graph = build_dispatch_graph()
        robots = [
            {
                "id": "near-low-battery",
                "name": "Near Low Battery",
                "lat": 21.0005,
                "lon": 105.0000,
                "battery": 0,
                "routeAlgorithm": "astar",
            },
            {
                "id": "far-healthy-battery",
                "name": "Far Healthy Battery",
                "lat": 21.0010,
                "lon": 105.0000,
                "battery": 100,
                "routeAlgorithm": "astar",
            },
        ]

        result = allocation.assign_deliveries(
            {"ox": None},
            graph,
            robots,
            [build_delivery()],
            0,
            nearest_node_id,
            lambda from_node, to_node, edge_data: edge_weight(
                graph, from_node, to_node, edge_data
            ),
            flat_penalty,
            flat_penalty,
            flat_penalty,
            noop_record_metrics,
            {},
            return_explanations=True,
        )
        assignments = result["assignments"]
        explanation = result["explanations"][0]

        self.assertEqual(assignments[0]["robotId"], "far-healthy-battery")
        self.assertEqual(assignments[0]["route"]["distance"], 100.0)
        self.assertTrue(explanation["cycleId"].startswith("dispatch-0-delivery-1"))
        self.assertEqual(explanation["orderId"], "delivery-1")
        self.assertEqual(explanation["selectedRobotId"], "far-healthy-battery")
        self.assertEqual(explanation["selectedRobotName"], "Far Healthy Battery")
        self.assertIn("lowest total score", explanation["finalExplanation"])
        near_candidate = next(
            item
            for item in explanation["candidates"]
            if item["robotId"] == "near-low-battery"
        )
        self.assertEqual(near_candidate["status"], "rejected")
        self.assertFalse(near_candidate["accepted"])
        self.assertFalse(near_candidate["constraints"]["batteryOk"])
        self.assertEqual(near_candidate["reasons"][0]["code"], "low_battery")
        self.assertEqual(near_candidate["rejectReasons"][0]["code"], "low_battery")
        selected_candidate = next(
            item
            for item in explanation["candidates"]
            if item["robotId"] == "far-healthy-battery"
        )
        self.assertEqual(selected_candidate["status"], "selected")
        self.assertTrue(selected_candidate["accepted"])
        self.assertEqual(selected_candidate["reasons"][0]["code"], "lowest_total_score")
        self.assertEqual(selected_candidate["scores"]["routeCost"], 100.0)
        self.assertEqual(selected_candidate["route"]["algorithm"], "astar")
        self.assertEqual(selected_candidate["route"]["distance"], 100.0)

    def test_assign_deliveries_normalizes_greedy_alias(self):
        graph = build_dispatch_graph()
        robots = [
            {
                "id": "greedy-robot",
                "name": "Greedy Robot",
                "lat": 21.0005,
                "lon": 105.0000,
                "battery": 100,
                "routeAlgorithm": "greedy",
            }
        ]

        assignments = allocation.assign_deliveries(
            {"ox": None},
            graph,
            robots,
            [build_delivery()],
            0,
            nearest_node_id,
            lambda from_node, to_node, edge_data: edge_weight(
                graph, from_node, to_node, edge_data
            ),
            flat_penalty,
            flat_penalty,
            flat_penalty,
            noop_record_metrics,
            {},
        )

        self.assertEqual(assignments[0]["route"]["algo"], "gbfs")

    def test_assign_deliveries_prunes_route_search_candidates(self):
        graph = build_dispatch_graph()
        robots = [
            {
                "id": "near",
                "name": "Near",
                "lat": 21.0005,
                "lon": 105.0000,
                "battery": 100,
                "routeAlgorithm": "astar",
            },
            {
                "id": "far",
                "name": "Far",
                "lat": 21.0010,
                "lon": 105.0000,
                "battery": 100,
                "routeAlgorithm": "astar",
            },
        ]

        with patch.object(allocation, "DISPATCH_MAX_ROUTE_CANDIDATES_PER_DELIVERY", 1):
            with patch.object(allocation, "DISPATCH_HIGH_PRIORITY_SCORE_THRESHOLD", 999):
                with patch.object(
                    allocation,
                    "run_weighted_route_search",
                    side_effect=lambda graph, start_node, end_node, *_: (
                        [start_node, end_node],
                        3,
                    ),
                ) as search_mock:
                    assignments = allocation.assign_deliveries(
                        {"ox": None},
                        graph,
                        robots,
                        [build_delivery()],
                        0,
                        nearest_node_id,
                        lambda from_node, to_node, edge_data: edge_weight(
                            graph, from_node, to_node, edge_data
                        ),
                        flat_penalty,
                        flat_penalty,
                        flat_penalty,
                        noop_record_metrics,
                        {},
                    )

        self.assertEqual(search_mock.call_count, 1)
        self.assertEqual(assignments[0]["robotId"], "near")

    def test_assign_deliveries_rejects_capacity_full_robot(self):
        graph = build_dispatch_graph()
        robots = [
            {
                "id": "full",
                "name": "Full",
                "lat": 21.0005,
                "lon": 105.0000,
                "battery": 100,
                "currentLoad": 1,
                "capacity": 1,
                "routeAlgorithm": "astar",
            },
            {
                "id": "available",
                "name": "Available",
                "lat": 21.0010,
                "lon": 105.0000,
                "battery": 100,
                "currentLoad": 0,
                "capacity": 1,
                "routeAlgorithm": "astar",
            },
        ]

        result = allocation.assign_deliveries(
            {"ox": None},
            graph,
            robots,
            [build_delivery()],
            0,
            nearest_node_id,
            lambda from_node, to_node, edge_data: edge_weight(
                graph, from_node, to_node, edge_data
            ),
            flat_penalty,
            flat_penalty,
            flat_penalty,
            noop_record_metrics,
            {},
            return_explanations=True,
        )

        self.assertEqual(result["assignments"][0]["robotId"], "available")
        full_candidate = next(
            item
            for item in result["explanations"][0]["candidates"]
            if item["robotId"] == "full"
        )
        self.assertEqual(full_candidate["status"], "rejected")
        self.assertEqual(full_candidate["reasons"][0]["code"], "capacity_full")
        self.assertFalse(full_candidate["constraints"]["capacityOk"])
        self.assertEqual(full_candidate["rejectReasons"][0]["code"], "capacity_full")

    def test_assign_deliveries_rejects_busy_robot_with_xai_reason(self):
        graph = build_dispatch_graph()
        robots = [
            {
                "id": "busy",
                "name": "Busy",
                "lat": 21.0005,
                "lon": 105.0000,
                "battery": 100,
                "status": "moving",
                "routeAlgorithm": "astar",
            },
            {
                "id": "idle",
                "name": "Idle",
                "lat": 21.0010,
                "lon": 105.0000,
                "battery": 100,
                "status": "idle",
                "routeAlgorithm": "astar",
            },
        ]

        result = allocation.assign_deliveries(
            {"ox": None},
            graph,
            robots,
            [build_delivery()],
            0,
            nearest_node_id,
            lambda from_node, to_node, edge_data: edge_weight(
                graph, from_node, to_node, edge_data
            ),
            flat_penalty,
            flat_penalty,
            flat_penalty,
            noop_record_metrics,
            {},
            return_explanations=True,
        )

        self.assertEqual(result["assignments"][0]["robotId"], "idle")
        busy_candidate = next(
            item
            for item in result["explanations"][0]["candidates"]
            if item["robotId"] == "busy"
        )
        self.assertEqual(busy_candidate["status"], "rejected")
        self.assertFalse(busy_candidate["accepted"])
        self.assertFalse(busy_candidate["constraints"]["idle"])
        self.assertEqual(busy_candidate["rejectReasons"][0]["code"], "not_idle")

    def test_assign_deliveries_rejects_low_projected_battery_after_route(self):
        graph = build_dispatch_graph()
        for edge_data in graph[2][1].values():
            edge_data["length"] = 3000.0

        robots = [
            {
                "id": "low-reserve",
                "name": "Low Reserve",
                "lat": 21.0005,
                "lon": 105.0000,
                "battery": 20,
                "status": "idle",
                "routeAlgorithm": "astar",
            },
            {
                "id": "healthy",
                "name": "Healthy",
                "lat": 21.0010,
                "lon": 105.0000,
                "battery": 100,
                "status": "idle",
                "routeAlgorithm": "astar",
            },
        ]

        result = allocation.assign_deliveries(
            {"ox": None},
            graph,
            robots,
            [build_delivery()],
            0,
            nearest_node_id,
            lambda from_node, to_node, edge_data: edge_weight(
                graph, from_node, to_node, edge_data
            ),
            flat_penalty,
            flat_penalty,
            flat_penalty,
            noop_record_metrics,
            {},
            return_explanations=True,
        )

        self.assertEqual(result["assignments"][0]["robotId"], "healthy")
        low_reserve_candidate = next(
            item
            for item in result["explanations"][0]["candidates"]
            if item["robotId"] == "low-reserve"
        )
        self.assertEqual(low_reserve_candidate["status"], "rejected")
        self.assertFalse(low_reserve_candidate["accepted"])
        self.assertFalse(low_reserve_candidate["constraints"]["batteryReserveOk"])
        self.assertEqual(
            low_reserve_candidate["rejectReasons"][0]["code"],
            "battery_reserve_too_low",
        )
        self.assertEqual(low_reserve_candidate["route"]["distance"], 3000.0)

    def test_assign_deliveries_rejects_slow_route_after_route(self):
        graph = build_dispatch_graph()
        for edge_data in graph[2][1].values():
            edge_data["length"] = 3000.0

        robots = [
            {
                "id": "slow-route",
                "name": "Slow Route",
                "lat": 21.0005,
                "lon": 105.0000,
                "battery": 100,
                "status": "idle",
                "routeAlgorithm": "astar",
            },
            {
                "id": "fast-route",
                "name": "Fast Route",
                "lat": 21.0010,
                "lon": 105.0000,
                "battery": 100,
                "status": "idle",
                "routeAlgorithm": "astar",
            },
        ]

        result = allocation.assign_deliveries(
            {"ox": None},
            graph,
            robots,
            [build_delivery()],
            0,
            nearest_node_id,
            lambda from_node, to_node, edge_data: edge_weight(
                graph, from_node, to_node, edge_data
            ),
            flat_penalty,
            flat_penalty,
            flat_penalty,
            noop_record_metrics,
            {},
            return_explanations=True,
        )

        self.assertEqual(result["assignments"][0]["robotId"], "fast-route")
        slow_candidate = next(
            item
            for item in result["explanations"][0]["candidates"]
            if item["robotId"] == "slow-route"
        )
        self.assertEqual(slow_candidate["status"], "rejected")
        self.assertFalse(slow_candidate["constraints"]["routeEtaOk"])
        self.assertEqual(
            slow_candidate["rejectReasons"][0]["code"],
            "route_eta_too_high",
        )
        self.assertGreater(
            slow_candidate["route"]["etaMinutes"],
            DISPATCH_MAX_ROUTE_ETA_MINUTES,
        )

    def test_assign_deliveries_batches_with_vrp_when_backlog_exceeds_robots(self):
        graph = build_vrp_graph()
        robots = [
            {
                "id": "vrp-robot",
                "name": "VRP Robot",
                "lat": graph.nodes[0]["y"],
                "lon": graph.nodes[0]["x"],
                "battery": 100,
                "status": "idle",
                "currentLoad": 0,
                "capacity": 10,
                "routeAlgorithm": "astar",
            }
        ]
        deliveries = [
            build_vrp_delivery("a", 1, 4, graph),
            build_vrp_delivery("b", 2, 5, graph),
            build_vrp_delivery("c", 3, 6, graph),
        ]

        with patch.object(allocation, "append_app_event") as log_mock:
            result = allocation.assign_deliveries(
                {"ox": None},
                graph,
                robots,
                deliveries,
                0,
                nearest_node_id,
                lambda from_node, to_node, edge_data: edge_weight(
                    graph, from_node, to_node, edge_data
                ),
                flat_penalty,
                flat_penalty,
                flat_penalty,
                noop_record_metrics,
                {},
                return_explanations=True,
            )

        assignments = result["assignments"]
        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0]["robotId"], "vrp-robot")
        self.assertEqual(assignments[0]["deliveryIds"], ["a", "b", "c"])
        self.assertEqual(len(assignments[0]["orderSequence"]), 6)
        self.assertIn("vrpStats", assignments[0])
        self.assertIn("vrpCost", assignments[0])
        self.assertTrue(assignments[0]["route"]["path"])
        log_mock.assert_called_once()
        self.assertEqual(log_mock.call_args.args[0]["type"], "vrp_result")

        timeline_stages = [
            step["stage"] for step in result["explanations"][0]["timeline"]
        ]
        self.assertIn("vrp_sequence", timeline_stages)
        vrp_explanation = result["explanations"][0]["vrp"]
        self.assertEqual(vrp_explanation["orderCount"], 3)
        self.assertEqual(vrp_explanation["deliveryIds"], ["a", "b", "c"])
        self.assertEqual(len(vrp_explanation["sequence"]), 6)
        self.assertIn("iterations", vrp_explanation["stats"])
        self.assertIn("acceptedMoves", vrp_explanation["stats"])

    def test_vrp_distance_matrix_tolerates_failed_pair_route(self):
        robot = {"lat": 21.0, "lon": 105.0}
        stops = [
            {
                "stopId": "P1",
                "type": "pickup",
                "deliveryId": 1,
                "lat": 21.001,
                "lon": 105.0,
            },
            {
                "stopId": "D1",
                "type": "dropoff",
                "deliveryId": 1,
                "lat": 21.002,
                "lon": 105.0,
            },
        ]

        def fake_route(*args):
            from_point = args[1]
            to_point = args[2]
            if from_point["stopId"] == "P1" and to_point["stopId"] == "D1":
                raise RuntimeError("no path")
            return {
                "distance": 12.0,
                "path": [[from_point["lat"], from_point["lon"]]],
                "costBreakdown": {"totalCost": 15.0},
            }

        with patch.object(allocation, "_route_between_points", side_effect=fake_route):
            matrix, route_cache = allocation._build_vrp_distance_matrix(
                None,
                robot,
                stops,
                nearest_node_id,
                {"ox": None},
                None,
                "astar",
                flat_penalty,
                flat_penalty,
                flat_penalty,
            )

        self.assertTrue(math.isinf(matrix["P1"]["D1"]))
        self.assertNotIn(("P1", "D1"), route_cache)
        self.assertEqual(matrix[allocation.START_NODE_ID]["P1"], 15.0)


if __name__ == "__main__":
    unittest.main()
