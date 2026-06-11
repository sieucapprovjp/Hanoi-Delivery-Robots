"""Module containing the concrete implementation of the four assignment/dispatch models.

All assignment models implement the AssignmentContract and follow the unified
input/output dataclass interfaces.
"""

import math
from typing import List, Dict
import networkx as nx
from scipy.optimize import linear_sum_assignment

from .base import AssignmentContract, AssignmentInput, AssignmentResult, AssignmentPair
from ..config import SPEED_METERS_PER_SECOND, BATTERY_DRAIN_RATE


def compute_battery_cost(graph: nx.MultiDiGraph, path: List[int]) -> float:
    """Computes the physical battery cost of traversing a path on the graph.

    BatteryCost(e) = Length(e) / v * r_drain. This is based on physical distance,
    independent of traffic multipliers.

    Args:
        graph (nx.MultiDiGraph): The road network graph.
        path (List[int]): List of node IDs representing the path.

    Returns:
        float: Estimated battery percentage depleted.
    """
    if not graph or len(path) < 2:
        return 0.0

    total_battery_cost = 0.0
    for u, v in zip(path[:-1], path[1:]):
        edge_data = graph.get_edge_data(u, v)
        if edge_data:
            if "length" in edge_data:
                edge_length = edge_data.get("length", 0.0)
            else:
                edge_length = min(
                    (data.get("length", 0.0) for data in edge_data.values()),
                    default=0.0,
                )
            battery_cost = (edge_length / SPEED_METERS_PER_SECOND) * BATTERY_DRAIN_RATE
            total_battery_cost += battery_cost
    return total_battery_cost


class NearestIdleAssignment(AssignmentContract[AssignmentInput, AssignmentResult]):
    """Nearest Idle dispatch model.

    Selects the idle robot nearest to the order's pickup point.
    """

    def execute(self, context: AssignmentInput) -> AssignmentResult:
        """Executes the Nearest Idle assignment model.

        Args:
            context (AssignmentInput): The input parameters for assignment.

        Returns:
            AssignmentResult: The list of assignments made.
        """
        assignments: List[AssignmentPair] = []
        available_robots = list(context.robots)

        for order in context.orders:
            if not available_robots:
                break

            pickup_node = context.nearest_node_fn(
                context.graph, order["pickup"]["lat"], order["pickup"]["lon"]
            )
            delivery_node = context.nearest_node_fn(
                context.graph, order["dropoff"]["lat"], order["dropoff"]["lon"]
            )

            # Check if delivery path is reachable
            try:
                dropoff_result = context.run_route_search_fn(
                    context.graph,
                    pickup_node,
                    delivery_node,
                    order["dropoff"]["lat"],
                    order["dropoff"]["lon"],
                    context.weight_fn,
                    "astar",
                )
                dropoff_path = dropoff_result.path
            except nx.NetworkXNoPath:
                continue

            best_robot = None
            best_cost = float("inf")
            best_pickup_path = None

            for robot in available_robots:
                robot_node = context.nearest_node_fn(
                    context.graph, robot.lat, robot.lon
                )
                try:
                    pickup_result = context.run_route_search_fn(
                        context.graph,
                        robot_node,
                        pickup_node,
                        order["pickup"]["lat"],
                        order["pickup"]["lon"],
                        context.weight_fn,
                        "astar",
                    )
                    cost = pickup_result.planned_cost
                    if cost < best_cost:
                        best_cost = cost
                        best_robot = robot
                        best_pickup_path = pickup_result.path
                except nx.NetworkXNoPath:
                    continue

            if best_robot and best_pickup_path:
                assignments.append(
                    AssignmentPair(
                        robot=best_robot,
                        order=order,
                        pickup_path=best_pickup_path,
                        dropoff_path=dropoff_path,
                        cost=best_cost,
                    )
                )
                available_robots.remove(best_robot)

        return AssignmentResult(assignments=assignments)


