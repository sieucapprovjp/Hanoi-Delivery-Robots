"""Module containing the StatsEngine class for statistical analysis of routing algorithms."""

import time
from typing import Any, Dict, List, Tuple
import scipy.stats as stats


class StatsEngine:
    """Class responsible for compiling routing metrics and performing statistical analysis.

    This class can register itself as a callback on the MetricsInterceptor to automatically
    record all search algorithm execution metrics.
    """

    def __init__(self) -> None:
        """Initializes the StatsEngine with empty history."""
        self.history: List[Dict[str, Any]] = []

    def clear_history(self) -> None:
        """Clears the collected execution metrics history.

        Returns:
            None
        """
        self.history.clear()
        return None

    def record_run(
        self,
        calc_time_ms: float,
        nodes_explored: int,
        path_length: int,
        memory_bytes: int,
        algo_name: str,
        optimality_ratio: float = 1.0,
        heuristic_effectiveness: float = 1.0,
        graph: Any | None = None,
        path: List[int] | None = None,
    ) -> None:
        """Callback method to record a search execution's metrics.

        Args:
            calc_time_ms (float): Execution duration in milliseconds.
            nodes_explored (int): Number of nodes explored.
            path_length (int): Number of nodes in the planned path.
            memory_bytes (int): Memory usage in bytes.
            algo_name (str): The name of the pathfinding algorithm.
            optimality_ratio (float): Ratio compared to Dijkstra optimal baseline.
            heuristic_effectiveness (float): Estimator of heuristic efficacy.
            graph (Any | None): The network graph instance.
            path (List[int] | None): The computed path node sequence.

        Returns:
            None
        """
        start_node = path[0] if path else None
        end_node = path[-1] if path else None
        planning_time = 0.0
        neighbor_ordering_policy = "id"

        if graph is not None:
            planning_time = getattr(graph, "planning_time", 0.0)
            if hasattr(graph, "neighbor_ordering_policy"):
                neighbor_ordering_policy = getattr(graph, "neighbor_ordering_policy")
            elif hasattr(graph, "snap_state") and graph.snap_state:
                neighbor_ordering_policy = graph.snap_state.get(
                    "neighbor_ordering_policy", "id"
                )

        self.history.append(
            {
                "timestamp": time.time(),
                "algo_name": algo_name,
                "calc_time_ms": calc_time_ms,
                "nodes_explored": nodes_explored,
                "path_length": path_length,
                "memory_bytes": memory_bytes,
                "optimality_ratio": optimality_ratio,
                "heuristic_effectiveness": heuristic_effectiveness,
                "start_node": start_node,
                "end_node": end_node,
                "planning_time": planning_time,
                "neighbor_ordering_policy": neighbor_ordering_policy,
            }
        )
        return None

    def get_paired_metrics(
        self, algo1: str, algo2: str, metric: str
    ) -> Tuple[List[float], List[float]]:
        """Pairs performance metrics of two algorithms based on their execution context.

        It groups queries by (start_node, end_node, planning_time, neighbor_ordering_policy)
        and pairs the k-th run of each algorithm. If no context-matched pairs can be found,
        it falls back to sequential/chronological pairing.

        Args:
            algo1 (str): Name of the first algorithm.
            algo2 (str): Name of the second algorithm.
            metric (str): The metric name to extract (e.g. 'calc_time_ms').

        Returns:
            Tuple[List[float], List[float]]: Two parallel lists representing paired metric values.
        """
        runs1 = [r for r in self.history if r["algo_name"] == algo1]
        runs2 = [r for r in self.history if r["algo_name"] == algo2]

        grouped1: Dict[Tuple[Any, Any, float, str], List[float]] = {}
        for r in runs1:
            key = (
                r["start_node"],
                r["end_node"],
                r["planning_time"],
                r["neighbor_ordering_policy"],
            )
            if key[0] is not None and key[1] is not None:
                grouped1.setdefault(key, []).append(float(r[metric]))

        grouped2: Dict[Tuple[Any, Any, float, str], List[float]] = {}
        for r in runs2:
            key = (
                r["start_node"],
                r["end_node"],
                r["planning_time"],
                r["neighbor_ordering_policy"],
            )
            if key[0] is not None and key[1] is not None:
                grouped2.setdefault(key, []).append(float(r[metric]))

        paired1: List[float] = []
        paired2: List[float] = []

        common_keys = set(grouped1.keys()) & set(grouped2.keys())
        for key in sorted(common_keys, key=lambda k: (k[2], k[0], k[1])):
            list1 = grouped1[key]
            list2 = grouped2[key]
            min_len = min(len(list1), len(list2))
            paired1.extend(list1[:min_len])
            paired2.extend(list2[:min_len])

        if not paired1:
            min_len = min(len(runs1), len(runs2))
            for i in range(min_len):
                paired1.append(float(runs1[i][metric]))
                paired2.append(float(runs2[i][metric]))

        return paired1, paired2

    def wilcoxon_test(
        self, x: List[float], y: List[float]
    ) -> Tuple[float, float, bool]:
        """Performs a paired Wilcoxon Signed-Rank Test.

        Args:
            x (List[float]): Metric measurements for the first algorithm.
            y (List[float]): Metric measurements for the second algorithm.

        Returns:
            Tuple[float, float, bool]: A tuple containing (statistic, p_value, is_significant).
                - statistic (float): The Wilcoxon test statistic.
                - p_value (float): The calculated p-value (two-sided).
                - is_significant (bool): True if p_value < 0.05.
        """
        if not x or not y or len(x) != len(y):
            return 0.0, 1.0, False

        # Check if all differences are zero.
        # Wilcoxon requires at least one non-zero difference.
        diffs = [xi - yi for xi, yi in zip(x, y)]
        if all(d == 0 for d in diffs):
            return 0.0, 1.0, False

        try:
            res = stats.wilcoxon(x, y, alternative="two-sided")
            statistic = float(res.statistic)
            p_value = float(res.pvalue)
            is_significant = p_value < 0.05
            return statistic, p_value, is_significant
        except ValueError:
            return 0.0, 1.0, False

    def confidence_interval(
        self, data: List[float], confidence: float = 0.95
    ) -> Tuple[float, float]:
        """Calculates the confidence interval for a dataset using t-Student distribution.

        Args:
            data (List[float]): The dataset to analyze.
            confidence (float): The confidence level (default 0.95).

        Returns:
            Tuple[float, float]: A tuple representing the lower and upper bounds of the CI.
        """
        n = len(data)
        if n == 0:
            return 0.0, 0.0
        mean = sum(data) / n
        if n <= 1:
            return mean, mean

        try:
            import math

            sem = stats.sem(data)
            if sem == 0.0:
                return mean, mean
            ci = stats.t.interval(confidence, df=n - 1, loc=mean, scale=sem)
            if math.isnan(ci[0]) or math.isnan(ci[1]):
                return mean, mean
            return float(ci[0]), float(ci[1])
        except Exception:
            return mean, mean

    def compare_algorithms(self, algo1: str, algo2: str, metric: str) -> Dict[str, Any]:
        """Performs a comprehensive paired performance comparison between two algorithms.

        Args:
            algo1 (str): Name of the first algorithm.
            algo2 (str): Name of the second algorithm.
            metric (str): Metric name to compare.

        Returns:
            Dict[str, Any]: A dictionary containing statistical test parameters, significance,
                means, mean difference, and confidence intervals.
        """
        x, y = self.get_paired_metrics(algo1, algo2, metric)
        if not x:
            return {
                "metric": metric,
                "algo1": algo1,
                "algo2": algo2,
                "n_samples": 0,
                "w_statistic": 0.0,
                "p_value": 1.0,
                "is_significant": False,
                "algo1_mean": 0.0,
                "algo2_mean": 0.0,
                "mean_difference": 0.0,
                "algo1_ci": (0.0, 0.0),
                "algo2_ci": (0.0, 0.0),
                "ci_difference": (0.0, 0.0),
            }

        w_statistic, p_value, is_significant = self.wilcoxon_test(x, y)

        algo1_mean = sum(x) / len(x)
        algo2_mean = sum(y) / len(y)

        diffs = [xi - yi for xi, yi in zip(x, y)]
        mean_difference = sum(diffs) / len(diffs)

        algo1_ci = self.confidence_interval(x)
        algo2_ci = self.confidence_interval(y)
        ci_difference = self.confidence_interval(diffs)

        return {
            "metric": metric,
            "algo1": algo1,
            "algo2": algo2,
            "n_samples": len(x),
            "w_statistic": w_statistic,
            "p_value": p_value,
            "is_significant": is_significant,
            "algo1_mean": algo1_mean,
            "algo2_mean": algo2_mean,
            "mean_difference": mean_difference,
            "algo1_ci": algo1_ci,
            "algo2_ci": algo2_ci,
            "ci_difference": ci_difference,
        }
