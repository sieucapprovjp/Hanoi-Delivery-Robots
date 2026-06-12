import unittest
import networkx as nx
from delivery_robots.algorithms.base import (
    SearchContract,
    AssignmentContract,
    ChargingPolicyContract,
    SearchInput,
    AlgoResult,
    ExecutionTrace,
)
from delivery_robots.algorithms.astar import AStarSearch
from delivery_robots.algorithms.dijkstra import DijkstraSearch
from delivery_robots.algorithms.gbfs import GBFSSearch
from delivery_robots.algorithms.dfs import DFSSearch
from delivery_robots.algorithms.bfs import BFSSearch
from delivery_robots.core.environment import SnapFactory


class ContractTests(unittest.TestCase):
    def test_cannot_instantiate_search_contract(self):
        with self.assertRaises(TypeError):
            SearchContract()  # type: ignore

    def test_cannot_instantiate_assignment_contract(self):
        with self.assertRaises(TypeError):
            AssignmentContract()  # type: ignore

    def test_cannot_instantiate_charging_policy_contract(self):
        with self.assertRaises(TypeError):
            ChargingPolicyContract()  # type: ignore

    def test_concrete_search_subclass(self):
        class ConcreteSearch(SearchContract[int, str]):
            def execute(self, context: int) -> str:
                return f"Result: {context}"

        search = ConcreteSearch()
        self.assertEqual(search.execute(42), "Result: 42")

    def test_concrete_assignment_subclass(self):
        class ConcreteAssignment(AssignmentContract[int, str]):
            def execute(self, context: int) -> str:
                return f"Assigned: {context}"

        assignment = ConcreteAssignment()
        self.assertEqual(assignment.execute(7), "Assigned: 7")

    def test_concrete_charging_policy_subclass(self):
        class ConcreteChargingPolicy(ChargingPolicyContract[int, str]):
            def execute(self, context: int) -> str:
                return f"Charge: {context}"

        policy = ConcreteChargingPolicy()
        self.assertEqual(policy.execute(100), "Charge: 100")


class SearchAlgorithmTests(unittest.TestCase):
    def setUp(self):
        self.graph = nx.MultiDiGraph()
        self.graph.add_node(1, x=105.000, y=21.000)
        self.graph.add_node(2, x=105.000, y=21.001)
        self.graph.add_node(3, x=105.000, y=21.002)
        self.graph.add_node(4, x=105.000, y=21.003)
        # 1 -> 2 -> 3 -> 4 (path length 333.0)
        # 1 -> 3 -> 4 (path length 1111.0)
        self.graph.add_edge(1, 2, length=111.0)
        self.graph.add_edge(2, 3, length=111.0)
        self.graph.add_edge(3, 4, length=111.0)
        self.graph.add_edge(1, 3, length=1000.0)

        self.weight_fn = lambda u, v, d: (
            d.get("length", 1.0)
            if "length" in d
            else min(edge.get("length", 1.0) for edge in d.values())
        )

    def test_astar_search(self):
        context = SearchInput(
            graph=self.graph,
            start_node=1,
            end_node=4,
            weight_fn=self.weight_fn,
            goal_lat=21.003,
            goal_lon=105.000,
        )
        path, explored = AStarSearch().execute(context)
        self.assertEqual(path, [1, 2, 3, 4])
        self.assertTrue(explored > 0)

    def test_dijkstra_search(self):
        context = SearchInput(
            graph=self.graph,
            start_node=1,
            end_node=4,
            weight_fn=self.weight_fn,
        )
        path, explored = DijkstraSearch().execute(context)
        self.assertEqual(path, [1, 2, 3, 4])
        self.assertTrue(explored > 0)

    def test_gbfs_search(self):
        context = SearchInput(
            graph=self.graph,
            start_node=1,
            end_node=4,
            weight_fn=self.weight_fn,
            goal_lat=21.003,
            goal_lon=105.000,
        )
        path, explored = GBFSSearch().execute(context)
        self.assertTrue(len(path) >= 2)
        self.assertEqual(path[0], 1)
        self.assertEqual(path[-1], 4)
        self.assertTrue(explored > 0)

    def test_dfs_search(self):
        context = SearchInput(
            graph=self.graph,
            start_node=1,
            end_node=4,
            weight_fn=self.weight_fn,
        )
        path, explored = DFSSearch().execute(context)
        self.assertTrue(len(path) >= 2)
        self.assertEqual(path[0], 1)
        self.assertEqual(path[-1], 4)
        self.assertTrue(explored > 0)

    def test_bfs_search(self):
        context = SearchInput(
            graph=self.graph,
            start_node=1,
            end_node=4,
            weight_fn=self.weight_fn,
        )
        path, explored = BFSSearch().execute(context)
        self.assertTrue(len(path) >= 2)
        self.assertEqual(path[0], 1)
        self.assertEqual(path[-1], 4)
        self.assertTrue(explored > 0)

    def test_no_path_raises_exception(self):
        self.graph.add_node(5, x=0.0, y=4.0)
        context = SearchInput(
            graph=self.graph,
            start_node=1,
            end_node=5,
            weight_fn=self.weight_fn,
        )
        for searcher in [
            AStarSearch(),
            DijkstraSearch(),
            GBFSSearch(),
            DFSSearch(),
            BFSSearch(),
        ]:
            with self.assertRaises(nx.NetworkXNoPath):
                searcher.execute(context)