class NearestFeasibleAssignment(AssignmentContract[AssignmentInput, AssignmentResult]):
    """Nearest Feasible dispatch model.

    Selects the idle robot nearest to pickup with sufficient battery to complete
    the entire order (Robot -> Pickup -> Delivery).
    """

    def execute(self, context: AssignmentInput) -> AssignmentResult:
        """Executes the Nearest Feasible assignment model.

        Args:
            context (AssignmentInput): The input parameters for assignment.

        Returns:
            AssignmentResult: The list of assignments made.
        """
        assignments: List[AssignmentPair] = []
        available_robots = list(context.robots)

        for order in context.orders:
            if not available_robots:
                break

            pickup_node = context.nearest_node_fn(
                context.graph, order["pickup"]["lat"], order["pickup"]["lon"]
            )
            delivery_node = context.nearest_node_fn(
                context.graph, order["dropoff"]["lat"], order["dropoff"]["lon"]
            )

            try:
                dropoff_result = context.run_route_search_fn(
                    context.graph,
                    pickup_node,
                    delivery_node,
                    order["dropoff"]["lat"],
                    order["dropoff"]["lon"],
                    context.weight_fn,
                    "astar",
                )
                dropoff_path = dropoff_result.path
            except nx.NetworkXNoPath:
                continue

            best_robot = None
            best_cost = float("inf")
            best_pickup_path = None

            for robot in available_robots:
                robot_node = context.nearest_node_fn(
                    context.graph, robot.lat, robot.lon
                )
                try:
                    pickup_result = context.run_route_search_fn(
                        context.graph,
                        robot_node,
                        pickup_node,
                        order["pickup"]["lat"],
                        order["pickup"]["lon"],
                        context.weight_fn,
                        "astar",
                    )
                    pickup_path = pickup_result.path
                    cost = pickup_result.planned_cost

                    # Evaluate feasibility
                    battery_cost = compute_battery_cost(
                        context.graph, pickup_path
                    ) + compute_battery_cost(context.graph, dropoff_path)

                    if robot.battery >= battery_cost:
                        if cost < best_cost:
                            best_cost = cost
                            best_robot = robot
                            best_pickup_path = pickup_path
                except nx.NetworkXNoPath:
                    continue

            if best_robot and best_pickup_path:
                assignments.append(
                    AssignmentPair(
                        robot=best_robot,
                        order=order,
                        pickup_path=best_pickup_path,
                        dropoff_path=dropoff_path,
                        cost=best_cost,
                    )
                )
                available_robots.remove(best_robot)

        return AssignmentResult(assignments=assignments)


class WeightedCostAssignment(AssignmentContract[AssignmentInput, AssignmentResult]):
    """Weighted Cost Assignment dispatch model.

    Selects the robot minimizing the multi-objective cost:
    Cost = alpha * d(robot, pickup) + beta * d(pickup, delivery) + gamma * e^(-lambda * Battery)
    """

    def execute(self, context: AssignmentInput) -> AssignmentResult:
        """Executes the Weighted Cost Assignment model.

        Args:
            context (AssignmentInput): The input parameters for assignment.

        Returns:
            AssignmentResult: The list of assignments made.
        """
        assignments: List[AssignmentPair] = []
        available_robots = list(context.robots)

        for order in context.orders:
            if not available_robots:
                break

            pickup_node = context.nearest_node_fn(
                context.graph, order["pickup"]["lat"], order["pickup"]["lon"]
            )
            delivery_node = context.nearest_node_fn(
                context.graph, order["dropoff"]["lat"], order["dropoff"]["lon"]
            )

            try:
                dropoff_result = context.run_route_search_fn(
                    context.graph,
                    pickup_node,
                    delivery_node,
                    order["dropoff"]["lat"],
                    order["dropoff"]["lon"],
                    context.weight_fn,
                    "astar",
                )
                dropoff_path = dropoff_result.path
                dropoff_cost = dropoff_result.planned_cost
            except nx.NetworkXNoPath:
                continue

            best_robot = None
            best_total_cost = float("inf")
            best_pickup_path = None
            best_pickup_cost = 0.0

            for robot in available_robots:
                robot_node = context.nearest_node_fn(
                    context.graph, robot.lat, robot.lon
                )
                try:
                    pickup_result = context.run_route_search_fn(
                        context.graph,
                        robot_node,
                        pickup_node,
                        order["pickup"]["lat"],
                        order["pickup"]["lon"],
                        context.weight_fn,
                        "astar",
                    )
                    pickup_path = pickup_result.path
                    pickup_cost = pickup_result.planned_cost

                    # Calculate exponential battery penalty f(B) = e^(-lambda * B)
                    battery_penalty = math.exp(-context.val_lambda * robot.battery)

                    # Compute final combined cost
                    total_cost = (
                        context.alpha * pickup_cost
                        + context.beta * dropoff_cost
                        + context.gamma * battery_penalty
                    )

                    if total_cost < best_total_cost:
                        best_total_cost = total_cost
                        best_robot = robot
                        best_pickup_path = pickup_path
                        best_pickup_cost = pickup_cost
                except nx.NetworkXNoPath:
                    continue

            if best_robot and best_pickup_path:
                assignments.append(
                    AssignmentPair(
                        robot=best_robot,
                        order=order,
                        pickup_path=best_pickup_path,
                        dropoff_path=dropoff_path,
                        cost=best_pickup_cost,
                    )
                )
                available_robots.remove(best_robot)

        return AssignmentResult(assignments=assignments)


