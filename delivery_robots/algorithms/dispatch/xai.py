from ...config import (
    DISPATCH_BATTERY_RISK_WEIGHT,
    DISPATCH_PRIORITY_WEIGHT,
)
from .constraints import build_constraints_summary, evaluate_pre_route_constraints


def _round(value, digits=1):
    if value is None:
        return None
    return round(value, digits)


def build_candidate_constraints(robot, pickup_distance_meters):
    result = evaluate_pre_route_constraints(robot, pickup_distance_meters)
    return {
        key: check["passed"]
        for key, check in result["checks"].items()
    }


def constraint_rejections(robot, pickup_distance_meters):
    return evaluate_pre_route_constraints(robot, pickup_distance_meters)["rejections"]


def build_candidate_record(robot, pickup_distance_meters, approximate_score):
    approximate_score = _round(approximate_score, 1)
    return {
        "robotId": robot.get("id"),
        "robotName": robot.get("name", ""),
        "status": "candidate",
        "accepted": True,
        "battery": _round(robot.get("battery", 0), 1),
        "currentLoad": robot.get("currentLoad", 0),
        "capacity": robot.get("capacity"),
        "pickupDistance": _round(pickup_distance_meters, 1),
        "approximateScore": approximate_score,
        "constraints": build_candidate_constraints(robot, pickup_distance_meters),
        "scores": {
            "approximateScore": approximate_score,
        },
        "route": None,
        "reasons": [],
        "rejectReasons": [],
    }


def build_dispatch_explanation(delivery, current_time_ms):
    delivery_id = delivery["id"]
    priority_score = _round(delivery["priorityScore"], 2)
    return {
        "cycleId": f"dispatch-{int(current_time_ms)}-{delivery_id}",
        "timestamp": current_time_ms,
        "orderId": delivery_id,
        "deliveryId": delivery_id,
        "pickupName": delivery["pickup"].get("name", ""),
        "destinationName": delivery["destination"].get("name", ""),
        "priorityScore": priority_score,
        "objective": "minimize routeCost + batteryRisk*wBattery - priority*wPriority",
        "constraints": build_constraints_summary(),
        "timeline": [
            {
                "stage": "priority",
                "status": "info",
                "message": f"Order #{delivery_id} priority = {delivery['priorityScore']:.1f}.",
            }
        ],
        "candidates": [],
        "selectedRobotId": None,
        "selectedRobotName": None,
        "finalExplanation": None,
    }


def add_timeline_step(explanation, stage, status, message, robot_id=None):
    step = {
        "stage": stage,
        "status": status,
        "message": message,
    }
    if robot_id is not None:
        step["robotId"] = robot_id
    explanation["timeline"].append(step)


def reject_candidate(explanation, candidate, robot, rejections, stage="csp"):
    candidate["status"] = "rejected"
    candidate["accepted"] = False
    candidate["reasons"] = rejections
    candidate["rejectReasons"] = rejections
    explanation["candidates"].append(candidate)
    add_timeline_step(
        explanation,
        stage,
        "rejected",
        (
            f"{robot.get('name', robot.get('id'))} rejected by CSP: "
            f"{', '.join(item['code'] for item in rejections)}."
        ),
        robot.get("id"),
    )


def mark_candidate_pruned(candidate, limit):
    reason = {
        "code": "outside_top_k_prescore",
        "message": (
            f"Not routed because only top {limit} feasible robots are expanded."
        ),
    }
    candidate["status"] = "pruned"
    candidate["reasons"] = [reason]


def add_candidate_pruning_step(explanation, feasible_count, routed_count):
    add_timeline_step(
        explanation,
        "candidate_pruning",
        "info",
        (
            f"{feasible_count} feasible robot(s); routing "
            f"{routed_count} after heuristic pre-score."
        ),
    )


def mark_candidate_scored(
    candidate,
    total_cost,
    battery_risk,
    total_score,
    algorithm,
    priority_score,
    route_payload,
):
    route_breakdown = route_payload.get("costBreakdown", {})
    candidate["status"] = "scored"
    candidate["routeCost"] = _round(total_cost, 1)
    candidate["batteryRisk"] = _round(battery_risk, 2)
    candidate["totalScore"] = _round(total_score, 2)
    candidate["algo"] = algorithm
    candidate["formula"] = (
        f"{total_cost:.1f} + {battery_risk:.2f}*"
        f"{DISPATCH_BATTERY_RISK_WEIGHT} - "
        f"{priority_score:.1f}*{DISPATCH_PRIORITY_WEIGHT}"
    )
    candidate["scores"].update(
        {
            "routeCost": _round(total_cost, 1),
            "batteryRisk": _round(battery_risk, 2),
            "priorityScore": _round(priority_score, 2),
            "totalScore": _round(total_score, 2),
        }
    )
    candidate["route"] = {
        "distance": _round(route_payload.get("distance", 0.0), 1),
        "etaMinutes": route_breakdown.get("estimatedMinutes"),
        "algorithm": algorithm,
        "nodesExplored": route_payload.get("nodesExplored"),
        "timeMs": route_payload.get("timeMs"),
        "pathCost": route_payload.get("pathCost"),
    }


def add_scoring_step(explanation, robot, total_score, algorithm, total_cost):
    add_timeline_step(
        explanation,
        "scoring",
        "info",
        (
            f"{robot.get('name', robot.get('id'))}: score "
            f"{total_score:.1f} using {algorithm.upper()} route cost "
            f"{total_cost:.1f}m."
        ),
        robot.get("id"),
    )


def mark_route_failure(explanation, candidate, robot):
    reason = {
        "code": "route_failed",
        "message": "No viable route found for this robot.",
    }
    candidate["status"] = "rejected"
    candidate["accepted"] = False
    candidate["reasons"] = [reason]
    candidate["rejectReasons"] = [reason]
    add_timeline_step(
        explanation,
        "routing",
        "rejected",
        f"{robot.get('name', robot.get('id'))} rejected: route search failed.",
        robot.get("id"),
    )


def mark_selection(explanation, best, delivery, routed_robot_ids):
    explanation["selectedRobotId"] = best["robotId"]
    explanation["selectedRobotName"] = best["robotName"]
    explanation["finalExplanation"] = (
        f"Selected {best['robotName']} for order #{delivery['id']} "
        f"because it had the lowest total score ({best['totalScore']:.1f})."
    )

    for candidate in explanation["candidates"]:
        if candidate["robotId"] == best["robotId"]:
            candidate["status"] = "selected"
            candidate["selected"] = True
            candidate["reasons"] = [
                {
                    "code": "lowest_total_score",
                    "message": "Selected because it has the lowest final score.",
                }
            ]
        elif candidate["robotId"] in routed_robot_ids and candidate["status"] == "scored":
            candidate["status"] = "not_selected"
            candidate["selected"] = False
            candidate["reasons"] = [
                {
                    "code": "higher_total_score",
                    "message": "Feasible, but score is higher than selected robot.",
                }
            ]

    add_timeline_step(
        explanation,
        "selection",
        "selected",
        (
            f"Selected {best['robotName']} for order #{delivery['id']} "
            f"with score {best['totalScore']:.1f}."
        ),
        best["robotId"],
    )


def mark_no_selection(explanation, delivery):
    explanation["finalExplanation"] = f"No feasible robot for order #{delivery['id']}."
    add_timeline_step(
        explanation,
        "selection",
        "rejected",
        f"No feasible robot for order #{delivery['id']}.",
    )
