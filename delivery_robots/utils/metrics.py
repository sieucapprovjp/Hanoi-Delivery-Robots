from typing import Dict, Any
from ..config import METRICS_INITIAL_MIN_CALC_TIME, METRICS_PATH_LENGTHS_MAX_SIZE


def create_metrics() -> Dict[str, Any]:
    """Initializes the metrics collection dictionary.

    Returns:
        Dict[str, Any]: A dictionary containing all search and simulation metrics initialized to default values.
    """
    return {
        "total_calculations": 0,
        "avg_calculation_time": 0.0,
        "last_calculation_time": 0.0,
        "min_calculation_time": METRICS_INITIAL_MIN_CALC_TIME,
        "max_calculation_time": 0.0,
        "avg_nodes_explored": 0.0,
        "total_calculation_time": 0.0,
        "total_nodes_explored": 0,
        "path_lengths": [],
        "failed_orders": 0,
        "total_orders": 0,
        "failure_rate": 0.0,
        "total_memory_used": 0,
        "avg_memory_used": 0.0,
        "last_memory_used": 0,
        "max_memory_used": 0,
        "total_optimality_ratio": 0.0,
        "avg_optimality_ratio": 1.0,
        "last_optimality_ratio": 1.0,
        "max_optimality_ratio": 1.0,
        "suboptimal_calculations": 0,
        "suboptimal_rate": 0.0,
        "total_heuristic_effectiveness": 0.0,
        "avg_heuristic_effectiveness": 1.0,
        "last_heuristic_effectiveness": 1.0,
        "plan_execute_gap": 0.0,
        "total_plan_execute_gap": 0.0,
        "total_deliveries": 0,
        "optimality_ratio": 1.0,
        "heuristic_effectiveness": 1.0,
    }


def record_route_metrics(
    metrics: Dict[str, Any],
    calc_time_ms: float,
    nodes_explored: int,
    path_length: int,
    memory_bytes: int = 0,
    optimality_ratio: float = 1.0,
    heuristic_effectiveness: float = 1.0,
) -> None:
    """Records the route calculation metrics from a single query execution.

    Args:
        metrics (Dict[str, Any]): The metrics collection dictionary to update.
        calc_time_ms (float): Computation time in milliseconds.
        nodes_explored (int): Number of nodes explored.
        path_length (int): Length of the planned path.
        memory_bytes (int): Memory usage in bytes. Defaults to 0.
        optimality_ratio (float): Path optimality ratio. Defaults to 1.0.
        heuristic_effectiveness (float): Heuristic effectiveness ratio. Defaults to 1.0.
    """
    metrics["total_calculations"] += 1
    metrics["last_calculation_time"] = calc_time_ms
    metrics["min_calculation_time"] = min(metrics["min_calculation_time"], calc_time_ms)
    metrics["max_calculation_time"] = max(metrics["max_calculation_time"], calc_time_ms)
    metrics["total_calculation_time"] += calc_time_ms
    metrics["avg_calculation_time"] = (
        metrics["total_calculation_time"] / metrics["total_calculations"]
    )
    metrics["total_nodes_explored"] += nodes_explored
    metrics["avg_nodes_explored"] = (
        metrics["total_nodes_explored"] / metrics["total_calculations"]
    )
    metrics["path_lengths"].append(path_length)
    if len(metrics["path_lengths"]) > METRICS_PATH_LENGTHS_MAX_SIZE:
        metrics["path_lengths"] = metrics["path_lengths"][
            -METRICS_PATH_LENGTHS_MAX_SIZE:
        ]

    # Memory tracking
    metrics["last_memory_used"] = memory_bytes
    metrics["max_memory_used"] = max(metrics.get("max_memory_used", 0), memory_bytes)
    metrics["total_memory_used"] = metrics.get("total_memory_used", 0) + memory_bytes
    metrics["avg_memory_used"] = (
        metrics["total_memory_used"] / metrics["total_calculations"]
    )

    # Optimality Ratio tracking
    metrics["optimality_ratio"] = optimality_ratio
    metrics["last_optimality_ratio"] = optimality_ratio
    metrics["max_optimality_ratio"] = max(
        metrics.get("max_optimality_ratio", 1.0), optimality_ratio
    )
    metrics["total_optimality_ratio"] = (
        metrics.get("total_optimality_ratio", 0.0) + optimality_ratio
    )
    metrics["avg_optimality_ratio"] = (
        metrics["total_optimality_ratio"] / metrics["total_calculations"]
    )

    if optimality_ratio > 1.05:
        metrics["suboptimal_calculations"] = (
            metrics.get("suboptimal_calculations", 0) + 1
        )

    metrics["suboptimal_rate"] = (
        metrics.get("suboptimal_calculations", 0) / metrics["total_calculations"]
    )

    # Heuristic Effectiveness Ratio tracking
    metrics["heuristic_effectiveness"] = heuristic_effectiveness
    metrics["last_heuristic_effectiveness"] = heuristic_effectiveness
    metrics["total_heuristic_effectiveness"] = (
        metrics.get("total_heuristic_effectiveness", 0.0) + heuristic_effectiveness
    )
    metrics["avg_heuristic_effectiveness"] = (
        metrics["total_heuristic_effectiveness"] / metrics["total_calculations"]
    )