class SnapshotIsolationTests(unittest.TestCase):
    def test_algo_result_unpacking_and_properties(self):
        result = AlgoResult(
            path=[1, 2, 3],
            explored_count=5,
            planned_cost=150.5,
            planning_time=100.0,
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], [1, 2, 3])
        self.assertEqual(result[1], 5)
        path, explored = result
        self.assertEqual(path, [1, 2, 3])
        self.assertEqual(explored, 5)
        self.assertEqual(result.planned_cost, 150.5)
        self.assertEqual(result.planning_time, 100.0)

    def test_execution_trace_properties(self):
        trace = ExecutionTrace(
            gps_coords=[(21.0, 105.0), (21.1, 105.1)],
            energy_consumed=12.5,
            travel_time=300.0,
        )
        self.assertEqual(trace.gps_coords, [(21.0, 105.0), (21.1, 105.1)])
        self.assertEqual(trace.energy_consumed, 12.5)
        self.assertEqual(trace.travel_time, 300.0)

    def test_graph_snapshot_immutability(self):
        import threading

        g = nx.MultiDiGraph()
        g.add_node(1, x=105.0, y=21.0)
        g.add_node(2, x=105.1, y=21.1)
        g.add_edge(1, 2, length=100.0)

        # Mocking environment state
        state = {
            "graph_lock": threading.Lock(),
            "obstacles_lock": threading.Lock(),
            "dynamic_traffic_lock": threading.Lock(),
            "road_graph": g,
            "rain_zones": [],
            "obstacles": [],
            "traffic_routes": [],
            "dynamic_traffic_routes": [],
            "rush_hours": [],
            "sim_now": 0.0,
        }

        snapshot = SnapFactory.create_snapshot(state, t=10.0)
        self.assertEqual(snapshot.planning_time, 10.0)
        self.assertIn(1, snapshot)
        self.assertIn(2, snapshot)

        # Immutability check - structural changes should raise an error
        with self.assertRaises(Exception):
            snapshot.add_node(3)
        with self.assertRaises(Exception):
            snapshot.remove_node(1)

    def test_snap_factory_locking_and_isolation(self):
        import threading

        g = nx.MultiDiGraph()
        g.add_node(1, x=105.0, y=21.0)
        g.add_node(2, x=105.1, y=21.1)
        g.add_edge(1, 2, length=100.0)

        state = {
            "graph_lock": threading.Lock(),
            "obstacles_lock": threading.Lock(),
            "dynamic_traffic_lock": threading.Lock(),
            "road_graph": g,
            "rain_zones": [],
            "obstacles": [{"center": (21.0, 105.0), "radius": 50.0, "severity": 2.0}],
            "traffic_routes": [],
            "dynamic_traffic_routes": [],
            "rush_hours": [],
            "sim_now": 0.0,
        }

        # Create snapshot at t=0
        snapshot1 = SnapFactory.create_snapshot(state, t=0.0)

        # Mutate live state
        with state["obstacles_lock"]:
            state["obstacles"].append(
                {"center": (21.1, 105.1), "radius": 100.0, "severity": 5.0}
            )

        # Verify that snapshot1 remains isolated (does not contain the new obstacle)
        self.assertEqual(len(snapshot1.snap_state["obstacles"]), 1)

    def test_algo_result_computation_time(self):
        # We can use a standard graph search setup
        g = nx.MultiDiGraph()
        g.add_node(1, x=105.000, y=21.000)
        g.add_node(2, x=105.000, y=21.001)
        g.add_edge(1, 2, length=100.0)

        def weight_fn(u, v, d):
            return d.get("length", 1.0)

        context = SearchInput(
            graph=g,
            start_node=1,
            end_node=2,
            weight_fn=weight_fn,
            goal_lat=21.001,
            goal_lon=105.000,
        )
        for searcher in [
            AStarSearch(),
            DijkstraSearch(),
            GBFSSearch(),
            DFSSearch(),
            BFSSearch(),
        ]:
            res = searcher.execute(context)
            self.assertTrue(res.computation_time >= 0.0)

    def test_robot_agent_execution_trace(self):
        import simpy
        import threading
        from delivery_robots.core.simulation.robot_agent import RobotAgent
        from delivery_robots.algorithms.base import ExecutionTrace

        env = simpy.Environment()
        g = nx.MultiDiGraph()
        g.add_node(1, x=105.000, y=21.000)
        g.add_node(2, x=105.000, y=21.001)
        g.add_edge(1, 2, length=60.0)

        state = {
            "road_graph": g,
            "history_lock": threading.Lock(),
            "delivery_history": [],
            "traffic_routes": [],
            "dynamic_traffic_routes": [],
            "dynamic_traffic_lock": threading.Lock(),
            "rain_zones": [],
            "obstacles": [],
            "obstacles_lock": threading.Lock(),
            "rush_hours": [],
        }

        agent = RobotAgent(
            env=env,
            robot_id=0,
            name="TestRobot",
            color="red",
            start_lat=21.000,
            start_lon=105.000,
            app_state=state,
            on_state_change=None,
        )

        task = {
            "pickup_path": [1, 2],
            "dropoff_path": [2, 1],
            "pickup": {"lat": 21.001, "lon": 105.000},
            "dropoff": {"lat": 21.000, "lon": 105.000},
        }

        # Run env slightly to allow the agent process to initialize and wait
        env.run(until=1)

        # Assign task and run to completion
        agent.assign_task(task)
        env.run(until=1000)

        self.assertIn("execution_trace", task)
        trace = task["execution_trace"]
        self.assertIsInstance(trace, ExecutionTrace)
        self.assertTrue(len(trace.gps_coords) >= 4)
        self.assertTrue(trace.energy_consumed > 0.0)
        self.assertTrue(trace.travel_time > 0.0)

    def test_robot_agent_path_feasibility(self):
        import simpy
        import threading
        from delivery_robots.core.simulation.robot_agent import RobotAgent

        env = simpy.Environment()
        g = nx.MultiDiGraph()
        g.add_node(1, x=105.000, y=21.000)
        g.add_node(2, x=105.000, y=21.001)
        # 1 -> 2 length is 120.0 meters.
        # Speed: 2 m/s. Battery drain rate: 1/60 per second.
        # Cost = (120.0 / 2) * (1/60) = 60 * 1/60 = 1.0% battery.
        g.add_edge(1, 2, length=120.0)

        state = {
            "road_graph": g,
            "history_lock": threading.Lock(),
            "delivery_history": [],
            "traffic_routes": [],
            "dynamic_traffic_routes": [],
            "dynamic_traffic_lock": threading.Lock(),
            "rain_zones": [],
            "obstacles": [],
            "obstacles_lock": threading.Lock(),
            "rush_hours": [],
        }

        agent = RobotAgent(
            env=env,
            robot_id=0,
            name="TestRobot",
            color="red",
            start_lat=21.000,
            start_lon=105.000,
            app_state=state,
            on_state_change=None,
        )

        # Base battery is 100.0
        # Check path [1, 2] which costs 1.0 battery
        self.assertTrue(agent.is_path_feasible([1, 2]))

        # Set battery to 0.5 (insufficient)
        agent.battery = 0.5
        self.assertFalse(agent.is_path_feasible([1, 2]))

        # Set battery to 1.0 (exactly sufficient)
        agent.battery = 1.0
        self.assertTrue(agent.is_path_feasible([1, 2]))

    def test_robot_agent_charging_decision_policy(self):
        import simpy
        import threading
        from delivery_robots.core.simulation.robot_agent import RobotAgent

        env = simpy.Environment()
        g = nx.MultiDiGraph()
        g.add_node(1, x=105.000, y=21.000)
        g.add_node(2, x=105.000, y=21.001)
        g.add_node(3, x=105.000, y=21.002)
        # 1 -> 2 -> 3
        g.add_edge(1, 2, length=120.0)
        g.add_edge(2, 3, length=120.0)

        # Set up app state
        state = {
            "road_graph": g,
            "history_lock": threading.Lock(),
            "delivery_history": [],
            "traffic_routes": [],
            "dynamic_traffic_routes": [],
            "dynamic_traffic_lock": threading.Lock(),
            "rain_zones": [],
            "obstacles": [],
            "obstacles_lock": threading.Lock(),
            "rush_hours": [],
            "charging_stations": [
                {"lat": 21.002, "lon": 105.000, "name": "Hub C", "spots": 2}
            ],
            "hub_resources": {},
            "order_queue": [],
        }

        # Setup Hub C resource
        state["hub_resources"]["Hub C"] = simpy.Resource(env, capacity=2)

        agent = RobotAgent(
            env=env,
            robot_id=0,
            name="TestRobot",
            color="red",
            start_lat=21.000,
            start_lon=105.000,
            app_state=state,
            on_state_change=None,
        )

        # 1. Test select_optimal_hub
        hub = agent.select_optimal_hub()
        self.assertIsNotNone(hub)
        self.assertEqual(hub["name"], "Hub C")

        # 2. Test get_safety_threshold
        # With no current task, safety threshold should be B_to_nearest_hub + margin
        # Distance from agent at node 1 (21.000, 105.000) to Hub C (21.002, 105.000)
        # Node path is 1 -> 2 -> 3 (Hub C is near node 3).
        # Cost of 1 -> 2 -> 3 is: (240 / 2) * (1/60) = 2.0%
        # Margin is 10.0%. Total safety threshold: 2.0 + 10.0 = 12.0%
        threshold = agent.get_safety_threshold()
        self.assertAlmostEqual(threshold, 12.0)


