"""Module containing the non-invasive metrics interceptor and decorator."""

import functools
import os
import time
import tracemalloc
from typing import Callable, List, TypeVar, Any

# Ensure tracemalloc is started globally for memory tracking
if not tracemalloc.is_tracing():
    tracemalloc.start()

T = TypeVar("T")


class MetricsInterceptor:
    """Class responsible for managing metrics callbacks and logging."""

    _callbacks: List[Callable[[float, int, int, int, str], None]] = []
    log_dir: str = "logs"
    log_file: str = os.path.join(log_dir, "interceptor.log")

    @classmethod
    def register_callback(
        cls, callback: Callable[[float, int, int, int, str], None]
    ) -> None:
        """Registers a callback function to receive search metrics.

        Args:
            callback: A callable taking (calc_time_ms, nodes_explored, path_length,
                memory_bytes, algo_name, optimality_ratio).
        """
        cls._callbacks.append(callback)

    @classmethod
    def notify(
        cls,
        calc_time_ms: float,
        nodes_explored: int,
        path_length: int,
        memory_bytes: int,
        algo_name: str,
        optimality_ratio: float = 1.0,
        heuristic_effectiveness: float = 1.0,
    ) -> None:
        """Notifies all registered callbacks and logs metrics to file.

        Args:
            calc_time_ms (float): Computation time in milliseconds.
            nodes_explored (int): Number of nodes explored.
            path_length (int): Number of nodes in the planned path.
            memory_bytes (int): Memory used during execution in bytes.
            algo_name (str): Name of the pathfinding algorithm.
            optimality_ratio (float): The optimality ratio compared to Dijkstra.
            heuristic_effectiveness (float): The heuristic effectiveness ratio.
        """
        # Notify callbacks
        for cb in cls._callbacks:
            try:
                cb(
                    calc_time_ms,
                    nodes_explored,
                    path_length,
                    memory_bytes,
                    algo_name,
                    optimality_ratio,
                    heuristic_effectiveness,
                )
            except TypeError:
                try:
                    cb(
                        calc_time_ms,
                        nodes_explored,
                        path_length,
                        memory_bytes,
                        algo_name,
                        optimality_ratio,
                    )
                except TypeError:
                    try:
                        cb(
                            calc_time_ms,
                            nodes_explored,
                            path_length,
                            memory_bytes,
                            algo_name,
                        )
                    except Exception:
                        pass
                except Exception:
                    pass
            except Exception:
                pass

        # Log metrics to file
        try:
            if not os.path.exists(cls.log_dir):
                os.makedirs(cls.log_dir)

            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            log_line = (
                f"[{timestamp}] [{algo_name}] "
                f"Path Length: {path_length} | "
                f"Nodes Explored: {nodes_explored} | "
                f"Time: {calc_time_ms:.2f} ms | "
                f"Memory: {memory_bytes} bytes | "
                f"Optimality Ratio: {optimality_ratio:.3f} | "
                f"Heuristic Effectiveness: {heuristic_effectiveness:.3f}\n"
            )
            with open(cls.log_file, "a") as f:
                f.write(log_line)
        except Exception:
            pass


def intercept_measure(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to intercept and measure search algorithm metrics non-invasively.

    Args:
        func: The function/method to be wrapped.

    Returns:
        The wrapped function.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        # Reset peak to measure peak allocation for this call specifically.
        # Note: In multi-threaded environments, reset_peak is shared,
        # but provides a good process-level estimate for benchmarking.
        tracemalloc.reset_peak()
        start_time = time.perf_counter()
        start_mem, _ = tracemalloc.get_traced_memory()

        # Run the search algorithm
        result = func(*args, **kwargs)

        end_time = time.perf_counter()
        _, peak_mem = tracemalloc.get_traced_memory()

        calc_time_ms = (end_time - start_time) * 1000.0
        memory_bytes = peak_mem - start_mem
        if memory_bytes < 0:
            memory_bytes = 0

        nodes_explored = 0
        path_length = 0
        optimality_ratio = 1.0

        # Extract metrics from result object dynamically to remain generic
        if hasattr(result, "explored_count"):
            nodes_explored = getattr(result, "explored_count") or 0
        elif isinstance(result, tuple) and len(result) >= 2:
            nodes_explored = result[1]

        if hasattr(result, "path"):
            path = getattr(result, "path")
            path_length = len(path) if path else 0
        elif isinstance(result, tuple) and len(result) >= 1:
            path = result[0]
            path_length = len(path) if path else 0

        if hasattr(result, "optimality_ratio"):
            optimality_ratio = getattr(result, "optimality_ratio")

        heuristic_effectiveness = 1.0
        if hasattr(result, "heuristic_effectiveness"):
            heuristic_effectiveness = getattr(result, "heuristic_effectiveness")

        # Derive algorithm name from class/function name
        algo_name = func.__name__
        if args and hasattr(args[0], "__class__"):
            algo_name = args[0].__class__.__name__

        MetricsInterceptor.notify(
            calc_time_ms=calc_time_ms,
            nodes_explored=nodes_explored,
            path_length=path_length,
            memory_bytes=memory_bytes,
            algo_name=algo_name,
            optimality_ratio=optimality_ratio,
            heuristic_effectiveness=heuristic_effectiveness,
        )

        return result

    return wrapper
