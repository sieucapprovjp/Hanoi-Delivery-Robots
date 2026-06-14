import time
from dataclasses import replace
from typing import Any

from ...config import (
    DISPATCH_MAX_PICKUP_DISTANCE_METERS,
    DISPATCH_MIN_BATTERY_PERCENT,
    DISPATCH_MIN_PROJECTED_BATTERY_PERCENT,
    DISPATCH_REQUIRED_ROBOT_STATUS,
    VRP_ENABLED,
    VRP_MAX_ORDERS_PER_ROBOT,
)
from ...utils.geo import haversine_distance
from ..assignment import compute_battery_cost, run_assignment
from .vrp_solver import build_order_stops, precompute_distance_matrix, solve_vrp_sa


def _round(value, digits=1):
    if value is None:
        return None
    return round(value, digits)


def _robot_value(robot: Any, key: str, default=None):
    if isinstance(robot, dict):
        return robot.get(key, default)
    return getattr(robot, key, default)


def _robot_id(robot: Any):
    return _robot_value(robot, "robot_id", _robot_value(robot, "id"))


def _robot_name(robot: Any):
    return _robot_value(robot, "name", str(_robot_id(robot)))


def _robot_capacity(robot: Any):
    return _robot_value(robot, "capacity", VRP_MAX_ORDERS_PER_ROBOT)


def _robot_current_load(robot: Any):
    value = _robot_value(robot, "currentLoad")
    if value is not None:
        return value

    load = 0
    if _robot_value(robot, "current_task") is not None:
        load += 1
    task_queue = _robot_value(robot, "task_queue", [])
    try:
        load += len(task_queue)
    except TypeError:
        pass
    return load


def _point(payload: dict | None):
    payload = payload or {}
    return {
        "lat": float(payload.get("lat", 0.0)),
        "lon": float(payload.get("lon", 0.0)),
        "name": payload.get("name", ""),
        "category": payload.get("category"),
    }


def _order_id(order: dict):
    return order.get("id") or order.get("deliveryId")


def build_constraints_summary():
    return {
        "requiredStatus": DISPATCH_REQUIRED_ROBOT_STATUS,
        "minBatteryPercent": DISPATCH_MIN_BATTERY_PERCENT,
        "minProjectedBatteryPercent": DISPATCH_MIN_PROJECTED_BATTERY_PERCENT,
        "maxPickupDistanceMeters": DISPATCH_MAX_PICKUP_DISTANCE_METERS,
        "capacityRule": "capacity is unset or currentLoad < capacity",
        "routeReachabilityRule": "robot can route to pickup and pickup can route to dropoff",
        "batteryRule": "battery can complete route or a charging hub is available",
    }


def _constraint_result(checks: dict):
    return {
        "passed": all(check["passed"] for check in checks.values()),
        "checks": checks,
        "rejections": [
            {
                "code": check["code"],
                "message": check["message"],
                "details": check["details"],
            }
            for check in checks.values()
            if not check["passed"]
        ],
    }


def _constraint_flags(result: dict):
    return {key: check["passed"] for key, check in result["checks"].items()}


def _pre_route_constraints(robot: Any, pickup_distance_meters: float):
    status = _robot_value(robot, "status")
    battery = float(_robot_value(robot, "battery", 0.0) or 0.0)
    capacity = _robot_capacity(robot)
    current_load = _robot_current_load(robot)

    checks = {
        "idle": {
            "passed": status is None or status == DISPATCH_REQUIRED_ROBOT_STATUS,
            "code": "not_idle",
            "message": f"Robot status is {status}; expected idle.",
            "details": {
                "actualStatus": status,
                "requiredStatus": DISPATCH_REQUIRED_ROBOT_STATUS,
            },
        },
        "batteryKnown": {
            "passed": battery >= DISPATCH_MIN_BATTERY_PERCENT,
            "code": "battery_below_minimum",
            "message": (
                f"Battery {battery:.1f}% is below "
                f"{DISPATCH_MIN_BATTERY_PERCENT:.1f}% minimum."
            ),
            "details": {
                "battery": battery,
                "minBatteryPercent": DISPATCH_MIN_BATTERY_PERCENT,
            },
        },
        "capacityOk": {
            "passed": capacity is None or current_load < capacity,
            "code": "capacity_full",
            "message": f"Load {current_load}/{capacity} leaves no free capacity.",
            "details": {
                "currentLoad": current_load,
                "capacity": capacity,
            },
        },
        "pickupDistanceOk": {
            "passed": pickup_distance_meters <= DISPATCH_MAX_PICKUP_DISTANCE_METERS,
            "code": "pickup_too_far",
            "message": (
                f"Pickup distance {pickup_distance_meters:.0f}m exceeds "
                f"{DISPATCH_MAX_PICKUP_DISTANCE_METERS:.0f}m limit."
            ),
            "details": {
                "pickupDistanceMeters": pickup_distance_meters,
                "maxPickupDistanceMeters": DISPATCH_MAX_PICKUP_DISTANCE_METERS,
            },
        },
    }
    return _constraint_result(checks)


