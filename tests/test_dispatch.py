import unittest
import networkx as nx
from typing import Any

from delivery_robots.algorithms.base import SearchInput, AlgoResult, AssignmentInput
from delivery_robots.algorithms.astar import AStarSearch
from delivery_robots.algorithms.assignment import (
    NearestIdleAssignment,
    NearestFeasibleAssignment,
    WeightedCostAssignment,
    HungarianAssignment,
    compute_battery_cost,
)


class MockRobot:
    """Mock RobotAgent for assignment tests."""

    def __init__(
        self, robot_id: int, name: str, lat: float, lon: float, battery: float
    ):
        self.robot_id = robot_id
        self.name = name
        self.lat = lat
        self.lon = lon
        self.battery = battery
        self.status = "idle"


class DispatchModelTests(unittest.TestCase):
    def setUp(self):
        # Setup simple graph representing street coordinates
        self.graph = nx.MultiDiGraph()

        # Add nodes with coordinates: (node_id, x=longitude, y=latitude)
        self.graph.add_node(1, x=105.000, y=21.000)  # Robot 1 pos
        self.graph.add_node(2, x=105.000, y=21.001)  # Order 1 pickup
        self.graph.add_node(3, x=105.000, y=21.002)  # Order 1 delivery

        self.graph.add_node(4, x=105.010, y=21.010)  # Robot 2 pos
        self.graph.add_node(5, x=105.010, y=21.011)  # Order 2 pickup
        self.graph.add_node(6, x=105.010, y=21.012)  # Order 2 delivery

        # Set up edge lengths (meters)
        # Robot 1 to pickup 1: 120m
        self.graph.add_edge(1, 2, length=120.0)
        # Pickup 1 to delivery 1: 120m
        self.graph.add_edge(2, 3, length=120.0)
        # Robot 2 to pickup 2: 120m
        self.graph.add_edge(4, 5, length=120.0)
        # Pickup 2 to delivery 2: 120m
        self.graph.add_edge(5, 6, length=120.0)

        # Cross edges for matching comparisons
        self.graph.add_edge(1, 5, length=500.0)
        self.graph.add_edge(4, 2, length=500.0)

        # Helper functions
        self.nearest_node_fn = lambda g, lat, lon: min(
            g.nodes,
            key=lambda n: abs(g.nodes[n]["y"] - lat) + abs(g.nodes[n]["x"] - lon),
        )
        self.weight_fn = lambda u, v, d: (
            d.get("length", 1.0)
            if "length" in d
            else min(edge.get("length", 1.0) for edge in d.values())
        )

        def mock_search_fn(
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

        self.run_route_search_fn = mock_search_fn

    def test_battery_cost_calculation(self):
        # 120m distance. Speed: 2 m/s. Base depletion: 1/60 per sec
        # Duration: 60 sec. Depletion: 60 * (1/60) = 1.0%
        cost = compute_battery_cost(self.graph, [1, 2])
        self.assertAlmostEqual(cost, 1.0)

    def test_nearest_idle_assignment(self):
        r1 = MockRobot(1, "Robot 1", 21.000, 105.000, 100.0)
        r2 = MockRobot(2, "Robot 2", 21.010, 105.010, 100.0)

        order = {
            "id": "ORDER-1",
            "pickup": {"lat": 21.001, "lon": 105.000},
            "dropoff": {"lat": 21.002, "lon": 105.000},
        }

        context = AssignmentInput(
            graph=self.graph,
            robots=[r1, r2],
            orders=[order],
            nearest_node_fn=self.nearest_node_fn,
            weight_fn=self.weight_fn,
            run_route_search_fn=self.run_route_search_fn,
        )

        result = NearestIdleAssignment().execute(context)
        self.assertEqual(len(result.assignments), 1)
        self.assertEqual(result.assignments[0].robot.name, "Robot 1")
        self.assertEqual(result.assignments[0].order["id"], "ORDER-1")

    def test_nearest_feasible_assignment(self):
        # Robot 1 is closer (120m to pickup), but has very low battery (0.5%)
        # Total cost is Robot -> Pickup -> Delivery (120m + 120m = 240m -> 2.0% battery required)
        r1 = MockRobot(1, "Robot 1", 21.000, 105.000, 0.5)
        # Robot 2 is further (500m to pickup), but has 100% battery
        r2 = MockRobot(2, "Robot 2", 21.010, 105.010, 100.0)

        order = {
            "id": "ORDER-1",
            "pickup": {"lat": 21.001, "lon": 105.000},
            "dropoff": {"lat": 21.002, "lon": 105.000},
        }

        context = AssignmentInput(
            graph=self.graph,
            robots=[r1, r2],
            orders=[order],
            nearest_node_fn=self.nearest_node_fn,
            weight_fn=self.weight_fn,
            run_route_search_fn=self.run_route_search_fn,
        )

        # Nearest Idle would choose Robot 1 because it's closer
        res_idle = NearestIdleAssignment().execute(context)
        self.assertEqual(res_idle.assignments[0].robot.name, "Robot 1")

        # Nearest Feasible must choose Robot 2 since Robot 1 has insufficient battery
        res_feasible = NearestFeasibleAssignment().execute(context)
        self.assertEqual(len(res_feasible.assignments), 1)
        self.assertEqual(res_feasible.assignments[0].robot.name, "Robot 2")

    def test_weighted_cost_assignment(self):
        # Robot 1: closer, battery = 5% (high penalty)
        r1 = MockRobot(1, "Robot 1", 21.000, 105.000, 5.0)
        # Robot 2: further, battery = 100% (low penalty)
        r2 = MockRobot(2, "Robot 2", 21.010, 105.010, 100.0)

        order = {
            "id": "ORDER-1",
            "pickup": {"lat": 21.001, "lon": 105.000},
            "dropoff": {"lat": 21.002, "lon": 105.000},
        }

        context = AssignmentInput(
            graph=self.graph,
            robots=[r1, r2],
            orders=[order],
            nearest_node_fn=self.nearest_node_fn,
            weight_fn=self.weight_fn,
            run_route_search_fn=self.run_route_search_fn,
            alpha=1.0,
            beta=1.0,
            gamma=1000.0,  # Very high battery penalty weight
            val_lambda=0.05,
        )

        result = WeightedCostAssignment().execute(context)
        self.assertEqual(len(result.assignments), 1)
        # Robot 2 should be chosen due to the massive battery penalty of Robot 1
        self.assertEqual(result.assignments[0].robot.name, "Robot 2")

    def test_hungarian_assignment(self):
        # We test a global optimization scenario:
        # Robot 1 is slightly closer to Order 1 (120m vs 500m)
        # Robot 2 is very close to Order 2 (120m) and slightly further from Order 1 (500m)
        # If we assign greedily:
        # Order 1 (processed first) matches to Robot 2 (cost 500m? No, wait:
        #   Robot 1 to Order 1 = 120m
        #   Robot 2 to Order 1 = 500m
        #   Robot 1 to Order 2 = 500m
        #   Robot 2 to Order 2 = 120m

        # Let's adjust the positions and cross weights so that greedy choice is suboptimal:
        # Robot 1 (pos node 1)
        # Robot 2 (pos node 4)
        # Order 1 (pickup node 2)
        # Order 2 (pickup node 5)
        # Lengths:
        # R1 -> P1 = 110m, R1 -> P2 = 1000m
        # R2 -> P1 = 100m, R2 -> P2 = 200m

        # Clear existing cross edges to define specific lengths
        self.graph.clear_edges()
        self.graph.add_edge(1, 2, length=110.0)  # R1 -> P1
        self.graph.add_edge(2, 3, length=100.0)  # P1 -> D1
        self.graph.add_edge(1, 5, length=1000.0)  # R1 -> P2
        self.graph.add_edge(5, 6, length=100.0)  # P2 -> D2
        self.graph.add_edge(4, 2, length=100.0)  # R2 -> P1
        self.graph.add_edge(4, 5, length=200.0)  # R2 -> P2

        r1 = MockRobot(1, "Robot 1", 21.000, 105.000, 100.0)
        r2 = MockRobot(2, "Robot 2", 21.010, 105.010, 100.0)

        o1 = {
            "id": "ORDER-1",
            "pickup": {"lat": 21.001, "lon": 105.000},
            "dropoff": {"lat": 21.002, "lon": 105.000},
        }
        o2 = {
            "id": "ORDER-2",
            "pickup": {"lat": 21.011, "lon": 105.010},
            "dropoff": {"lat": 21.012, "lon": 105.010},
        }

        # Greedy / Sequential (WeightedCostAssignment):
        # Order 1: R1 cost is 110 + 100 = 210. R2 cost is 100 + 100 = 200.
        #   R2 is closer -> R2 gets Order 1.
        # Order 2: Only R1 is available. Cost is 1000 + 100 = 1100.
        #   R1 gets Order 2.
        # Total matching cost: 200 + 1100 = 1300.

        # Hungarian:
        # Match R1 -> Order 1 (cost 210)
        # Match R2 -> Order 2 (cost 200 + 200 = 400)
        # Total matching cost: 210 + 400 = 610 (globally optimal).

        context = AssignmentInput(
            graph=self.graph,
            robots=[r1, r2],
            orders=[o1, o2],
            nearest_node_fn=self.nearest_node_fn,
            weight_fn=self.weight_fn,
            run_route_search_fn=self.run_route_search_fn,
            alpha=1.0,
            beta=1.0,
            gamma=0.0,  # Disable battery penalty for distance matching simplicity
            val_lambda=0.05,
        )

        greedy_res = WeightedCostAssignment().execute(context)
        # Verify greedy matches R2 -> ORDER-1 and R1 -> ORDER-2
        greedy_map = {a.robot.name: a.order["id"] for a in greedy_res.assignments}
        self.assertEqual(greedy_map["Robot 2"], "ORDER-1")
        self.assertEqual(greedy_map["Robot 1"], "ORDER-2")

        hungarian_res = HungarianAssignment().execute(context)
        # Verify Hungarian matches R1 -> ORDER-1 and R2 -> ORDER-2
        hungarian_map = {a.robot.name: a.order["id"] for a in hungarian_res.assignments}
        self.assertEqual(hungarian_map["Robot 1"], "ORDER-1")
        self.assertEqual(hungarian_map["Robot 2"], "ORDER-2")


class ThreeLegRoutingTests(unittest.TestCase):
    def setUp(self):
        import simpy
        import threading
        from unittest.mock import MagicMock
        from delivery_robots.core.simulation.simulator import SimulatorManager
        from delivery_robots.core.simulation.robot_agent import RobotAgent

        self.graph = nx.MultiDiGraph()

        # Coordinates
        self.graph.add_node(1, x=105.000, y=21.000)
        self.graph.add_node(2, x=105.000, y=21.004)
        self.graph.add_node(3, x=105.000, y=21.006)
        self.graph.add_node(4, x=105.000, y=21.002)

        # Lengths
        self.graph.add_edge(1, 4, length=240.0)
        self.graph.add_edge(4, 2, length=240.0)
        self.graph.add_edge(2, 3, length=240.0)
        self.graph.add_edge(1, 2, length=480.0)

        # Standard helpers
        self.nearest_node_fn = lambda g, lat, lon: min(
            g.nodes,
            key=lambda n: abs(g.nodes[n]["y"] - lat) + abs(g.nodes[n]["x"] - lon),
        )
        self.weight_fn = lambda u, v, d: (
            d.get("length", 1.0)
            if "length" in d
            else min(edge.get("length", 1.0) for edge in d.values())
        )

        def mock_search_fn(
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

        self.run_route_search_fn = mock_search_fn

        # App State
        self.state = {
            "road_graph": self.graph,
            "graph_lock": threading.Lock(),
            "obstacles_lock": threading.Lock(),
            "dynamic_traffic_lock": threading.Lock(),
            "history_lock": threading.Lock(),
            "api_logs_lock": threading.Lock(),
            "delivery_history": [],
            "traffic_routes": [],
            "dynamic_traffic_routes": [],
            "rain_zones": [],
            "obstacles": [],
            "rush_hours": [],
            "charging_stations": [
                {"lat": 21.002, "lon": 105.000, "name": "Hub A", "spots": 1}
            ],
            "hub_resources": {},
            "order_queue": [],
            "dispatch_model": "nearest_idle",
            "robots": [],
            "sim_now": 0.0,
        }

        # Setup SimulatorManager but mock socketio
        self.socketio_mock = MagicMock()
        self.sim_manager = SimulatorManager(
            socketio=self.socketio_mock,
            app_state=self.state,
            nearest_node_id=self.nearest_node_fn,
            run_weighted_route_search=self.run_route_search_fn,
            edge_weight_with_traffic=self.weight_fn,
            build_route_geometry=lambda g, p: ([], []),
        )

        self.env = self.sim_manager.env
        self.state["hub_resources"]["Hub A"] = simpy.Resource(self.env, capacity=1)

        # Manually create robot with full battery to stay IDLE
        self.robot = RobotAgent(
            env=self.env,
            robot_id=0,
            name="TestRobot",
            color="red",
            start_lat=21.000,
            start_lon=105.000,
            app_state=self.state,
            on_state_change=None,
        )
        self.robot.battery = 100.0
        self.sim_manager.robots = [self.robot]
        self.state["robots"] = [self.robot]

    def test_3_leg_route_generation_and_execution(self):
        # Let the environment start and robot go to sleep in IDLE state
        self.env.run(until=2)
        self.assertEqual(self.robot.status, "idle")

        # Now manually lower battery to 5.0% so it needs to charge for the order
        self.robot.battery = 5.0

        # Add order
        order = {
            "id": "ORDER-1",
            "pickup": {"lat": 21.004, "lon": 105.000},
            "dropoff": {"lat": 21.006, "lon": 105.000},
        }
        self.sim_manager.order_manager.add_order(order)

        # Run dispatcher process
        self.env.process(self.sim_manager._dispatcher_process())
        self.env.run(until=20)

        # Verify that the order was assigned
        self.assertEqual(order["status"], "assigned")
        self.assertTrue(order.get("is_3_leg"))
        self.assertEqual(order.get("charging_station")["name"], "Hub A")
        self.assertEqual(order.get("charge_path"), [1, 4])
        self.assertEqual(order.get("pickup_path"), [4, 2])
        self.assertEqual(order.get("dropoff_path"), [2, 3])

        # Run the simulation loop to let the robot move, charge, and deliver
        self.env.run(until=3000)

        # Verify robot has completed the task and battery is charged/used correctly
        self.assertEqual(order["status"], "delivered")
        self.assertEqual(self.robot.status, "idle")


class ReassignmentTests(unittest.TestCase):
    def setUp(self):
        import threading
        from unittest.mock import MagicMock
        from delivery_robots.core.simulation.simulator import SimulatorManager
        from delivery_robots.core.simulation.robot_agent import RobotAgent

        self.graph = nx.MultiDiGraph()

        # Coordinates
        self.graph.add_node(1, x=105.000, y=21.000)  # Robot A start
        self.graph.add_node(2, x=105.000, y=21.004)  # Pickup
        self.graph.add_node(3, x=105.000, y=21.006)  # Delivery
        self.graph.add_node(4, x=105.005, y=21.004)  # Robot B start
        self.graph.add_node(5, x=105.005, y=21.002)  # Robot C start (even closer)

        # Edges
        self.graph.add_edge(1, 2, length=400.0)
        self.graph.add_edge(4, 2, length=200.0)
        self.graph.add_edge(5, 2, length=10.0)
        self.graph.add_edge(2, 3, length=200.0)

        # Standard helpers
        self.nearest_node_fn = lambda g, lat, lon: min(
            g.nodes,
            key=lambda n: abs(g.nodes[n]["y"] - lat) + abs(g.nodes[n]["x"] - lon),
        )
        self.weight_fn = lambda u, v, d: (
            d.get("length", 1.0)
            if "length" in d
            else min(edge.get("length", 1.0) for edge in d.values())
        )

        def mock_search_fn(
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

        self.run_route_search_fn = mock_search_fn

        # App State
        self.state = {
            "road_graph": self.graph,
            "graph_lock": threading.Lock(),
            "obstacles_lock": threading.Lock(),
            "dynamic_traffic_lock": threading.Lock(),
            "history_lock": threading.Lock(),
            "api_logs_lock": threading.Lock(),
            "delivery_history": [],
            "traffic_routes": [],
            "dynamic_traffic_routes": [],
            "rain_zones": [],
            "obstacles": [],
            "rush_hours": [],
            "charging_stations": [],
            "hub_resources": {},
            "order_queue": [],
            "dispatch_model": "nearest_idle",
            "robots": [],
            "sim_now": 0.0,
        }

        self.socketio_mock = MagicMock()
        self.sim_manager = SimulatorManager(
            socketio=self.socketio_mock,
            app_state=self.state,
            nearest_node_id=self.nearest_node_fn,
            run_weighted_route_search=self.run_route_search_fn,
            edge_weight_with_traffic=self.weight_fn,
            build_route_geometry=lambda g, p: ([], []),
        )

        self.env = self.sim_manager.env

        # Create Robot A
        self.robot_a = RobotAgent(
            env=self.env,
            robot_id=0,
            name="Robot A",
            color="red",
            start_lat=21.000,
            start_lon=105.000,
            app_state=self.state,
            on_state_change=None,
        )
        self.robot_a.battery = 100.0

        # Create Robot B
        self.robot_b = RobotAgent(
            env=self.env,
            robot_id=1,
            name="Robot B",
            color="blue",
            start_lat=21.004,
            start_lon=105.005,
            app_state=self.state,
            on_state_change=None,
        )
        self.robot_b.battery = 100.0

        # Create Robot C
        self.robot_c = RobotAgent(
            env=self.env,
            robot_id=2,
            name="Robot C",
            color="green",
            start_lat=21.002,
            start_lon=105.005,
            app_state=self.state,
            on_state_change=None,
        )
        self.robot_c.battery = 100.0

        self.sim_manager.robots = [self.robot_a]
        self.state["robots"] = [self.robot_a]

    def test_reassignment_trigger_and_anti_chatter(self):
        order = {
            "id": "ORDER-1",
            "pickup": {"lat": 21.004, "lon": 105.000},
            "dropoff": {"lat": 21.006, "lon": 105.000},
        }
        self.sim_manager.order_manager.add_order(order)

        # Let simulation run briefly to sleep robots
        self.env.run(until=2)

        # Dispatch order. Since only Robot A is idle, it should be assigned to Robot A.
        self.env.process(self.sim_manager._dispatcher_process())
        self.env.run(until=20)

        self.assertEqual(order["status"], "assigned")
        self.assertEqual(self.robot_a.status, "moving_to_pickup")
        self.assertEqual(self.robot_a.current_task["id"], "ORDER-1")

        # 2. Now, Robot B is added to the active robots list. It is much closer (50m vs 400m remaining).
        self.sim_manager.robots.append(self.robot_b)
        self.state["robots"].append(self.robot_b)

        # Run dispatcher tick
        self.env.run(until=40)

        # Verify reassignment occurred: Robot B took over, Robot A became idle
        self.assertEqual(self.robot_b.status, "moving_to_pickup")
        self.assertEqual(self.robot_a.status, "idle")
        self.assertEqual(order["reassign_count"], 1)
        self.assertEqual(order["last_reassign_time"], 22.0)

        # 3. Test Cooldown: Robot C is added now.
        self.sim_manager.robots.append(self.robot_c)
        self.state["robots"].append(self.robot_c)

        # If we change graph edge length of 4 -> 2 to 400.0, then B -> Pickup remaining cost is 400.0.
        # C -> Pickup is 10. Cost improvement: 400 - 10 = 390 > 60.
        # But since cooldown (60s) has not passed, it should NOT trigger.
        self.graph[4][2][0]["length"] = 400.0  # Make B further

        self.env.run(until=80)  # still within cooldown (22 + 60 = 82)
        # Verify no reassignment happened (still assigned to B)
        self.assertEqual(self.robot_b.status, "moving_to_pickup")
        self.assertEqual(self.robot_c.status, "idle")
        self.assertEqual(order["reassign_count"], 1)

        # Run until after cooldown (sim time 84)
        self.env.run(until=84)
        # Verify reassignment to Robot C occurred
        self.assertEqual(self.robot_c.status, "moving_to_pickup")
        self.assertEqual(self.robot_b.status, "idle")
        self.assertEqual(order["reassign_count"], 2)
        self.assertEqual(order["last_reassign_time"], 82.0)

        # 4. Test Max Limit: Try to reassign again (limit is 2, so it should be blocked)
        # Let's make Robot C distance 400.0.
        # Let's make Robot A extremely close to pickup.
        self.graph[5][2][0]["length"] = 400.0  # Make C further
        self.graph[1][2][0]["length"] = 1.0  # Make A extremely close

        self.env.run(until=200)  # well past cooldown
        # Verify no reassignment happened because limit was reached (still assigned to C)
        self.assertEqual(self.robot_c.status, "moving_to_dropoff")
        self.assertEqual(self.robot_a.status, "idle")
        self.assertEqual(order["reassign_count"], 2)


if __name__ == "__main__":
    unittest.main()
