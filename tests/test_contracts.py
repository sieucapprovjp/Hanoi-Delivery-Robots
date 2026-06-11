import unittest
from delivery_robots.algorithms.base import (
    SearchContract,
    AssignmentContract,
    ChargingPolicyContract,
)


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


import networkx as nx
from delivery_robots.algorithms.base import SearchInput, AlgoResult, ExecutionTrace
from delivery_robots.algorithms.astar import AStarSearch
from delivery_robots.algorithms.dijkstra import DijkstraSearch
from delivery_robots.algorithms.gbfs import GBFSSearch
from delivery_robots.algorithms.dfs import DFSSearch
from delivery_robots.algorithms.bfs import BFSSearch
from delivery_robots.core.environment import SnapFactory


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

        self.weight_fn = (
            lambda u, v, d: d.get("length", 1.0)
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
            state["obstacles"].append({"center": (21.1, 105.1), "radius": 100.0, "severity": 5.0})

        # Verify that snapshot1 remains isolated (does not contain the new obstacle)
        self.assertEqual(len(snapshot1.snap_state["obstacles"]), 1)


if __name__ == "__main__":
    unittest.main()

