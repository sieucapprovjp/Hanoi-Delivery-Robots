"""Unit tests for the StatsEngine utility."""

import unittest

from delivery_robots.utils.stats_engine import StatsEngine
from delivery_robots.utils.interceptor import MetricsInterceptor, intercept_measure
from delivery_robots.algorithms.base import AlgoResult


class TestStatsEngine(unittest.TestCase):
    """Test suite for the StatsEngine class and its statistical analysis functions."""

    def setUp(self) -> None:
        """Sets up a fresh instance of StatsEngine and clears registered callbacks."""
        self.engine = StatsEngine()
        MetricsInterceptor._callbacks = []
        return None

    def test_wilcoxon_test_significant_difference(self) -> None:
        """Tests Wilcoxon test on inputs with a large, consistent difference."""
        x = [
            1.2,
            1.5,
            1.8,
            2.0,
            1.4,
            1.6,
            1.9,
            2.1,
            1.5,
            1.7,
            1.8,
            1.4,
        ] * 3  # 36 elements
        # y is systematically larger
        y = [val + 0.5 for val in x]

        stat, p_val, sig = self.engine.wilcoxon_test(x, y)
        self.assertTrue(stat >= 0.0)
        self.assertTrue(p_val < 0.05)
        self.assertTrue(sig)
        return None

    def test_wilcoxon_test_no_difference(self) -> None:
        """Tests Wilcoxon test on identical inputs."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [1.0, 2.0, 3.0, 4.0, 5.0]

        stat, p_val, sig = self.engine.wilcoxon_test(x, y)
        self.assertEqual(stat, 0.0)
        self.assertEqual(p_val, 1.0)
        self.assertFalse(sig)
        return None

    def test_confidence_interval_normal_data(self) -> None:
        """Tests that confidence interval bounds are correctly calculated."""
        data = [10.0, 12.0, 11.0, 9.0, 13.0, 10.0, 11.0, 12.0]
        lower, upper = self.engine.confidence_interval(data, confidence=0.95)

        mean = sum(data) / len(data)
        self.assertTrue(lower < mean < upper)
        return None

    def test_confidence_interval_constant_data(self) -> None:
        """Tests that confidence interval on constant data returns the mean as bounds."""
        data = [5.0, 5.0, 5.0, 5.0]
        lower, upper = self.engine.confidence_interval(data)
        self.assertEqual(lower, 5.0)
        self.assertEqual(upper, 5.0)
        return None

    def test_confidence_interval_insufficient_data(self) -> None:
        """Tests confidence interval with 1 or 0 elements."""
        lower_1, upper_1 = self.engine.confidence_interval([42.0])
        self.assertEqual(lower_1, 42.0)
        self.assertEqual(upper_1, 42.0)

        lower_0, upper_0 = self.engine.confidence_interval([])
        self.assertEqual(lower_0, 0.0)
        self.assertEqual(upper_0, 0.0)
        return None

    def test_get_paired_metrics_by_query_context(self) -> None:
        """Tests pairing of metrics based on the query context key."""
        # Setup runs for algo1
        # Run 1: Query A
        self.engine.record_run(
            calc_time_ms=10.0,
            nodes_explored=5,
            path_length=2,
            memory_bytes=100,
            algo_name="algo1",
            path=[101, 102],
        )
        # Run 2: Query B
        self.engine.record_run(
            calc_time_ms=20.0,
            nodes_explored=8,
            path_length=3,
            memory_bytes=150,
            algo_name="algo1",
            path=[201, 202, 203],
        )

        # Setup runs for algo2 out of chronological order
        # Run 1: Query B (should pair with algo1 Run 2)
        self.engine.record_run(
            calc_time_ms=25.0,
            nodes_explored=12,
            path_length=3,
            memory_bytes=200,
            algo_name="algo2",
            path=[201, 202, 203],
        )
        # Run 2: Query A (should pair with algo1 Run 1)
        self.engine.record_run(
            calc_time_ms=12.0,
            nodes_explored=6,
            path_length=2,
            memory_bytes=110,
            algo_name="algo2",
            path=[101, 102],
        )

        x, y = self.engine.get_paired_metrics("algo1", "algo2", "calc_time_ms")

        # They should pair Query A first (since sorted by keys) then Query B
        self.assertEqual(len(x), 2)
        self.assertEqual(len(y), 2)
        # Context-based matching:
        # Query A: (101, 102) -> algo1=10.0, algo2=12.0
        # Query B: (201, 203) -> algo1=20.0, algo2=25.0
        self.assertEqual(x, [10.0, 20.0])
        self.assertEqual(y, [12.0, 25.0])
        return None

    def test_get_paired_metrics_chronological_fallback(self) -> None:
        """Tests that pairing falls back to chronological sequence if path is missing."""
        self.engine.record_run(
            calc_time_ms=10.0,
            nodes_explored=5,
            path_length=2,
            memory_bytes=100,
            algo_name="algo1",
            path=None,  # missing path -> start/end node are None
        )
        self.engine.record_run(
            calc_time_ms=15.0,
            nodes_explored=7,
            path_length=2,
            memory_bytes=110,
            algo_name="algo2",
            path=None,
        )

        x, y = self.engine.get_paired_metrics("algo1", "algo2", "calc_time_ms")
        self.assertEqual(x, [10.0])
        self.assertEqual(y, [15.0])
        return None

    def test_compare_algorithms(self) -> None:
        """Tests compare_algorithms method compiles statistics correctly."""
        # Populate history with matched pairs
        for i in range(10):
            self.engine.record_run(
                calc_time_ms=10.0 + i,
                nodes_explored=5,
                path_length=2,
                memory_bytes=100,
                algo_name="algo1",
                path=[1, 2],
            )
            self.engine.record_run(
                calc_time_ms=15.0 + i,
                nodes_explored=6,
                path_length=2,
                memory_bytes=120,
                algo_name="algo2",
                path=[1, 2],
            )

        res = self.engine.compare_algorithms("algo1", "algo2", "calc_time_ms")
        self.assertEqual(res["n_samples"], 10)
        self.assertEqual(res["algo1_mean"], 14.5)
        self.assertEqual(res["algo2_mean"], 19.5)
        self.assertEqual(res["mean_difference"], -5.0)
        self.assertTrue(len(res["algo1_ci"]) == 2)
        self.assertTrue(len(res["algo2_ci"]) == 2)
        self.assertTrue(len(res["ci_difference"]) == 2)
        return None

    def test_interceptor_callback_integration(self) -> None:
        """Tests StatsEngine integration with MetricsInterceptor decorator."""
        MetricsInterceptor.register_callback(self.engine.record_run)

        @intercept_measure
        def dummy_search() -> AlgoResult:
            return AlgoResult(
                path=[10, 20, 30],
                explored_count=15,
                planned_cost=3.5,
                planning_time=123.45,
            )

        dummy_search()

        self.assertEqual(len(self.engine.history), 1)
        record = self.engine.history[0]
        self.assertEqual(record["algo_name"], "dummy_search")
        self.assertEqual(record["start_node"], 10)
        self.assertEqual(record["end_node"], 30)
        self.assertEqual(record["nodes_explored"], 15)
        return None


if __name__ == "__main__":
    unittest.main()