class ChargingAndHubSelectionTests(unittest.TestCase):
    def test_simpy_resource_mapping(self):
        import simpy
        from delivery_robots.core.simulation.simulator import SimulatorManager
        from unittest.mock import MagicMock

        app_state = {
            "road_graph": None,
            "charging_stations": [
                {"lat": 21.0285, "lon": 105.8542, "name": "Hoan Kiem Hub", "spots": 3},
                {"lat": 21.0355, "lon": 105.8516, "name": "Dong Xuan", "spots": 2},
            ],
        }

        sim_manager = SimulatorManager(
            socketio=MagicMock(),
            app_state=app_state,
            nearest_node_id=MagicMock(),
            run_weighted_route_search=MagicMock(),
            edge_weight_with_traffic=MagicMock(),
            build_route_geometry=MagicMock(),
        )
        sim_manager.initialize_robots()

        resources = app_state["hub_resources"]
        # Hoan Kiem Hub has capacity 3 (odd) -> PriorityResource
        self.assertIsInstance(resources["Hoan Kiem Hub"], simpy.PriorityResource)
        self.assertEqual(resources["Hoan Kiem Hub"].capacity, 3)

        # Dong Xuan has capacity 2 (even) -> Resource
        self.assertIsInstance(resources["Dong Xuan"], simpy.Resource)
        self.assertNotIsInstance(resources["Dong Xuan"], simpy.PriorityResource)
        self.assertEqual(resources["Dong Xuan"].capacity, 2)

    def test_optimal_hub_selection_wait_time(self):
        import simpy
        import threading
        from delivery_robots.core.simulation.robot_agent import RobotAgent

        env = simpy.Environment()
        g = nx.MultiDiGraph()
        g.add_node(1, x=105.000, y=21.000)
        g.add_node(2, x=105.000, y=21.001)
        g.add_edge(1, 2, length=60.0)

        state = {
            "road_graph": g,
            "history_lock": threading.Lock(),
            "delivery_history": [],
            "traffic_routes": [],
            "dynamic_traffic_routes": [],
            "dynamic_traffic_lock": threading.Lock(),
            "rain_zones": [],
            "obstacles": [],
            "obstacles_lock": threading.Lock(),
            "rush_hours": [],
            "charging_stations": [
                {"lat": 21.001, "lon": 105.000, "name": "Hub A", "spots": 1},
                {"lat": 21.001, "lon": 105.000, "name": "Hub B", "spots": 1},
            ],
            "hub_resources": {
                "Hub A": simpy.Resource(env, capacity=1),
                "Hub B": simpy.Resource(env, capacity=1),
            },
        }

        agent = RobotAgent(
            env=env,
            robot_id=0,
            name="TestRobot",
            color="red",
            start_lat=21.000,
            start_lon=105.000,
            app_state=state,
            on_state_change=None,
        )

        # Let the background run() loop go to sleep first
        env.run(until=1)

        state["hub_resources"]["Hub A"]
        res_b = state["hub_resources"]["Hub B"]

        # Simulate active charging on Hub B
        req1 = res_b.request()

        def get_req():
            yield req1

        env.run(env.process(get_req()))

        # Simulate a robot waiting in queue on Hub B
        res_b.request()

        self.assertEqual(res_b.count, 1)
        self.assertEqual(len(res_b.queue), 1)

        opt_hub = agent.select_optimal_hub()
        self.assertEqual(opt_hub["name"], "Hub A")

    def test_robot_charging_formula(self):
        import simpy
        import threading
        from delivery_robots.core.simulation.robot_agent import RobotAgent
        from delivery_robots.config import CHARGING_RATE_PERCENT_PER_MINUTE

        env = simpy.Environment()
        g = nx.MultiDiGraph()
        g.add_node(1, x=105.000, y=21.000)

        state = {
            "road_graph": g,
            "history_lock": threading.Lock(),
            "delivery_history": [],
            "traffic_routes": [],
            "dynamic_traffic_routes": [],
            "dynamic_traffic_lock": threading.Lock(),
            "rain_zones": [],
            "obstacles": [],
            "obstacles_lock": threading.Lock(),
            "rush_hours": [],
            "charging_stations": [
                {"lat": 21.000, "lon": 105.000, "name": "Hub C", "spots": 2}
            ],
            "hub_resources": {
                "Hub C": simpy.Resource(env, capacity=2),
            },
        }

        agent = RobotAgent(
            env=env,
            robot_id=0,
            name="TestRobot",
            color="red",
            start_lat=21.000,
            start_lon=105.000,
            app_state=state,
            on_state_change=None,
        )

        # Let background run() loop go to sleep first
        env.run(until=1)

        agent.battery = 30.0
        station = state["charging_stations"][0]
        env.process(agent.charge(station))

        # Let the simulation run for 61 seconds of charging (since charging starts at t=1, we run until t=62)
        env.run(until=62)

        self.assertAlmostEqual(
            agent.battery, 30.0 + CHARGING_RATE_PERCENT_PER_MINUTE, places=1
        )

    def test_robot_priority_charging(self):
        import simpy
        import threading
        from delivery_robots.core.simulation.robot_agent import RobotAgent

        env = simpy.Environment()
        g = nx.MultiDiGraph()
        g.add_node(1, x=105.000, y=21.000)

        state = {
            "road_graph": g,
            "history_lock": threading.Lock(),
            "delivery_history": [],
            "traffic_routes": [],
            "dynamic_traffic_routes": [],
            "dynamic_traffic_lock": threading.Lock(),
            "rain_zones": [],
            "obstacles": [],
            "obstacles_lock": threading.Lock(),
            "rush_hours": [],
            "charging_stations": [
                {"lat": 21.000, "lon": 105.000, "name": "Priority Hub", "spots": 1}
            ],
            "hub_resources": {
                "Priority Hub": simpy.PriorityResource(env, capacity=1),
            },
        }

        r1 = RobotAgent(
            env=env,
            robot_id=1,
            name="R1",
            color="red",
            start_lat=21.000,
            start_lon=105.000,
            app_state=state,
            on_state_change=None,
        )
        r2 = RobotAgent(
            env=env,
            robot_id=2,
            name="R2",
            color="green",
            start_lat=21.000,
            start_lon=105.000,
            app_state=state,
            on_state_change=None,
        )
        r3 = RobotAgent(
            env=env,
            robot_id=3,
            name="R3",
            color="blue",
            start_lat=21.000,
            start_lon=105.000,
            app_state=state,
            on_state_change=None,
        )

        # Let their background run() processes go to sleep first
        env.run(until=1)

        r1.battery = 50.0
        r2.battery = 80.0
        r3.battery = 10.0

        station = state["charging_stations"][0]

        env.process(r1.charge(station))
        env.process(r2.charge(station))
        env.process(r3.charge(station))

        # We run for 1 step to process the requests
        env.run(until=2)

        resource = state["hub_resources"]["Priority Hub"]
        self.assertEqual(len(resource.users), 1)
        self.assertEqual(len(resource.queue), 2)
        self.assertEqual(resource.queue[0].priority, 10)
        self.assertEqual(resource.queue[1].priority, 80)

    def test_robot_fsm_successful_transitions(self):
        import simpy
        import threading
        from delivery_robots.core.simulation.robot_agent import RobotAgent
        from delivery_robots.config import (
            ROBOT_STATUS_IDLE,
            ROBOT_STATUS_MOVING_TO_PICKUP,
            ROBOT_STATUS_MOVING_TO_DROPOFF,
            ROBOT_STATUS_MOVING_TO_CHARGE,
            ROBOT_STATUS_CHARGING,
            ORDER_STATUS_ASSIGNED,
            ORDER_STATUS_IN_TRANSIT,
            ORDER_STATUS_DELIVERED,
        )

        env = simpy.Environment()
        g = nx.MultiDiGraph()
        g.add_node(1, x=105.000, y=21.000)
        g.add_node(2, x=105.000, y=21.001)
        g.add_edge(1, 2, length=60.0)

        state = {
            "road_graph": g,
            "history_lock": threading.Lock(),
            "delivery_history": [],
            "traffic_routes": [],
            "dynamic_traffic_routes": [],
            "dynamic_traffic_lock": threading.Lock(),
            "rain_zones": [],
            "obstacles": [],
            "obstacles_lock": threading.Lock(),
            "rush_hours": [],
            "charging_stations": [
                {"lat": 21.000, "lon": 105.000, "name": "Hub A", "spots": 1}
            ],
            "hub_resources": {
                "Hub A": simpy.Resource(env, capacity=1),
            },
            "order_queue": [],
        }

        task = {
            "id": "T1",
            "pickup_path": [1, 2],
            "dropoff_path": [2, 1],
            "pickup": {"lat": 21.001, "lon": 105.000},
            "dropoff": {"lat": 21.000, "lon": 105.000},
        }

        history = []

        def on_change(agent_state):
            current_status = agent_state.get("status")
            task_status = task.get("status")
            history.append((current_status, task_status))

        agent = RobotAgent(
            env=env,
            robot_id=0,
            name="TestRobot",
            color="red",
            start_lat=21.000,
            start_lon=105.000,
            app_state=state,
            on_state_change=on_change,
        )

        # Run env slightly to allow the agent process to initialize and wait
        env.run(until=1)
        self.assertEqual(agent.status, ROBOT_STATUS_IDLE)

        # Assign task and run to completion
        agent.assign_task(task)
        env.run(until=1000)

        # Let's inspect the history of state changes
        # It should contain (ROBOT_STATUS_MOVING_TO_PICKUP, ORDER_STATUS_ASSIGNED)
        # and then (ROBOT_STATUS_MOVING_TO_DROPOFF, ORDER_STATUS_IN_TRANSIT)
        # and then (ROBOT_STATUS_IDLE, ORDER_STATUS_DELIVERED)
        self.assertTrue(
            any(
                status == ROBOT_STATUS_MOVING_TO_PICKUP
                and t_status == ORDER_STATUS_ASSIGNED
                for status, t_status in history
            )
        )
        self.assertTrue(
            any(
                status == ROBOT_STATUS_MOVING_TO_DROPOFF
                and t_status == ORDER_STATUS_IN_TRANSIT
                for status, t_status in history
            )
        )
        self.assertEqual(agent.status, ROBOT_STATUS_IDLE)
        self.assertEqual(task.get("status"), ORDER_STATUS_DELIVERED)

        # Now test the case where battery is low at the end of delivery
        task2 = {
            "id": "T2",
            "pickup_path": [1, 2],
            "dropoff_path": [2, 1],
            "pickup": {"lat": 21.001, "lon": 105.000},
            "dropoff": {"lat": 21.000, "lon": 105.000},
        }

        agent.battery = 50.0  # above low battery threshold (30%)
        history.clear()

        # Reset task status for on_change capture
        def on_change2(agent_state):
            current_status = agent_state.get("status")
            task_status = task2.get("status")
            history.append((current_status, task_status))
            # Set battery to 20% (low) during dropoff leg to trigger low-battery charging after delivery
            if current_status == ROBOT_STATUS_MOVING_TO_DROPOFF:
                agent.battery = 20.0

        agent.on_state_change = on_change2
        agent.assign_task(task2)
        env.run(until=3000)

        # The robot should have completed delivery and then transitioned to ROBOT_STATUS_MOVING_TO_CHARGE
        # and ultimately to CHARGING, and then IDLE after battery >= 100%
        self.assertEqual(task2.get("status"), ORDER_STATUS_DELIVERED)
        self.assertTrue(
            any(status == ROBOT_STATUS_MOVING_TO_CHARGE for status, _ in history)
        )
        self.assertTrue(any(status == ROBOT_STATUS_CHARGING for status, _ in history))
        self.assertEqual(agent.status, ROBOT_STATUS_IDLE)
        self.assertEqual(agent.battery, 100.0)

    def test_robot_fsm_safety_threshold_interrupt(self):
        import simpy
        import threading
        from delivery_robots.core.simulation.robot_agent import RobotAgent
        from delivery_robots.config import (
            ROBOT_STATUS_MOVING_TO_CHARGE,
            ORDER_STATUS_PENDING,
            ROBOT_STATUS_MOVING_TO_PICKUP,
        )

        env = simpy.Environment()
        g = nx.MultiDiGraph()
        g.add_node(1, x=105.000, y=21.000)
        g.add_node(2, x=105.000, y=21.001)
        g.add_edge(1, 2, length=60.0)

        state = {
            "road_graph": g,
            "history_lock": threading.Lock(),
            "delivery_history": [],
            "traffic_routes": [],
            "dynamic_traffic_routes": [],
            "dynamic_traffic_lock": threading.Lock(),
            "rain_zones": [],
            "obstacles": [],
            "obstacles_lock": threading.Lock(),
            "rush_hours": [],
            "charging_stations": [
                {"lat": 21.000, "lon": 105.000, "name": "Hub A", "spots": 1}
            ],
            "hub_resources": {
                "Hub A": simpy.Resource(env, capacity=1),
            },
            "order_queue": [],
        }

        task = {
            "id": "T1",
            "pickup_path": [1, 2],
            "dropoff_path": [2, 1],
            "pickup": {"lat": 21.001, "lon": 105.000},
            "dropoff": {"lat": 21.000, "lon": 105.000},
        }

        agent = RobotAgent(
            env=env,
            robot_id=0,
            name="TestRobot",
            color="red",
            start_lat=21.000,
            start_lon=105.000,
            app_state=state,
            on_state_change=None,
        )

        # Run env slightly to allow the agent process to initialize and wait
        env.run(until=1)

        history = []

        def on_change(agent_state):
            current_status = agent_state.get("status")
            task_status = task.get("status")
            history.append((current_status, task_status))
            # Set battery to 5% (below safety threshold) during pickup movement to trigger interrupt
            if current_status == ROBOT_STATUS_MOVING_TO_PICKUP:
                agent.battery = 5.0

        agent.on_state_change = on_change

        agent.assign_task(task)
        env.run(until=2000)

        # Task should have been returned to the order queue in PENDING status
        self.assertEqual(len(state["order_queue"]), 1)
        self.assertEqual(state["order_queue"][0]["id"], "T1")
        self.assertEqual(state["order_queue"][0]["status"], ORDER_STATUS_PENDING)

        # Agent should have transitioned to charging, charged up to 100% and then become IDLE
        self.assertTrue(
            any(status == ROBOT_STATUS_MOVING_TO_CHARGE for status, _ in history)
        )
        self.assertEqual(agent.status, "idle")
        self.assertEqual(agent.battery, 100.0)

    def test_plan_execute_gap_calculation(self):
        import simpy
        import threading
        from delivery_robots.core.simulation.robot_agent import RobotAgent

        env = simpy.Environment()
        g = nx.MultiDiGraph()
        g.add_node(1, x=105.000, y=21.000)
        g.add_node(2, x=105.000, y=21.001)
        g.add_edge(1, 2, length=120.0)
        g.add_edge(2, 1, length=120.0)

        state = {
            "road_graph": g,
            "graph_lock": threading.Lock(),
            "history_lock": threading.Lock(),
            "delivery_history": [],
            "traffic_routes": [],
            "dynamic_traffic_routes": [],
            "dynamic_traffic_lock": threading.Lock(),
            "rain_zones": [],
            "obstacles": [],
            "obstacles_lock": threading.Lock(),
            "rush_hours": [],
        }

        agent = RobotAgent(
            env=env,
            robot_id=0,
            name="TestRobot",
            color="red",
            start_lat=21.000,
            start_lon=105.000,
            app_state=state,
            on_state_change=None,
        )

        task = {
            "id": "T1",
            "pickup_path": [1, 2],
            "dropoff_path": [2, 1],
            "pickup": {"lat": 21.001, "lon": 105.000},
            "dropoff": {"lat": 21.000, "lon": 105.000},
            "pickup_planned_cost": 120.0,
            "dropoff_planned_cost": 120.0,
            "pickup_edge_planned_costs": [120.0],
            "dropoff_edge_planned_costs": [120.0],
        }

        env.run(until=1)
        agent.assign_task(task)
        env.run(until=1000)

        self.assertIn("planned_cost", task)
        self.assertIn("actual_cost", task)
        self.assertIn("plan_execute_gap", task)
        self.assertEqual(task["planned_cost"], 240.0)
        self.assertEqual(task["actual_cost"], 240.0)
        self.assertEqual(task["plan_execute_gap"], 0.0)

    def test_replanning_on_traffic_spike(self):
        import simpy
        import threading
        from delivery_robots.core.simulation.robot_agent import RobotAgent

        env = simpy.Environment()
        g = nx.MultiDiGraph()
        g.add_node(1, x=105.000, y=21.000)
        g.add_node(2, x=105.000, y=21.001)
        g.add_node(3, x=105.001, y=21.000)
        g.add_node(4, x=105.001, y=21.001)

        g.add_edge(1, 2, length=60.0)
        g.add_edge(2, 4, length=60.0)
        g.add_edge(1, 3, length=70.0)
        g.add_edge(3, 4, length=70.0)
        g.add_edge(4, 1, length=60.0)

        state = {
            "road_graph": g,
            "graph_lock": threading.Lock(),
            "history_lock": threading.Lock(),
            "delivery_history": [],
            "traffic_routes": [],
            "dynamic_traffic_routes": [],
            "dynamic_traffic_lock": threading.Lock(),
            "rain_zones": [],
            "obstacles": [],
            "obstacles_lock": threading.Lock(),
            "rush_hours": [],
        }

        agent = RobotAgent(
            env=env,
            robot_id=0,
            name="TestRobot",
            color="red",
            start_lat=21.000,
            start_lon=105.000,
            app_state=state,
            on_state_change=None,
        )

        task = {
            "id": "T2",
            "pickup_path": [1, 2, 4],
            "dropoff_path": [4, 1],
            "pickup": {"lat": 21.001, "lon": 105.001},
            "dropoff": {"lat": 21.000, "lon": 105.000},
            "pickup_planned_cost": 120.0,
            "dropoff_planned_cost": 60.0,
            "pickup_edge_planned_costs": [60.0, 60.0],
            "dropoff_edge_planned_costs": [60.0],
        }

        env.run(until=1)

        # Introduce obstacle to trigger replanning (small radius covers only 2 -> 4)
        state["obstacles"].append(
            {
                "name": "Obs1",
                "center": (21.001, 105.0005),
                "radius": 30.0,
                "severity": 100.0,
                "type": "roadblock",
            }
        )

        agent.assign_task(task)
        env.run(until=1000)

        self.assertEqual(task["pickup_path"], [1, 3, 4])

    def test_robot_charging_state_fields(self):
        import simpy
        import threading
        from delivery_robots.core.simulation.robot_agent import RobotAgent
        from delivery_robots.config import (
            ROBOT_STATUS_CHARGING,
            ROBOT_STATUS_MOVING_TO_CHARGE,
        )

        env = simpy.Environment()
        g = nx.MultiDiGraph()
        g.add_node(1, x=105.000, y=21.000)

        state = {
            "road_graph": g,
            "history_lock": threading.Lock(),
            "delivery_history": [],
            "traffic_routes": [],
            "dynamic_traffic_routes": [],
            "dynamic_traffic_lock": threading.Lock(),
            "rain_zones": [],
            "obstacles": [],
            "obstacles_lock": threading.Lock(),
            "rush_hours": [],
            "charging_stations": [
                {"lat": 21.000, "lon": 105.000, "name": "Hub X", "spots": 1}
            ],
            "hub_resources": {
                "Hub X": simpy.Resource(env, capacity=1),
            },
        }

        agent = RobotAgent(
            env=env,
            robot_id=0,
            name="TestRobot",
            color="red",
            start_lat=21.000,
            start_lon=105.000,
            app_state=state,
            on_state_change=None,
        )

        env.run(until=1)

        # Verify initial fields
        agent_state = agent.get_state()
        self.assertIn("charging_station", agent_state)
        self.assertIn("remaining_charge_time", agent_state)
        self.assertIsNone(agent_state["charging_station"])
        self.assertEqual(agent_state["remaining_charge_time"], 0.0)

        # Simulate moving to charge
        station = state["charging_stations"][0]
        agent.status = ROBOT_STATUS_MOVING_TO_CHARGE
        agent.charging_station_name = station["name"]

        agent_state = agent.get_state()
        self.assertEqual(agent_state["status"], ROBOT_STATUS_MOVING_TO_CHARGE)
        self.assertEqual(agent_state["charging_station"], "Hub X")

        # Start charging
        agent.battery = 50.0
        env.process(agent.charge(station))

        # Let it step slightly (t=5)
        env.run(until=5)

        agent_state = agent.get_state()
        self.assertEqual(agent_state["status"], ROBOT_STATUS_CHARGING)
        self.assertEqual(agent_state["charging_station"], "Hub X")
        # Remaining time should be calculated and > 0 since battery < 100
        self.assertGreater(agent_state["remaining_charge_time"], 0.0)