class HungarianAssignment(AssignmentContract[AssignmentInput, AssignmentResult]):
    """Hungarian Algorithm global matching model.

    Finds the globally optimal robot-to-order bipartite matching that minimizes
    the sum of Weighted Costs across all assignments.
    """

    def execute(self, context: AssignmentInput) -> AssignmentResult:
        """Executes the Hungarian Algorithm global matching model.

        Args:
            context (AssignmentInput): The input parameters for assignment.

        Returns:
            AssignmentResult: The list of assignments made.
        """
        robots = context.robots
        orders = context.orders

        if not robots or not orders:
            return AssignmentResult(assignments=[])

        num_robots = len(robots)
        num_orders = len(orders)

        # Precompute dropoff routes for all orders
        dropoff_info = []
        for order in orders:
            pickup_node = context.nearest_node_fn(
                context.graph, order["pickup"]["lat"], order["pickup"]["lon"]
            )
            delivery_node = context.nearest_node_fn(
                context.graph, order["dropoff"]["lat"], order["dropoff"]["lon"]
            )
            try:
                dropoff_result = context.run_route_search_fn(
                    context.graph,
                    pickup_node,
                    delivery_node,
                    order["dropoff"]["lat"],
                    order["dropoff"]["lon"],
                    context.weight_fn,
                    "astar",
                )
                dropoff_info.append(
                    (
                        dropoff_result.path,
                        dropoff_result.planned_cost,
                        pickup_node,
                    )
                )
            except nx.NetworkXNoPath:
                dropoff_info.append((None, float("inf"), pickup_node))

        # Build cost matrix and path cache
        cost_matrix = [[1e9 for _ in range(num_orders)] for _ in range(num_robots)]
        path_cache = {}

        for i, robot in enumerate(robots):
            robot_node = context.nearest_node_fn(context.graph, robot.lat, robot.lon)
            for j, order in enumerate(orders):
                dropoff_path, dropoff_cost, pickup_node = dropoff_info[j]
                if dropoff_path is None:
                    cost_matrix[i][j] = 1e9
                    continue

                try:
                    pickup_result = context.run_route_search_fn(
                        context.graph,
                        robot_node,
                        pickup_node,
                        order["pickup"]["lat"],
                        order["pickup"]["lon"],
                        context.weight_fn,
                        "astar",
                    )
                    pickup_path = pickup_result.path
                    pickup_cost = pickup_result.planned_cost

                    battery_penalty = math.exp(-context.val_lambda * robot.battery)
                    total_cost = (
                        context.alpha * pickup_cost
                        + context.beta * dropoff_cost
                        + context.gamma * battery_penalty
                    )

                    cost_matrix[i][j] = total_cost
                    path_cache[(i, j)] = (pickup_path, dropoff_path, pickup_cost)
                except nx.NetworkXNoPath:
                    cost_matrix[i][j] = 1e9

        # Run Kuhn-Munkres matching
        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        assignments: List[AssignmentPair] = []
        for r_idx, o_idx in zip(row_ind, col_ind):
            cost_val = cost_matrix[r_idx][o_idx]
            if cost_val < 1e8:  # Valid assignment, not a penalty
                pickup_path, dropoff_path, pickup_cost = path_cache[(r_idx, o_idx)]
                assignments.append(
                    AssignmentPair(
                        robot=robots[r_idx],
                        order=orders[o_idx],
                        pickup_path=pickup_path,
                        dropoff_path=dropoff_path,
                        cost=pickup_cost,
                    )
                )

        return AssignmentResult(assignments=assignments)


ASSIGNMENT_POLICIES: Dict[
    str, AssignmentContract[AssignmentInput, AssignmentResult]
] = {
    "nearest_idle": NearestIdleAssignment(),
    "nearest_feasible": NearestFeasibleAssignment(),
    "weighted_cost": WeightedCostAssignment(),
    "hungarian": HungarianAssignment(),
}


def run_assignment(
    policy_name: str,
    context: AssignmentInput,
) -> AssignmentResult:
    """Dispatches the assignment query to the selected AssignmentContract plugin.

    Args:
        policy_name (str): Identifier of the assignment policy to execute.
        context (AssignmentInput): The input parameters required for the assignment.

    Returns:
        AssignmentResult: The calculated assignment mapping of robots to orders.
    """
    policy: AssignmentContract[AssignmentInput, AssignmentResult] = (
        ASSIGNMENT_POLICIES.get(policy_name, ASSIGNMENT_POLICIES["nearest_idle"])
    )
    return policy.execute(context)