def record_delivery_gap(metrics: Dict[str, Any], gap: float) -> None:
    """Records the plan-execute gap from a completed delivery task.

    Args:
        metrics (Dict[str, Any]): The metrics collection dictionary to update.
        gap (float): The calculated plan-execute gap.
    """
    metrics["total_deliveries"] = metrics.get("total_deliveries", 0) + 1
    metrics["plan_execute_gap"] = gap
    metrics["total_plan_execute_gap"] = metrics.get("total_plan_execute_gap", 0.0) + gap


def build_metrics_payload(
    metrics: Dict[str, Any],
    graph: Any,
    rain_count: int,
    traffic_count: int,
    obstacle_count: int,
    include_static: bool = False,
) -> Dict[str, Any]:
    """Builds a formatted payload dictionary containing all system metrics.

    Args:
        metrics (Dict[str, Any]): The metrics collection dictionary.
        graph (Any): The road network graph.
        rain_count (int): Number of active rain zones.
        traffic_count (int): Number of active traffic routes.
        obstacle_count (int): Number of active obstacles.
        include_static (bool): Whether to include static graph details. Defaults to False.

    Returns:
        Dict[str, Any]: The formatted payload dictionary.
    """
    path_lengths = metrics.get("path_lengths", [])
    avg_path = sum(path_lengths) / len(path_lengths) if path_lengths else 0.0

    total_orders = metrics.get("total_orders", 0)
    failed_orders = metrics.get("failed_orders", 0)
    failure_rate = failed_orders / total_orders if total_orders > 0 else 0.0

    payload = {
        "pathfinding": {
            "total_calculations": metrics.get("total_calculations", 0),
            "avg_calculation_time": round(metrics.get("avg_calculation_time", 0.0), 2),
            "last_calculation_time": round(
                metrics.get("last_calculation_time", 0.0), 2
            ),
            "min_calculation_time": round(metrics.get("min_calculation_time", 0.0), 2)
            if metrics.get("min_calculation_time", METRICS_INITIAL_MIN_CALC_TIME)
            < METRICS_INITIAL_MIN_CALC_TIME
            else 0.0,
            "max_calculation_time": round(metrics.get("max_calculation_time", 0.0), 2),
            "avg_nodes_explored": round(metrics.get("avg_nodes_explored", 0.0), 1),
            "avg_path_length": round(avg_path, 1),
            "avg_memory_used_bytes": round(metrics.get("avg_memory_used", 0.0), 2),
            "last_memory_used_bytes": metrics.get("last_memory_used", 0),
            "max_memory_used_bytes": metrics.get("max_memory_used", 0),
            "avg_optimality_ratio": round(metrics.get("avg_optimality_ratio", 1.0), 3),
            "last_optimality_ratio": round(
                metrics.get("last_optimality_ratio", 1.0), 3
            ),
            "max_optimality_ratio": round(metrics.get("max_optimality_ratio", 1.0), 3),
            "suboptimal_rate": round(metrics.get("suboptimal_rate", 0.0), 3),
            "avg_heuristic_effectiveness": round(
                metrics.get("avg_heuristic_effectiveness", 1.0), 3
            ),
            "last_heuristic_effectiveness": round(
                metrics.get("last_heuristic_effectiveness", 1.0), 3
            ),
            "optimality_ratio": round(metrics.get("optimality_ratio", 1.0), 3),
            "plan_execute_gap": round(metrics.get("plan_execute_gap", 0.0), 3),
            "heuristic_effectiveness": round(
                metrics.get("heuristic_effectiveness", 1.0), 3
            ),
        },
        "active_factors": {
            "rain_zones": rain_count,
            "traffic_routes": traffic_count,
            "obstacles": obstacle_count,
        },
        "failure_metrics": {
            "failed_orders": failed_orders,
            "total_orders": total_orders,
            "failure_rate": round(failure_rate, 3),
        },
        "optimality_ratio": round(metrics.get("optimality_ratio", 1.0), 3),
        "plan_execute_gap": round(metrics.get("plan_execute_gap", 0.0), 3),
        "heuristic_effectiveness": round(
            metrics.get("heuristic_effectiveness", 1.0), 3
        ),
        "failure_rate": round(failure_rate, 3),
        "suboptimal_rate": round(metrics.get("suboptimal_rate", 0.0), 3),
    }

    if include_static:
        payload["graph"] = {
            "total_nodes": graph.number_of_nodes() if graph else 0,
            "total_edges": graph.number_of_edges() if graph else 0,
        }

    return payload
