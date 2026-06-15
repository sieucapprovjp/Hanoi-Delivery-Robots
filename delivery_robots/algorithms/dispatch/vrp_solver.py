import math
import random

from ...config import (
    VRP_MIN_ORDERS_FOR_SA,
    VRP_SA_COOLING_RATE,
    VRP_SA_INITIAL_TEMP,
    VRP_SA_ITERATIONS_PER_TEMP,
    VRP_SA_MAX_ITERATIONS,
    VRP_SA_MIN_TEMP,
)
from ...utils.geo import haversine_distance


START_NODE_ID = "__start__"


def _delivery_id(order):
    for key in ("id", "deliveryId", "orderId"):
        if key in order:
            return order[key]
    return None


def _stop_key(stop):
    if isinstance(stop, str):
        return stop
    if stop.get("stopId"):
        return stop["stopId"]
    prefix = "P" if stop.get("type") == "pickup" else "D"
    return f"{prefix}{stop['deliveryId']}"


def _order_point(order, kind):
    if kind == "pickup":
        return order["pickup"]
    return order.get("dropoff") or order.get("destination")


def build_order_stops(orders):
    stops = []
    for order in orders:
        delivery_id = _delivery_id(order)
        pickup = _order_point(order, "pickup")
        dropoff = _order_point(order, "dropoff")

        stops.append(
            {
                "stopId": f"P{delivery_id}",
                "type": "pickup",
                "deliveryId": delivery_id,
                "lat": pickup["lat"],
                "lon": pickup["lon"],
                "name": pickup.get("name"),
                "category": pickup.get("category"),
            }
        )
        stops.append(
            {
                "stopId": f"D{delivery_id}",
                "type": "dropoff",
                "deliveryId": delivery_id,
                "lat": dropoff["lat"],
                "lon": dropoff["lon"],
                "name": dropoff.get("name"),
                "category": dropoff.get("category"),
            }
        )
    return stops


def check_precedence(sequence):
    picked_up = set()
    expected = {stop["deliveryId"] for stop in sequence if stop.get("type") == "pickup"}

    for stop in sequence:
        delivery_id = stop.get("deliveryId")
        if stop.get("type") == "pickup":
            if delivery_id in picked_up:
                return False
            picked_up.add(delivery_id)
        elif stop.get("type") == "dropoff":
            if delivery_id not in expected or delivery_id not in picked_up:
                return False
        else:
            return False

    return True


def _matrix_cost(distance_matrix, from_key, to_key):
    if from_key in distance_matrix and to_key in distance_matrix[from_key]:
        return distance_matrix[from_key][to_key]
    if (from_key, to_key) in distance_matrix:
        return distance_matrix[(from_key, to_key)]
    return math.inf


def sequence_cost(sequence, distance_matrix, start_key=START_NODE_ID):
    total = 0.0
    current_key = start_key

    for stop in sequence:
        next_key = _stop_key(stop)
        total += _matrix_cost(distance_matrix, current_key, next_key)
        current_key = next_key

    return total


def precompute_distance_matrix(robot_pos, stops, cost_fn=None):
    points = [{**robot_pos, "stopId": START_NODE_ID}, *stops]
    matrix = {point["stopId"]: {} for point in points}

    for from_point in points:
        for to_point in points:
            if from_point["stopId"] == to_point["stopId"]:
                matrix[from_point["stopId"]][to_point["stopId"]] = 0.0
                continue
            if cost_fn:
                cost = cost_fn(from_point, to_point)
            else:
                cost = haversine_distance(
                    from_point["lat"],
                    from_point["lon"],
                    to_point["lat"],
                    to_point["lon"],
                )
            matrix[from_point["stopId"]][to_point["stopId"]] = float(cost)

    return matrix


def greedy_initial_solution(robot_pos, orders, distance_matrix):
    remaining = build_order_stops(orders)
    sequence = []
    picked_up = set()
    current_key = START_NODE_ID

    while remaining:
        feasible = [
            stop
            for stop in remaining
            if stop["type"] == "pickup" or stop["deliveryId"] in picked_up
        ]
        if not feasible:
            break

        next_stop = min(
            feasible,
            key=lambda stop: _matrix_cost(distance_matrix, current_key, _stop_key(stop)),
        )
        sequence.append(next_stop)
        remaining.remove(next_stop)
        current_key = _stop_key(next_stop)
        if next_stop["type"] == "pickup":
            picked_up.add(next_stop["deliveryId"])

    return sequence


def _best_finite_sequence(orders, distance_matrix):
    stops = build_order_stops(orders)
    best_sequence = None
    best_cost = math.inf

    def visit(current_key, picked_up, remaining, sequence, total_cost):
        nonlocal best_sequence, best_cost

        if total_cost >= best_cost:
            return
        if not remaining:
            best_sequence = list(sequence)
            best_cost = total_cost
            return

        for index, stop in enumerate(remaining):
            delivery_id = stop["deliveryId"]
            if stop["type"] == "dropoff" and delivery_id not in picked_up:
                continue

            stop_key = _stop_key(stop)
            step_cost = _matrix_cost(distance_matrix, current_key, stop_key)
            if not math.isfinite(step_cost):
                continue

            next_remaining = remaining[:index] + remaining[index + 1 :]
            next_picked_up = set(picked_up)
            if stop["type"] == "pickup":
                next_picked_up.add(delivery_id)

            visit(
                stop_key,
                next_picked_up,
                next_remaining,
                [*sequence, stop],
                total_cost + step_cost,
            )

    visit(START_NODE_ID, set(), stops, [], 0.0)
    return best_sequence, best_cost


