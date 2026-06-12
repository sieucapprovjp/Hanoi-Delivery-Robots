"""Module defining unified contracts for search, assignment, and charging policy plugins.

This module provides the abstract base classes and input schemas to enforce
a unified interface across different algorithm implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar, Callable, List, Dict, Tuple, Any
import networkx as nx

Input = TypeVar("Input")
Output = TypeVar("Output")


@dataclass(frozen=True)
class AlgoResult:
    """planned route (Plan) found at planning time t0.

    Attributes:
        path (List[int]): List of node IDs representing the path.
        explored_count (int): Number of nodes explored during the search.
        planned_cost (float): Total calculated cost of the path at planning time.
        planning_time (float): The timestamp when the planning occurred.
        computation_time (float): Time taken to compute the path in seconds.
        optimality_ratio (float): Ratio of planned cost compared to optimal cost.
        heuristic_effectiveness (float): Effectiveness ratio of the heuristic.
    """

    path: List[int]
    explored_count: int
    planned_cost: float
    planning_time: float
    computation_time: float = 0.0
    optimality_ratio: float = 1.0
    heuristic_effectiveness: float = 1.0

    def __len__(self) -> int:
        return 2

    def __getitem__(self, index: int) -> Any:
        return (self.path, self.explored_count)[index]

    def __iter__(self):
        return iter((self.path, self.explored_count))


@dataclass(frozen=True)
class ExecutionTrace:
    """actual route travelled (Execute), recording actual GPS coordinates and actual energy/battery consumption.

    Attributes:
        gps_coords (List[Tuple[float, float]]): List of (latitude, longitude) visited.
        energy_consumed (float): Total battery/energy depleted.
        travel_time (float): Total travel time in seconds.
    """

    gps_coords: List[Tuple[float, float]]
    energy_consumed: float
    travel_time: float


@dataclass
class SearchInput:
    """Input context for path search algorithms.

    Attributes:
        graph (nx.MultiDiGraph): The road network graph.
        start_node (int): The start node identifier.
        end_node (int): The target node identifier.
        weight_fn (Callable[[int, int, dict], float]): Function to compute edge weight.
        goal_lat (float): The latitude of the destination coordinate.
        goal_lon (float): The longitude of the destination coordinate.
        neighbor_ordering_policy (str): The active neighbor ordering policy.
    """

    graph: nx.MultiDiGraph
    start_node: int
    end_node: int
    weight_fn: Callable[[int, int, dict], float]
    goal_lat: float = 0.0
    goal_lon: float = 0.0
    neighbor_ordering_policy: str = "id"


class SearchContract(ABC, Generic[Input, Output]):
    """Unified interface contract for path search algorithms."""

    @abstractmethod
    def execute(self, context: Input) -> Output:
        """Executes the pathfinding query under the contract.

        Args:
            context (Input): The input parameters required for the search.

        Returns:
            Output: The planned route and execution statistics.
        """
        pass


@dataclass
class AssignmentInput:
    """Input context for robot-to-order assignment algorithms.

    Attributes:
        graph (nx.MultiDiGraph): The road network graph snapshot.
        robots: List of active RobotAgent objects.
        orders: List of pending order dictionaries.
        nearest_node_fn: Function to find nearest node ID.
        weight_fn: Function to calculate edge weight.
        run_route_search_fn: Function to run path search algorithm.
        alpha (float): Travel cost weight to pickup point.
        beta (float): Travel cost weight from pickup to delivery.
        gamma (float): Battery penalty weight.
        val_lambda (float): Exponential coefficient in battery penalty function.
    """

    graph: nx.MultiDiGraph
    robots: List[Any]
    orders: List[Dict[str, Any]]
    nearest_node_fn: Callable[[nx.MultiDiGraph, float, float], int]
    weight_fn: Callable[[int, int, dict], float]
    run_route_search_fn: Callable[
        [
            nx.MultiDiGraph,
            int,
            int,
            float,
            float,
            Callable[[int, int, dict], float],
            str,
        ],
        Any,
    ]
    alpha: float = 1.0
    beta: float = 1.0
    gamma: float = 100.0
    val_lambda: float = 0.05


@dataclass(frozen=True)
class AssignmentPair:
    """Represents a matched robot and order with pre-computed paths.

    Attributes:
        robot (Any): The RobotAgent object.
        order (Dict[str, Any]): The order dictionary.
        pickup_path (List[int]): Pre-computed route path from robot's position to pickup.
        dropoff_path (List[int]): Pre-computed route path from pickup to delivery.
        cost (float): Calculated dispatch cost of this assignment.
        pickup_cost (float): Pre-computed route cost from robot's position to pickup.
        dropoff_cost (float): Pre-computed route cost from pickup to delivery.
    """

    robot: Any
    order: Dict[str, Any]
    pickup_path: List[int]
    dropoff_path: List[int]
    cost: float
    pickup_cost: float = 0.0
    dropoff_cost: float = 0.0


@dataclass(frozen=True)
class AssignmentResult:
    """Result containing all assignments made by the dispatcher model.

    Attributes:
        assignments (List[AssignmentPair]): List of assigned pairs.
    """

    assignments: List[AssignmentPair]


class AssignmentContract(ABC, Generic[Input, Output]):
    """Unified interface contract for robot-to-order assignment models."""

    @abstractmethod
    def execute(self, context: Input) -> Output:
        """Executes the assignment model under the contract.

        Args:
            context (Input): The input parameters required for the assignment.

        Returns:
            Output: The assigned pairs or routing results.
        """
        pass


class ChargingPolicyContract(ABC, Generic[Input, Output]):
    """Unified interface contract for robot charging decisions."""

    @abstractmethod
    def execute(self, context: Input) -> Output:
        """Executes the charging decision logic under the contract.

        Args:
            context (Input): The input parameters required for charging policy.

        Returns:
            Output: The decided charging action or selected hub.
        """
        pass


def reconstruct_node_path(came_from: Dict[int, int], current: int) -> List[int]:
    """Reconstructs the node path sequence from start to destination.

    Args:
        came_from (Dict[int, int]): Mapping of node IDs to parent node IDs.
        current (int): The destination node ID where reconstruction starts.

    Returns:
        List[int]: Sequential list of node IDs from start to destination.
    """
    path: List[int] = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path


def get_ordered_neighbors(
    graph: nx.MultiDiGraph, current: int, goal: int, policy: str
) -> List[int]:
    """Retrieves neighbors of a node, sorted according to the Neighbor Ordering Policy.

    Args:
        graph (nx.MultiDiGraph): The graph snapshot.
        current (int): The current node ID.
        goal (int): The destination/goal node ID.
        policy (str): The active Neighbor Ordering Policy ('id' or 'bearing').

    Returns:
        List[int]: Sorted list of neighbor node IDs.
    """
    neighbors = list(graph.neighbors(current))
    if policy == "bearing":
        if current not in graph.nodes or goal not in graph.nodes:
            return sorted(neighbors)

        lat_u = graph.nodes[current].get("y", 0.0)
        lon_u = graph.nodes[current].get("x", 0.0)
        lat_goal = graph.nodes[goal].get("y", 0.0)
        lon_goal = graph.nodes[goal].get("x", 0.0)

        from ..utils.geo import calculate_bearing

        bearing_u_goal = calculate_bearing(lat_u, lon_u, lat_goal, lon_goal)

        def get_neighbor_sort_key(v: int) -> Tuple[float, int]:
            if v not in graph.nodes:
                return (360.0, v)
            lat_v = graph.nodes[v].get("y", 0.0)
            lon_v = graph.nodes[v].get("x", 0.0)
            bearing_u_v = calculate_bearing(lat_u, lon_u, lat_v, lon_v)
            diff = abs(bearing_u_v - bearing_u_goal)
            angular_diff = min(diff, 360.0 - diff)
            return (angular_diff, v)

        return sorted(neighbors, key=get_neighbor_sort_key)
    else:
        return sorted(neighbors)
