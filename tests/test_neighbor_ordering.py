import unittest
import networkx as nx
from delivery_robots.utils.geo import calculate_bearing
from delivery_robots.algorithms.base import get_ordered_neighbors, SearchInput
from delivery_robots.algorithms.dfs import DFSSearch
from delivery_robots.algorithms.bfs import BFSSearch
from delivery_robots.algorithms.dijkstra import DijkstraSearch
from delivery_robots.algorithms.astar import AStarSearch
from delivery_robots.algorithms.gbfs import GBFSSearch


class NeighborOrderingTests(unittest.TestCase):
    def test_calculate_bearing(self):
        # North
        self.assertAlmostEqual(
            calculate_bearing(21.0, 105.0, 21.01, 105.0), 0.0, places=1
        )
        # East
        self.assertAlmostEqual(
            calculate_bearing(21.0, 105.0, 21.0, 105.01), 90.0, places=1
        )
        # South
        self.assertAlmostEqual(
            calculate_bearing(21.0, 105.0, 20.99, 105.0), 180.0, places=1
        )
        # West
        self.assertAlmostEqual(
            calculate_bearing(21.0, 105.0, 21.0, 104.99), 270.0, places=1
        )

    def test_get_ordered_neighbors_id_policy(self):
        graph = nx.MultiDiGraph()
        graph.add_node(1, x=105.0, y=21.0)
        graph.add_node(3, x=105.0, y=21.1)
        graph.add_node(2, x=105.1, y=21.0)
        graph.add_edge(1, 3)
        graph.add_edge(1, 2)

        neighbors = get_ordered_neighbors(graph, 1, 3, "id")
        self.assertEqual(neighbors, [2, 3])

    def test_get_ordered_neighbors_bearing_policy(self):
        graph = nx.MultiDiGraph()
        # Start u
        graph.add_node(1, x=105.0, y=21.0)
        # Goal T is to the East (bearing 90)
        graph.add_node(4, x=105.05, y=21.0)
        # Neighbor 2 is North (bearing 0, diff 90)
        graph.add_node(2, x=105.0, y=21.02)
        # Neighbor 3 is East (bearing 90, diff 0)
        graph.add_node(3, x=105.02, y=21.0)

        graph.add_edge(1, 2)
        graph.add_edge(1, 3)

        # Under bearing policy, 3 is closer to goal direction than 2, so 3 is prioritized
        neighbors = get_ordered_neighbors(graph, 1, 4, "bearing")
        self.assertEqual(neighbors, [3, 2])

    def test_dfs_path_changes_with_policy(self):
        graph = nx.MultiDiGraph()
        graph.add_node(1, x=105.0, y=21.0)
        graph.add_node(4, x=105.05, y=21.0)
        graph.add_node(2, x=105.0, y=21.02)
        graph.add_node(3, x=105.02, y=21.0)

        graph.add_edge(1, 2, length=10.0)
        graph.add_edge(1, 3, length=10.0)
        graph.add_edge(2, 4, length=10.0)
        graph.add_edge(3, 4, length=10.0)

        def weight_fn(u, v, d):
            return 10.0

        # 1. Under "id" policy, neighbors of 1 are sorted as [2, 3].
        # For DFS, stack gets [3, 2], so 2 is visited first.
        # Path should be [1, 2, 4].
        context_id = SearchInput(
            graph=graph,
            start_node=1,
            end_node=4,
            weight_fn=weight_fn,
            goal_lat=21.0,
            goal_lon=105.05,
            neighbor_ordering_policy="id",
        )
        res_id = DFSSearch().execute(context_id)
        self.assertEqual(res_id.path, [1, 2, 4])

        # 2. Under "bearing" policy, neighbors of 1 are sorted as [3, 2].
        # For DFS, stack gets [2, 3], so 3 is visited first.
        # Path should be [1, 3, 4].
        context_bearing = SearchInput(
            graph=graph,
            start_node=1,
            end_node=4,
            weight_fn=weight_fn,
            goal_lat=21.0,
            goal_lon=105.05,
            neighbor_ordering_policy="bearing",
        )
        res_bearing = DFSSearch().execute(context_bearing)
        self.assertEqual(res_bearing.path, [1, 3, 4])

    def test_algorithms_compilation(self):
        # Simply ensure all five algorithms compile and run without exceptions with the new parameter
        graph = nx.MultiDiGraph()
        graph.add_node(1, x=105.0, y=21.0)
        graph.add_node(2, x=105.01, y=21.0)
        graph.add_edge(1, 2, length=10.0)

        def weight_fn(u, v, d):
            return 10.0

        context = SearchInput(
            graph=graph,
            start_node=1,
            end_node=2,
            weight_fn=weight_fn,
            goal_lat=21.0,
            goal_lon=105.01,
            neighbor_ordering_policy="bearing",
        )

        for alg in [
            BFSSearch(),
            DFSSearch(),
            DijkstraSearch(),
            AStarSearch(),
            GBFSSearch(),
        ]:
            res = alg.execute(context)
            self.assertEqual(res.path, [1, 2])


if __name__ == "__main__":
    unittest.main()