class EventBusAndEnvironmentTests(unittest.TestCase):
    def test_event_bus_environment_mutations(self):
        import threading
        from delivery_robots.core.event_bus import EventBus, Event, EventType
        from delivery_robots.core.environment import register_environment_subscribers

        state = {
            "rain_zones": [],
            "dynamic_traffic_routes": [],
            "dynamic_traffic_lock": threading.Lock(),
            "obstacles": [],
            "obstacles_lock": threading.Lock(),
        }

        bus = EventBus()
        register_environment_subscribers(bus, state)

        # 1. Test Rain
        bus.publish(
            Event(EventType.RAIN_ADDED, {"lat": 21.03, "lon": 105.85, "radius": 150})
        )
        self.assertEqual(len(state["rain_zones"]), 1)
        self.assertEqual(state["rain_zones"][0]["center"], (21.03, 105.85))
        self.assertEqual(state["rain_zones"][0]["radius"], 150)

        bus.publish(Event(EventType.RAIN_CLEARED))
        self.assertEqual(len(state["rain_zones"]), 0)

        # 2. Test Traffic
        path = [{"lat": 21.0, "lon": 105.0}, {"lat": 21.1, "lon": 105.1}]
        bus.publish(
            Event(
                EventType.TRAFFIC_ADDED,
                {"name": "Test Traffic", "severity": 0.8, "path": path},
            )
        )
        self.assertEqual(len(state["dynamic_traffic_routes"]), 1)
        self.assertEqual(state["dynamic_traffic_routes"][0]["name"], "Test Traffic")
        self.assertEqual(state["dynamic_traffic_routes"][0]["severity"], 0.8)

        bus.publish(Event(EventType.TRAFFIC_CLEARED))
        self.assertEqual(len(state["dynamic_traffic_routes"]), 0)

        # 3. Test Obstacle
        bus.publish(
            Event(
                EventType.OBSTACLE_ADDED,
                {"lat": 21.01, "lon": 105.82, "radius": 50, "severity": 10},
            )
        )
        self.assertEqual(len(state["obstacles"]), 1)
        self.assertEqual(state["obstacles"][0]["center"], (21.01, 105.82))
        self.assertEqual(state["obstacles"][0]["severity"], 10)

        bus.publish(Event(EventType.OBSTACLE_CLEARED))
        self.assertEqual(len(state["obstacles"]), 0)

    def test_scenario_config_serialization(self):
        import os
        from delivery_robots.core.event_bus import Event, EventType, ScenarioConfig

        # Create temporary file path inside workspace cache directory
        scratch_dir = "/home/lan/projects/AI-Intro/cache"
        os.makedirs(scratch_dir, exist_ok=True)
        filepath = os.path.join(scratch_dir, "test_scenario.json")

        events = [
            Event(
                EventType.RAIN_ADDED,
                {"lat": 21.0, "lon": 105.0, "radius": 100},
                sim_time=10.0,
            ),
            Event(
                EventType.OBSTACLE_ADDED,
                {"lat": 21.1, "lon": 105.1, "radius": 50, "severity": 5.0},
                sim_time=20.0,
            ),
        ]
        config = ScenarioConfig(events, seed=42, params={"dispatch_model": "hungarian"})
        config.save_to_file(filepath)

        loaded_config = ScenarioConfig()
        loaded_config.load_from_file(filepath)

        self.assertEqual(loaded_config.seed, 42)
        self.assertEqual(loaded_config.params.get("dispatch_model"), "hungarian")
        self.assertEqual(len(loaded_config.events), 2)
        self.assertEqual(loaded_config.events[0].event_type, EventType.RAIN_ADDED)
        self.assertEqual(loaded_config.events[0].sim_time, 10.0)
        self.assertEqual(loaded_config.events[0].data["lat"], 21.0)
        self.assertEqual(loaded_config.events[1].event_type, EventType.OBSTACLE_ADDED)
        self.assertEqual(loaded_config.events[1].sim_time, 20.0)

        # Test backward compatibility (older format where JSON is a raw list of events)
        import json

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump([e.to_dict() for e in events], f, indent=2)

        loaded_legacy = ScenarioConfig()
        loaded_legacy.load_from_file(filepath)
        self.assertIsNone(loaded_legacy.seed)
        self.assertEqual(loaded_legacy.params, {})
        self.assertEqual(len(loaded_legacy.events), 2)

        # Clean up
        if os.path.exists(filepath):
            os.remove(filepath)

    def test_scenario_injection_simulation(self):
        import threading
        from unittest.mock import MagicMock
        from delivery_robots.core.event_bus import (
            EventBus,
            Event,
            EventType,
            ScenarioConfig,
        )
        from delivery_robots.core.environment import register_environment_subscribers
        from delivery_robots.core.simulation.simulator import SimulatorManager

        bus = EventBus()
        state = {
            "road_graph": nx.MultiDiGraph(),
            "history_lock": threading.Lock(),
            "delivery_history": [],
            "traffic_routes": [],
            "dynamic_traffic_routes": [],
            "dynamic_traffic_lock": threading.Lock(),
            "rain_zones": [],
            "obstacles": [],
            "obstacles_lock": threading.Lock(),
            "rush_hours": [],
            "charging_stations": [],
            "hub_resources": {},
            "order_queue": [],
            "event_bus": bus,
        }

        register_environment_subscribers(bus, state)

        sim_manager = SimulatorManager(
            socketio=MagicMock(),
            app_state=state,
            nearest_node_id=MagicMock(),
            run_weighted_route_search=MagicMock(),
            edge_weight_with_traffic=MagicMock(),
            build_route_geometry=MagicMock(),
        )

        events = [
            Event(
                EventType.RAIN_ADDED,
                {"lat": 21.02, "lon": 105.84, "radius": 120},
                sim_time=15.0,
            ),
        ]
        scenario = ScenarioConfig(events)
        sim_manager.scenario_config = scenario

        # Bind processes
        sim_manager.env.process(sim_manager._scenario_injector_process())

        # At t=10, rain zones should be empty
        sim_manager.env.run(until=10)
        self.assertEqual(len(state["rain_zones"]), 0)

        # At t=20, rain zone should be populated
        sim_manager.env.run(until=20)
        self.assertEqual(len(state["rain_zones"]), 1)
        self.assertEqual(state["rain_zones"][0]["center"], (21.02, 105.84))

    def test_scenario_config_params_and_seeding(self):
        import threading
        from unittest.mock import MagicMock
        from delivery_robots.core.event_bus import (
            EventBus,
            ScenarioConfig,
        )
        from delivery_robots.core.simulation.simulator import SimulatorManager

        bus = EventBus()
        state = {
            "road_graph": nx.MultiDiGraph(),
            "history_lock": threading.Lock(),
            "delivery_history": [],
            "traffic_routes": [],
            "dynamic_traffic_routes": [],
            "dynamic_traffic_lock": threading.Lock(),
            "rain_zones": [],
            "obstacles": [],
            "obstacles_lock": threading.Lock(),
            "rush_hours": [],
            "charging_stations": [],
            "hub_resources": {},
            "order_queue": [],
            "event_bus": bus,
            "dispatch_model": "nearest_idle",
            "simulation_speed": 60,
        }

        sim_manager = SimulatorManager(
            socketio=MagicMock(),
            app_state=state,
            nearest_node_id=MagicMock(),
            run_weighted_route_search=MagicMock(),
            edge_weight_with_traffic=MagicMock(),
            build_route_geometry=MagicMock(),
        )

        scenario = ScenarioConfig(
            events=[],
            seed=12345,
            params={"dispatch_model": "hungarian", "simulation_speed": 120},
        )
        sim_manager.scenario_config = scenario

        # Call start (mocking background task and loop sleep)
        sim_manager.socketio.start_background_task = MagicMock()
        sim_manager.start()

        # Check that state parameters were overridden
        self.assertEqual(state["dispatch_model"], "hungarian")
        self.assertEqual(state["simulation_speed"], 120)

        # Verify that random was seeded deterministically
        import random

        r1 = random.random()

        # Reset and run again with same seed
        random.seed(12345)
        r2 = random.random()
        self.assertEqual(r1, r2)


