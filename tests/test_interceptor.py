import unittest
from typing import Tuple, List
from delivery_robots.utils.interceptor import MetricsInterceptor, intercept_measure
from delivery_robots.algorithms.base import AlgoResult


class TestInterceptor(unittest.TestCase):
    def setUp(self) -> None:
        # Clear callbacks
        MetricsInterceptor._callbacks = []

    def test_interceptor_decorator_preserves_return_value_algo_result(self) -> None:
        @intercept_measure
        def dummy_search_algo_result() -> AlgoResult:
            return AlgoResult(
                path=[1, 2, 3],
                explored_count=10,
                planned_cost=5.5,
                planning_time=100.0,
            )

        res = dummy_search_algo_result()
        self.assertEqual(res.path, [1, 2, 3])
        self.assertEqual(res.explored_count, 10)
        self.assertEqual(res.planned_cost, 5.5)

    def test_interceptor_decorator_preserves_return_value_tuple(self) -> None:
        @intercept_measure
        def dummy_search_tuple() -> Tuple[List[int], int]:
            return [1, 2, 3], 15

        res = dummy_search_tuple()
        self.assertEqual(res[0], [1, 2, 3])
        self.assertEqual(res[1], 15)

    def test_interceptor_triggers_callback_with_correct_metrics(self) -> None:
        called_metrics = []

        def callback(
            calc_time_ms: float,
            nodes_explored: int,
            path_length: int,
            memory_bytes: int,
            algo_name: str,
        ) -> None:
            called_metrics.append(
                (calc_time_ms, nodes_explored, path_length, memory_bytes, algo_name)
            )

        MetricsInterceptor.register_callback(callback)

        @intercept_measure
        def execute_dummy_search() -> AlgoResult:
            # Allocate memory to ensure memory tracking can detect some usage
            _x = [i for i in range(1000)]  # noqa: F841
            return AlgoResult(
                path=[10, 20, 30, 40],
                explored_count=42,
                planned_cost=12.3,
                planning_time=1.0,
            )

        execute_dummy_search()

        self.assertEqual(len(called_metrics), 1)
        calc_time, nodes_exp, path_len, mem, name = called_metrics[0]
        self.assertTrue(calc_time >= 0.0)
        self.assertEqual(nodes_exp, 42)
        self.assertEqual(path_len, 4)
        self.assertTrue(mem >= 0)
        self.assertEqual(name, "execute_dummy_search")


if __name__ == "__main__":
    unittest.main()