def _post_route_constraints(
    robot: Any,
    battery_cost: float,
    has_charging_hub: bool,
):
    battery = float(_robot_value(robot, "battery", 0.0) or 0.0)
    projected_battery = battery - battery_cost
    route_can_complete = projected_battery >= DISPATCH_MIN_PROJECTED_BATTERY_PERCENT
    checks = {
        "routeBatteryOk": {
            "passed": route_can_complete or has_charging_hub,
            "code": "battery_route_not_feasible",
            "message": (
                f"Projected battery {projected_battery:.1f}% is below "
                f"{DISPATCH_MIN_PROJECTED_BATTERY_PERCENT:.1f}% and no charging hub is available."
            ),
            "details": {
                "battery": battery,
                "batteryCost": battery_cost,
                "projectedBattery": projected_battery,
                "minProjectedBatteryPercent": DISPATCH_MIN_PROJECTED_BATTERY_PERCENT,
                "hasChargingHub": has_charging_hub,
                "requiresCharging": not route_can_complete and has_charging_hub,
            },
        },
    }
    return _constraint_result(checks)


def _build_explanation(order: dict, current_time: float, policy_name: str):
    pickup = _point(order.get("pickup"))
    dropoff = _point(order.get("dropoff") or order.get("destination"))
    order_id = _order_id(order)
    return {
        "cycleId": f"dispatch-{int(current_time)}-{order_id}",
        "timestamp": current_time,
        "orderId": order_id,
        "deliveryId": order_id,
        "pickupName": pickup.get("name", ""),
        "dropoffName": dropoff.get("name", ""),
        "policy": policy_name,
        "objective": f"apply CSP filters, then assign with {policy_name}",
        "constraints": build_constraints_summary(),
        "timeline": [
            {
                "stage": "candidate_scan",
                "status": "info",
                "message": f"Evaluating robots for order {order_id}.",
            }
        ],
        "candidates": [],
        "selectedRobotId": None,
        "selectedRobotName": None,
        "finalExplanation": None,
    }


def _candidate_base(robot: Any, pickup_distance_meters: float):
    return {
        "robotId": _robot_id(robot),
        "robotName": _robot_name(robot),
        "status": "candidate",
        "accepted": True,
        "battery": _round(float(_robot_value(robot, "battery", 0.0) or 0.0), 1),
        "currentLoad": _robot_current_load(robot),
        "capacity": _robot_capacity(robot),
        "pickupDistance": _round(pickup_distance_meters, 1),
        "constraints": {},
        "scores": {},
        "route": None,
        "reasons": [],
        "rejectReasons": [],
    }


def _reject_candidate(explanation: dict, candidate: dict, rejections: list, stage: str):
    candidate["status"] = "rejected"
    candidate["accepted"] = False
    candidate["reasons"] = rejections
    candidate["rejectReasons"] = rejections
    explanation["candidates"].append(candidate)
    explanation["timeline"].append(
        {
            "stage": stage,
            "status": "rejected",
            "robotId": candidate["robotId"],
            "message": (
                f"{candidate['robotName']} rejected: "
                f"{', '.join(item['code'] for item in rejections)}."
            ),
        }
    )


def _mark_no_selection(explanation: dict):
    explanation["finalExplanation"] = (
        f"No feasible robot for order {explanation['orderId']}."
    )
    explanation["timeline"].append(
        {
            "stage": "selection",
            "status": "rejected",
            "message": explanation["finalExplanation"],
        }
    )


def _mark_selection(explanation: dict, selected_robot: Any):
    selected_id = _robot_id(selected_robot)
    selected_name = _robot_name(selected_robot)
    explanation["selectedRobotId"] = selected_id
    explanation["selectedRobotName"] = selected_name
    explanation["finalExplanation"] = (
        f"Selected {selected_name} for order {explanation['orderId']} "
        f"after CSP filtering and {explanation['policy']} assignment."
    )

    for candidate in explanation["candidates"]:
        if candidate["robotId"] == selected_id:
            candidate["status"] = "selected"
            candidate["selected"] = True
            candidate["reasons"] = [
                {
                    "code": "selected_by_assignment_policy",
                    "message": "Selected by the active assignment policy after CSP filters.",
                }
            ]
        elif candidate.get("accepted"):
            candidate["status"] = "not_selected"
            candidate["selected"] = False
            candidate["reasons"] = [
                {
                    "code": "not_selected_by_assignment_policy",
                    "message": "Feasible, but not selected by the active assignment policy.",
                }
            ]

    explanation["timeline"].append(
        {
            "stage": "selection",
            "status": "selected",
            "robotId": selected_id,
            "message": explanation["finalExplanation"],
        }
    )


