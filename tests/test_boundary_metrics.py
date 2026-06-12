import unittest
import networkx as nx
from delivery_robots.algorithms.exceptions import NoPathError, RoutingTimeoutError
from delivery_robots.algorithms import run_weighted_route_search
from delivery_robots.utils import MetricsInterceptor
from delivery_robots.utils.metrics import (
    create_metrics,
    record_route_metrics,
    record_route_failure,
    record_battery_failure,
    build_metrics_payload,
)


class TestBoundaryMetrics(unittest.TestCase):
    def setUp(self) -> None:
        # Clear metrics callbacks
        MetricsInterceptor._callbacks = []
        MetricsInterceptor._failure_callbacks = []

        # Create a basic test graph
        self.graph = nx.MultiDiGraph()
        self.graph.add_node(1, x=105.000, y=21.000)
        self.graph.add_node(2, x=105.000, y=21.001)
        self.graph.add_node(3, x=105.000, y=21.002)
        self.graph.add_edge(1, 2, length=100.0)
        self.graph.add_edge(2, 3, length=100.0)

        def weight_fn(u, v, d):
            return d.get("length", 1.0)

        self.weight_fn = weight_fn

    def test_routing_timeout_exception_handling(self) -> None:
        # Set routing timeout to a negative number to trigger immediate timeout
        from delivery_robots import config

        original_timeout = config.ROUTING_TIMEOUT_MS
        config.ROUTING_TIMEOUT_MS = -1.0

        try:
            with self.assertRaises(RoutingTimeoutError):
                run_weighted_route_search(
                    graph=self.graph,
                    start_node=1,
                    end_node=3,
                    goal_lat=21.002,
                    goal_lon=105.000,
                    weight_fn=self.weight_fn,
                    algorithm="astar",
                )
        finally:
            config.ROUTING_TIMEOUT_MS = original_timeout

    def test_routing_no_path_custom_exception(self) -> None:
        # Remove edges to ensure no path exists
        unconnected_graph = nx.MultiDiGraph()
        unconnected_graph.add_node(1, x=105.000, y=21.000)
        unconnected_graph.add_node(3, x=105.000, y=21.002)

        with self.assertRaises(NoPathError):
            run_weighted_route_search(
                graph=unconnected_graph,
                start_node=1,
                end_node=3,
                goal_lat=21.002,
                goal_lon=105.000,
                weight_fn=self.weight_fn,
                algorithm="astar",
            )

    def test_metrics_failure_callback_triggered(self) -> None:
        called_metrics = []

        def failure_callback(
            calc_time_ms: float,
            memory_bytes: int,
            algo_name: str,
            error: Exception,
            graph=None,
            start_node=None,
            end_node=None,
            nodes_explored: int = 0,
        ) -> None:
            called_metrics.append(
                (
                    calc_time_ms,
                    memory_bytes,
                    algo_name,
                    error,
                    start_node,
                    end_node,
                    nodes_explored,
                )
            )

        MetricsInterceptor.register_failure_callback(failure_callback)

        unconnected_graph = nx.MultiDiGraph()
        unconnected_graph.add_node(1, x=105.000, y=21.000)
        unconnected_graph.add_node(3, x=105.000, y=21.002)

        try:
            run_weighted_route_search(
                graph=unconnected_graph,
                start_node=1,
                end_node=3,
                goal_lat=21.002,
                goal_lon=105.000,
                weight_fn=self.weight_fn,
                algorithm="astar",
            )
        except NoPathError:
            pass

        self.assertEqual(len(called_metrics), 1)
        calc_time, mem, name, error, start, end, nodes = called_metrics[0]
        self.assertTrue(calc_time >= 0.0)
        self.assertEqual(name, "AStarSearch")
        self.assertIsInstance(error, NoPathError)
        self.assertEqual(start, 1)
        self.assertEqual(end, 3)

    def test_record_route_failure_and_battery_failure(self) -> None:
        metrics = create_metrics()
        self.assertEqual(metrics["failed_queries"], 0)
        self.assertEqual(metrics["battery_failures"], 0)
        self.assertEqual(metrics["total_queries"], 0)

        # Record failure
        record_route_failure(
            metrics=metrics,
            calc_time_ms=10.0,
            memory_bytes=200,
            algo_name="AStarSearch",
            error=NoPathError("No Path", nodes_explored=5),
            start_node=1,
            end_node=3,
            nodes_explored=5,
        )

        self.assertEqual(metrics["failed_queries"], 1)
        self.assertEqual(metrics["total_queries"], 1)

        # Record battery failure
        record_battery_failure(metrics)
        self.assertEqual(metrics["battery_failures"], 1)

        # Build metrics payload
        payload = build_metrics_payload(
            metrics, self.graph, rain_count=0, traffic_count=0, obstacle_count=0
        )
        self.assertEqual(payload["failure_metrics"]["failed_queries"], 1)
        self.assertEqual(payload["failure_metrics"]["battery_failures"], 1)
        self.assertEqual(payload["failure_metrics"]["total_queries"], 1)
        self.assertEqual(
            payload["failure_rate"], 1.0
        )  # (1 failed + 1 battery) / 1 query = 2 / 1 clamped to 1.0

    def test_worst_case_scenario_tracking(self) -> None:
        metrics = create_metrics()

        # Record a fast successful route
        record_route_metrics(
            metrics=metrics,
            calc_time_ms=5.0,
            nodes_explored=3,
            path_length=2,
            path=[1, 2],
            algo_name="AStarSearch",
        )

        # Record a slower successful route (worst case)
        record_route_metrics(
            metrics=metrics,
            calc_time_ms=25.0,
            nodes_explored=15,
            path_length=3,
            path=[1, 2, 3],
            algo_name="AStarSearch",
        )

        # Record a failed route with even more nodes explored
        record_route_failure(
            metrics=metrics,
            calc_time_ms=15.0,
            memory_bytes=100,
            algo_name="AStarSearch",
            error=NoPathError("No Path", nodes_explored=50),
            start_node=1,
            end_node=3,
            nodes_explored=50,
        )

        worst = metrics["worst_case"]["AStarSearch"]
        self.assertEqual(worst["max_calculation_time"], 25.0)
        self.assertEqual(worst["max_nodes_explored"], 50)

        # Verify time query is the successful 25ms one
        self.assertEqual(worst["worst_time_query"]["calc_time_ms"], 25.0)
        self.assertEqual(worst["worst_time_query"]["status"], "success")

        # Verify nodes query is the failed 50 nodes one
        self.assertEqual(worst["worst_nodes_query"]["nodes_explored"], 50)
        self.assertEqual(worst["worst_nodes_query"]["status"], "failure")


if __name__ == "__main__":
    unittest.main()