class OrderManagerTests(unittest.TestCase):
    def test_order_lifecycle_and_fifo(self):
        import simpy
        from delivery_robots.core.simulation.order_manager import OrderManager
        from delivery_robots.config import (
            ORDER_STATUS_PENDING,
            ORDER_STATUS_ASSIGNED,
            ORDER_STATUS_IN_TRANSIT,
            ORDER_STATUS_DELIVERED,
        )

        env = simpy.Environment()
        state = {"metrics": {"failed_orders": 0, "total_orders": 0}}
        om = OrderManager(env, state)

        t1 = {"id": "ORDER-1", "pickup": "A", "dropoff": "B"}
        t2 = {"id": "ORDER-2", "pickup": "B", "dropoff": "C"}

        om.add_order(t1)
        om.add_order(t2)

        self.assertEqual(len(om.order_queue), 2)
        self.assertEqual(t1["status"], ORDER_STATUS_PENDING)
        self.assertEqual(t2["status"], ORDER_STATUS_PENDING)
        self.assertEqual(t1["created_time"], 0.0)
        self.assertEqual(t2["created_time"], 0.0)

        # FIFO verification
        popped_t1 = om.pop_next_pending()
        self.assertEqual(popped_t1["id"], "ORDER-1")
        self.assertEqual(popped_t1["status"], ORDER_STATUS_ASSIGNED)

        popped_t2 = om.pop_next_pending()
        self.assertEqual(popped_t2["id"], "ORDER-2")
        self.assertEqual(popped_t2["status"], ORDER_STATUS_ASSIGNED)

        # Transition lifecycle
        om.mark_in_transit(popped_t1)
        self.assertEqual(popped_t1["status"], ORDER_STATUS_IN_TRANSIT)

        om.mark_delivered(popped_t1)
        self.assertEqual(popped_t1["status"], ORDER_STATUS_DELIVERED)

        # Requeue verification
        om.requeue_order(popped_t1)
        self.assertEqual(popped_t1["status"], ORDER_STATUS_PENDING)
        self.assertEqual(om.order_queue[0]["id"], "ORDER-1")

    def test_order_expiration_and_failure_metrics(self):
        import simpy
        from unittest.mock import MagicMock
        from delivery_robots.core.simulation.order_manager import OrderManager
        from delivery_robots.config import ORDER_STATUS_EXPIRED, ORDER_EXPIRY_TIMEOUT

        env = simpy.Environment()
        state = {"metrics": {"failed_orders": 0, "total_orders": 0}}
        socket_mock = MagicMock()
        om = OrderManager(env, state, socket_mock)

        t1 = {"id": "ORDER-X", "pickup": "A", "dropoff": "B"}
        om.add_order(t1)

        # Run environment forward by less than expiration timeout (e.g., 100 sim seconds)
        env.run(until=100)
        self.assertEqual(t1["status"], "pending")
        self.assertEqual(len(om.order_queue), 1)

        # Run environment past expiration timeout (e.g., 320 seconds)
        env.run(until=320)
        self.assertEqual(t1["status"], ORDER_STATUS_EXPIRED)
        self.assertEqual(len(om.order_queue), 0)
        self.assertEqual(state["metrics"]["failed_orders"], 1)

        # Verify socketio emit was called
        socket_mock.emit.assert_called_with(
            "system_event",
            {"message": f"Order ORDER-X has expired after {ORDER_EXPIRY_TIMEOUT}s"},
        )