def _add_vrp_selection(explanation: dict, batch: list, vrp_result: dict):
    if len(batch) <= 1:
        return

    explanation["vrp"] = {
        "enabled": True,
        "orderIds": [_order_id(order) for order in batch],
        "orderCount": len(batch),
        "sequence": vrp_result["sequenceLabels"],
        "initialCost": _round(vrp_result["initialCost"], 1),
        "finalCost": _round(vrp_result["finalCost"], 1),
        "improvementRatio": _round(vrp_result["improvementRatio"], 4),
        "usedSimulatedAnnealing": vrp_result["usedSimulatedAnnealing"],
        "stats": vrp_result["stats"],
    }
    explanation["timeline"].append(
        {
            "stage": "vrp_batch",
            "status": "selected",
            "message": (
                f"Grouped {len(batch)} order(s) with sequence "
                f"{' -> '.join(vrp_result['sequenceLabels'])}."
            ),
        }
    )


def _candidate_route_context(context, robot: Any, order: dict):
    pickup = _point(order.get("pickup"))
    dropoff = _point(order.get("dropoff") or order.get("destination"))
    robot_node = context.nearest_node_fn(
        context.graph,
        float(_robot_value(robot, "lat", 0.0)),
        float(_robot_value(robot, "lon", 0.0)),
    )
    pickup_node = context.nearest_node_fn(context.graph, pickup["lat"], pickup["lon"])
    dropoff_node = context.nearest_node_fn(context.graph, dropoff["lat"], dropoff["lon"])

    pickup_result = context.run_route_search_fn(
        context.graph,
        robot_node,
        pickup_node,
        pickup["lat"],
        pickup["lon"],
        context.weight_fn,
        "astar",
    )
    dropoff_result = context.run_route_search_fn(
        context.graph,
        pickup_node,
        dropoff_node,
        dropoff["lat"],
        dropoff["lon"],
        context.weight_fn,
        "astar",
    )
    return pickup_result, dropoff_result


def _evaluate_candidate(context, app_state: dict | None, robot: Any, order: dict):
    pickup = _point(order.get("pickup"))
    pickup_distance = haversine_distance(
        float(_robot_value(robot, "lat", 0.0)),
        float(_robot_value(robot, "lon", 0.0)),
        pickup["lat"],
        pickup["lon"],
    )
    candidate = _candidate_base(robot, pickup_distance)
    pre_result = _pre_route_constraints(robot, pickup_distance)
    candidate["constraints"].update(_constraint_flags(pre_result))
    if not pre_result["passed"]:
        return candidate, pre_result["rejections"], None

    try:
        pickup_result, dropoff_result = _candidate_route_context(context, robot, order)
    except Exception:
        candidate["constraints"]["routeReachable"] = False
        reason = {
            "code": "route_unreachable",
            "message": "No viable route found from robot to pickup/dropoff.",
            "details": {},
        }
        return candidate, [reason], None

    candidate["constraints"]["routeReachable"] = True
    battery_cost = compute_battery_cost(
        context.graph, pickup_result.path
    ) + compute_battery_cost(context.graph, dropoff_result.path)
    has_charging_hub = bool((app_state or {}).get("charging_stations"))
    post_result = _post_route_constraints(robot, battery_cost, has_charging_hub)
    candidate["constraints"].update(_constraint_flags(post_result))

    total_route_cost = pickup_result.planned_cost + dropoff_result.planned_cost
    projected_battery = float(_robot_value(robot, "battery", 0.0) or 0.0) - battery_cost
    candidate["status"] = "scored"
    candidate["scores"] = {
        "pickupCost": _round(pickup_result.planned_cost, 1),
        "dropoffCost": _round(dropoff_result.planned_cost, 1),
        "totalRouteCost": _round(total_route_cost, 1),
        "batteryCost": _round(battery_cost, 2),
        "projectedBattery": _round(projected_battery, 1),
        "requiresCharging": projected_battery < DISPATCH_MIN_PROJECTED_BATTERY_PERCENT
        and has_charging_hub,
    }
    candidate["route"] = {
        "pickupPathLength": len(pickup_result.path),
        "dropoffPathLength": len(dropoff_result.path),
        "pickupPlannedCost": _round(pickup_result.planned_cost, 1),
        "dropoffPlannedCost": _round(dropoff_result.planned_cost, 1),
    }

    if not post_result["passed"]:
        return candidate, post_result["rejections"], None

    return candidate, [], robot


