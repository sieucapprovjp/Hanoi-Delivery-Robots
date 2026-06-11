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
    """

    path: List[int]
    explored_count: int
    planned_cost: float
    planning_time: float

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
    """

    graph: nx.MultiDiGraph
    start_node: int
    end_node: int
    weight_fn: Callable[[int, int, dict], float]
    goal_lat: float = 0.0
    goal_lon: float = 0.0


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