def _rng_or_default(rng):
    return rng or random


def swap_operator(sequence, rng=None, max_attempts=20):
    rng = _rng_or_default(rng)
    if len(sequence) < 2:
        return list(sequence)

    for _ in range(max_attempts):
        candidate = list(sequence)
        i, j = rng.sample(range(len(candidate)), 2)
        candidate[i], candidate[j] = candidate[j], candidate[i]
        if check_precedence(candidate):
            return candidate

    return list(sequence)


def relocate_operator(sequence, rng=None, max_attempts=20):
    rng = _rng_or_default(rng)
    if len(sequence) < 2:
        return list(sequence)

    for _ in range(max_attempts):
        candidate = list(sequence)
        from_idx, to_idx = rng.sample(range(len(candidate)), 2)
        stop = candidate.pop(from_idx)
        candidate.insert(to_idx, stop)
        if check_precedence(candidate):
            return candidate

    return list(sequence)


def two_opt_operator(sequence, rng=None, max_attempts=20):
    rng = _rng_or_default(rng)
    if len(sequence) < 4:
        return list(sequence)

    for _ in range(max_attempts):
        candidate = list(sequence)
        i, j = sorted(rng.sample(range(len(candidate)), 2))
        if i == j:
            continue
        candidate[i : j + 1] = reversed(candidate[i : j + 1])
        if check_precedence(candidate):
            return candidate

    return list(sequence)


def _sa_params(params):
    params = params or {}
    return {
        "initial_temp": params.get("initial_temp", VRP_SA_INITIAL_TEMP),
        "min_temp": params.get("min_temp", VRP_SA_MIN_TEMP),
        "cooling_rate": params.get("cooling_rate", VRP_SA_COOLING_RATE),
        "iterations_per_temp": params.get(
            "iterations_per_temp", VRP_SA_ITERATIONS_PER_TEMP
        ),
        "max_iterations": params.get("max_iterations", VRP_SA_MAX_ITERATIONS),
        "min_orders_for_sa": params.get("min_orders_for_sa", VRP_MIN_ORDERS_FOR_SA),
    }


def _serialize_sequence(sequence):
    return [
        {
            "stopId": _stop_key(stop),
            "type": stop["type"],
            "deliveryId": stop["deliveryId"],
            "lat": stop["lat"],
            "lon": stop["lon"],
            "name": stop.get("name"),
            "category": stop.get("category"),
        }
        for stop in sequence
    ]


def _result(sequence, initial_cost, best_cost, stats, used_sa):
    improvement = 0.0
    if math.isfinite(initial_cost) and initial_cost > 0 and math.isfinite(best_cost):
        improvement = max(0.0, (initial_cost - best_cost) / initial_cost)

    return {
        "sequence": _serialize_sequence(sequence),
        "sequenceLabels": [_stop_key(stop) for stop in sequence],
        "initialCost": initial_cost,
        "finalCost": best_cost,
        "cost": best_cost,
        "improvementRatio": improvement,
        "usedSimulatedAnnealing": used_sa,
        "stats": stats,
    }


def solve_vrp_sa(robot_pos, orders, distance_matrix=None, params=None, rng=None):
    params = _sa_params(params)
    rng = _rng_or_default(rng)
    stops = build_order_stops(orders)
    if distance_matrix is None:
        distance_matrix = precompute_distance_matrix(robot_pos, stops)

    current = greedy_initial_solution(robot_pos, orders, distance_matrix)
    if not check_precedence(current):
        raise ValueError("Initial VRP sequence violates pickup-before-dropoff.")

    current_cost = sequence_cost(current, distance_matrix)
    repaired_initial_sequence = False
    if not math.isfinite(current_cost):
        finite_sequence, finite_cost = _best_finite_sequence(orders, distance_matrix)
        if finite_sequence is not None:
            current = finite_sequence
            current_cost = finite_cost
            repaired_initial_sequence = True

    best = list(current)
    best_cost = current_cost
    initial_cost = current_cost

    stats = {
        "iterations": 0,
        "acceptedMoves": 0,
        "improvements": 0,
        "finalTemp": params["initial_temp"],
        "repairedInitialSequence": repaired_initial_sequence,
    }

    if len(orders) < params["min_orders_for_sa"]:
        return _result(best, initial_cost, best_cost, stats, used_sa=False)

    operators = [swap_operator, relocate_operator, two_opt_operator]
    temperature = params["initial_temp"]

    while (
        temperature > params["min_temp"]
        and stats["iterations"] < params["max_iterations"]
    ):
        for _ in range(params["iterations_per_temp"]):
            if stats["iterations"] >= params["max_iterations"]:
                break

            stats["iterations"] += 1
            operator = rng.choice(operators)
            candidate = operator(current, rng)
            candidate_cost = sequence_cost(candidate, distance_matrix)
            delta = candidate_cost - current_cost

            if delta <= 0 or rng.random() < math.exp(-delta / temperature):
                current = candidate
                current_cost = candidate_cost
                stats["acceptedMoves"] += 1

                if current_cost < best_cost:
                    best = list(current)
                    best_cost = current_cost
                    stats["improvements"] += 1

        temperature *= params["cooling_rate"]
        stats["finalTemp"] = temperature

    return _result(best, initial_cost, best_cost, stats, used_sa=True)