def _assignment_context_for_order(context, robots: list, order: dict):
    return replace(context, robots=robots, orders=[order])


def _remaining_capacity(robot: Any):
    capacity = _robot_capacity(robot)
    current_load = _robot_current_load(robot)
    if capacity is None:
        capacity = VRP_MAX_ORDERS_PER_ROBOT
    return max(1, min(VRP_MAX_ORDERS_PER_ROBOT, int(capacity) - int(current_load)))


def _vrp_cost_fn(from_point: dict, to_point: dict):
    return haversine_distance(
        from_point["lat"],
        from_point["lon"],
        to_point["lat"],
        to_point["lon"],
    )


def _build_vrp_batch(context, app_state: dict | None, selected_robot: Any, orders: list):
    if not VRP_ENABLED or not orders:
        return orders[:1], None

    max_orders = _remaining_capacity(selected_robot)
    batch = []

    for order in orders:
        if len(batch) >= max_orders:
            break
        candidate, rejections, eligible_robot = _evaluate_candidate(
            context, app_state, selected_robot, order
        )
        if rejections or eligible_robot is None:
            continue
        batch.append(order)

    if len(batch) <= 1:
        return batch[:1], None

    robot_pos = {
        "lat": float(_robot_value(selected_robot, "lat", 0.0)),
        "lon": float(_robot_value(selected_robot, "lon", 0.0)),
    }
    stops = build_order_stops(batch)
    distance_matrix = precompute_distance_matrix(robot_pos, stops, _vrp_cost_fn)
    vrp_result = solve_vrp_sa(robot_pos, batch, distance_matrix)
    return batch, vrp_result


def run_assignment_with_csp_xai(
    policy_name: str,
    context,
    app_state: dict | None = None,
    current_time: float | None = None,
):
    current_time = time.time() if current_time is None else current_time
    assignments = []
    explanations = []
    available_robots = list(context.robots)
    assigned_order_ids = set()

    for order in context.orders:
        if _order_id(order) in assigned_order_ids:
            continue

        explanation = _build_explanation(order, current_time, policy_name)
        eligible_robots = []

        for robot in available_robots:
            candidate, rejections, eligible_robot = _evaluate_candidate(
                context, app_state, robot, order
            )
            if rejections:
                _reject_candidate(explanation, candidate, rejections, "csp")
                continue

            explanation["candidates"].append(candidate)
            eligible_robots.append(eligible_robot)
            explanation["timeline"].append(
                {
                    "stage": "csp",
                    "status": "accepted",
                    "robotId": candidate["robotId"],
                    "message": f"{candidate['robotName']} passed CSP filters.",
                }
            )

        if not eligible_robots:
            _mark_no_selection(explanation)
            explanations.append(explanation)
            continue

        single_context = _assignment_context_for_order(context, eligible_robots, order)
        result = run_assignment(policy_name, single_context)
        if not result.assignments:
            _mark_no_selection(explanation)
            explanations.append(explanation)
            continue

        selected = result.assignments[0]

        candidate_orders = [
            candidate_order
            for candidate_order in context.orders
            if _order_id(candidate_order) not in assigned_order_ids
        ]
        batch, vrp_result = _build_vrp_batch(
            context, app_state, selected.robot, candidate_orders
        )
        if len(batch) > 1 and vrp_result:
            selected.order["vrp_batch_orders"] = batch
            selected.order["vrp_sequence"] = vrp_result["sequence"]
            selected.order["vrp_stats"] = vrp_result["stats"]
            selected.order["vrp_sequence_labels"] = vrp_result["sequenceLabels"]
            selected.order["vrp_cost"] = vrp_result["finalCost"]
            selected.order["vrp_initial_cost"] = vrp_result["initialCost"]
            selected.order["vrp_improvement_ratio"] = vrp_result["improvementRatio"]
            _add_vrp_selection(explanation, batch, vrp_result)
        else:
            batch = [selected.order]

        assignments.append(selected)
        assigned_order_ids.update(_order_id(batch_order) for batch_order in batch)
        available_robots = [
            robot for robot in available_robots if robot is not selected.robot
        ]
        _mark_selection(explanation, selected.robot)
        explanations.append(explanation)

    from ..base import AssignmentResult

    return AssignmentResult(assignments=assignments), explanations