class RoutingOptimalityTests(unittest.TestCase):
    def setUp(self):
        self.graph = nx.MultiDiGraph()
        self.graph.add_node(1, x=105.000, y=21.000)
        self.graph.add_node(2, x=105.000, y=21.001)
        self.graph.add_node(3, x=105.000, y=21.002)
        # 1 -> 2 length 120.0
        # 2 -> 3 length 120.0
        # 1 -> 3 length 1000.0 (suboptimal direct path)
        self.graph.add_edge(1, 2, length=120.0)
        self.graph.add_edge(2, 3, length=120.0)
        self.graph.add_edge(1, 3, length=1000.0)

        def weight_fn(u, v, d):
            return (
                d.get("length", 1.0)
                if "length" in d
                else min(edge.get("length", 1.0) for edge in d.values())
            )

        self.weight_fn = weight_fn

    def test_dijkstra_oracle_ratio(self):
        from delivery_robots.algorithms.search_manager import run_weighted_route_search

        # Test Dijkstra returns optimality_ratio == 1.0
        res_dijkstra = run_weighted_route_search(
            graph=self.graph,
            start_node=1,
            end_node=3,
            goal_lat=21.002,
            goal_lon=105.000,
            weight_fn=self.weight_fn,
            algorithm="dijkstra",
        )
        self.assertEqual(res_dijkstra.optimality_ratio, 1.0)
        self.assertEqual(res_dijkstra.path, [1, 2, 3])
        self.assertEqual(res_dijkstra.planned_cost, 240.0)

    def test_astar_oracle_ratio(self):
        from delivery_robots.algorithms.search_manager import run_weighted_route_search

        # Test A* returns optimality_ratio == 1.0 (since it finds the optimal path)
        res_astar = run_weighted_route_search(
            graph=self.graph,
            start_node=1,
            end_node=3,
            goal_lat=21.002,
            goal_lon=105.000,
            weight_fn=self.weight_fn,
            algorithm="astar",
        )
        self.assertEqual(res_astar.optimality_ratio, 1.0)
        self.assertEqual(res_astar.path, [1, 2, 3])
        self.assertEqual(res_astar.planned_cost, 240.0)

    def test_bfs_dfs_recalculated_cost_and_ratio(self):
        from delivery_robots.algorithms.search_manager import run_weighted_route_search

        # Test BFS
        res_bfs = run_weighted_route_search(
            graph=self.graph,
            start_node=1,
            end_node=3,
            goal_lat=21.002,
            goal_lon=105.000,
            weight_fn=self.weight_fn,
            algorithm="bfs",
        )
        # Its planned_cost should be calculated using weight_fn
        expected_cost = sum(
            self.weight_fn(u, v, self.graph[u][v])
            for u, v in zip(res_bfs.path[:-1], res_bfs.path[1:])
        )
        self.assertEqual(res_bfs.planned_cost, expected_cost)
        self.assertEqual(res_bfs.optimality_ratio, expected_cost / 240.0)

    def test_metrics_optimality_ratio_recording(self):
        from delivery_robots.utils.metrics import (
            create_metrics,
            record_route_metrics,
            build_metrics_payload,
        )

        metrics = create_metrics()
        self.assertIn("avg_optimality_ratio", metrics)
        self.assertEqual(metrics["avg_optimality_ratio"], 1.0)
        self.assertEqual(metrics["suboptimal_rate"], 0.0)

        # Record route metrics
        record_route_metrics(
            metrics,
            calc_time_ms=5.0,
            nodes_explored=10,
            path_length=3,
            memory_bytes=100,
            optimality_ratio=1.0,
        )
        self.assertEqual(metrics["avg_optimality_ratio"], 1.0)
        self.assertEqual(metrics["suboptimal_rate"], 0.0)

        # Record suboptimal path
        record_route_metrics(
            metrics,
            calc_time_ms=6.0,
            nodes_explored=12,
            path_length=4,
            memory_bytes=120,
            optimality_ratio=1.5,
        )
        self.assertEqual(metrics["avg_optimality_ratio"], 1.25)
        self.assertEqual(metrics["suboptimal_rate"], 0.5)

        # Build payload and verify
        payload = build_metrics_payload(
            metrics, self.graph, rain_count=0, traffic_count=0, obstacle_count=0
        )
        self.assertEqual(payload["pathfinding"]["avg_optimality_ratio"], 1.25)
        self.assertEqual(payload["pathfinding"]["suboptimal_rate"], 0.5)

    def test_reverse_dijkstra_calculation(self) -> None:
        from delivery_robots.algorithms.astar import compute_reverse_dijkstra

        # Compute reverse Dijkstra costs from target node 3
        reverse_costs = compute_reverse_dijkstra(
            self.graph, dest_node=3, weight_fn=self.weight_fn
        )

        # Expected shortest path cost from node 1 to 3 is 240.0 (via 2)
        # Expected shortest path cost from node 2 to 3 is 120.0
        # Expected shortest path cost from node 3 to 3 is 0.0
        self.assertEqual(reverse_costs[1], 240.0)
        self.assertEqual(reverse_costs[2], 120.0)
        self.assertEqual(reverse_costs[3], 0.0)

    def test_astar_heuristic_effectiveness(self) -> None:
        from delivery_robots.algorithms.search_manager import run_weighted_route_search

        # Test A* returns heuristic_effectiveness in result
        res_astar = run_weighted_route_search(
            graph=self.graph,
            start_node=1,
            end_node=3,
            goal_lat=21.002,
            goal_lon=105.000,
            weight_fn=self.weight_fn,
            algorithm="astar",
        )
        # Ensure heuristic_effectiveness exists and is within [0.0, 1.0]
        self.assertTrue(hasattr(res_astar, "heuristic_effectiveness"))
        self.assertTrue(0.0 <= res_astar.heuristic_effectiveness <= 1.0)

    def test_metrics_heuristic_effectiveness_recording(self) -> None:
        from delivery_robots.utils.metrics import (
            create_metrics,
            record_route_metrics,
            build_metrics_payload,
        )

        metrics = create_metrics()
        self.assertIn("avg_heuristic_effectiveness", metrics)
        self.assertEqual(metrics["avg_heuristic_effectiveness"], 1.0)

        # Record route metrics with heuristic_effectiveness = 0.8
        record_route_metrics(
            metrics,
            calc_time_ms=5.0,
            nodes_explored=10,
            path_length=3,
            memory_bytes=100,
            optimality_ratio=1.0,
            heuristic_effectiveness=0.8,
        )
        self.assertEqual(metrics["last_heuristic_effectiveness"], 0.8)
        self.assertEqual(metrics["avg_heuristic_effectiveness"], 0.8)

        # Record another route metrics with heuristic_effectiveness = 0.6
        record_route_metrics(
            metrics,
            calc_time_ms=6.0,
            nodes_explored=12,
            path_length=4,
            memory_bytes=120,
            optimality_ratio=1.5,
            heuristic_effectiveness=0.6,
        )
        self.assertEqual(metrics["last_heuristic_effectiveness"], 0.6)
        self.assertAlmostEqual(metrics["avg_heuristic_effectiveness"], 0.7)

        # Build payload and verify
        payload = build_metrics_payload(
            metrics, self.graph, rain_count=0, traffic_count=0, obstacle_count=0
        )
        self.assertEqual(payload["pathfinding"]["avg_heuristic_effectiveness"], 0.7)
        self.assertEqual(payload["pathfinding"]["last_heuristic_effectiveness"], 0.6)

    def test_metrics_payload_new_snake_case_fields(self) -> None:
        from delivery_robots.utils.metrics import (
            create_metrics,
            record_route_metrics,
            record_delivery_gap,
            build_metrics_payload,
        )

        metrics = create_metrics()
        self.assertEqual(metrics["plan_execute_gap"], 0.0)
        self.assertEqual(metrics["failure_rate"], 0.0)

        # Record a route metric
        record_route_metrics(
            metrics,
            calc_time_ms=10.0,
            nodes_explored=5,
            path_length=2,
            memory_bytes=50,
            optimality_ratio=1.1,
            heuristic_effectiveness=0.9,
        )

        # Record a delivery gap
        record_delivery_gap(metrics, 15.5)
        self.assertEqual(metrics["plan_execute_gap"], 15.5)
        self.assertEqual(metrics["total_plan_execute_gap"], 15.5)
        self.assertEqual(metrics["total_deliveries"], 1)

        # Increment total and failed orders
        metrics["total_orders"] = 10
        metrics["failed_orders"] = 2

        payload = build_metrics_payload(
            metrics, self.graph, rain_count=1, traffic_count=2, obstacle_count=3
        )

        # Assert new payload fields
        self.assertEqual(payload["optimality_ratio"], 1.1)
        self.assertEqual(payload["plan_execute_gap"], 15.5)
        self.assertEqual(payload["heuristic_effectiveness"], 0.9)
        self.assertEqual(payload["failure_rate"], 0.2)
        self.assertEqual(payload["suboptimal_rate"], 1.0)  # since 1.1 > 1.05

        # Check pathfinding structure
        self.assertEqual(payload["pathfinding"]["optimality_ratio"], 1.1)
        self.assertEqual(payload["pathfinding"]["plan_execute_gap"], 15.5)
        self.assertEqual(payload["pathfinding"]["heuristic_effectiveness"], 0.9)
        self.assertEqual(payload["pathfinding"]["suboptimal_rate"], 1.0)

        # Check failure_metrics structure
        self.assertEqual(payload["failure_metrics"]["failed_orders"], 2)
        self.assertEqual(payload["failure_metrics"]["total_orders"], 10)
        self.assertEqual(payload["failure_metrics"]["failure_rate"], 0.2)


if __name__ == "__main__":
    unittest.main()
