import math
import time

from ...algorithms.weighted_search import run_weighted_route_search
from ...config import (
    DISPATCH_BATTERY_DRAIN_PER_KM,
    DISPATCH_BATTERY_RISK_WEIGHT,
    DISPATCH_BATTERY_SAFETY_MARGIN,
    DISPATCH_DEFAULT_CATEGORY_WEIGHT,
    DISPATCH_DROPOFF_CATEGORY_WEIGHTS,
    ESTIMATED_SPEED_METERS_PER_MINUTE,
    DISPATCH_HIGH_PRIORITY_EXTRA_CANDIDATES,
    DISPATCH_HIGH_PRIORITY_SCORE_THRESHOLD,
    DISPATCH_PICKUP_CATEGORY_WEIGHTS,
    DISPATCH_WAIT_MINUTES_WEIGHT,
    DEFAULT_ROAD_MEMORY_PENALTY,
    DEFAULT_ROUTING_ALGORITHM,
    DISPATCH_MAX_ROUTE_CANDIDATES_PER_DELIVERY,
    DISPATCH_PRIORITY_WEIGHT,
    ROUTING_ALGORITHM_ALIASES,
    SECONDS_PER_MINUTE,
    TIMESTAMP_MS_MULTIPLIER,
    VALID_ROUTING_ALGORITHMS,
    VRP_ENABLED,
    VRP_MAX_ORDERS_PER_ROBOT,
)
from ...algorithms.dispatch.xai import (
    add_candidate_pruning_step,
    add_scoring_step,
    add_timeline_step,
    apply_constraint_result,
    build_candidate_record,
    build_dispatch_explanation,
    constraint_rejections,
    mark_candidate_pruned,
    mark_candidate_scored,
    mark_no_selection,
    mark_post_route_constraint_failure,
    mark_route_failure,
    mark_selection,
    reject_candidate,
)
from ...algorithms.dispatch.vrp_solver import (
    START_NODE_ID,
    build_order_stops,
    solve_vrp_sa,
)
from .constraints import evaluate_post_route_constraints
from ...utils.geo import haversine_distance
from ...utils.persistent_log import append_app_event
from ...utils.route_analysis import (
    attach_route_metadata,
    build_memory_weight_fn,
    build_route_response,
)


def calculate_priority_score(delivery, current_time_ms):
    created_at = delivery.get('createdAt') or current_time_ms
    wait_minutes = max(0, current_time_ms - created_at) / (
        SECONDS_PER_MINUTE * TIMESTAMP_MS_MULTIPLIER
    )
    theme = delivery.get('theme', {})
    pickup_cat = theme.get('pickupCategory')
    drop_cat = theme.get('dropoffCategory')
    
    p_weight = DISPATCH_PICKUP_CATEGORY_WEIGHTS.get(
        pickup_cat, DISPATCH_DEFAULT_CATEGORY_WEIGHT
    )
    d_weight = DISPATCH_DROPOFF_CATEGORY_WEIGHTS.get(
        drop_cat, DISPATCH_DEFAULT_CATEGORY_WEIGHT
    )
    return p_weight + d_weight + wait_minutes * DISPATCH_WAIT_MINUTES_WEIGHT


def _normalize_route_algorithm(algorithm):
    normalized = (algorithm or DEFAULT_ROUTING_ALGORITHM).strip().lower()
    normalized = ROUTING_ALGORITHM_ALIASES.get(normalized, normalized)
    if normalized not in VALID_ROUTING_ALGORITHMS:
        return DEFAULT_ROUTING_ALGORITHM
    return normalized


def _approximate_robot_score(robot, distance):
    projected_drain = (distance / 1000.0) * DISPATCH_BATTERY_DRAIN_PER_KM
    battery_risk = max(
        0,
        projected_drain
        - robot.get('battery', 0) * DISPATCH_BATTERY_SAFETY_MARGIN,
    )
    return distance + battery_risk * DISPATCH_BATTERY_RISK_WEIGHT


def _candidate_limit(delivery, ranked_count):
    extra_candidates = (
        DISPATCH_HIGH_PRIORITY_EXTRA_CANDIDATES
        if delivery['priorityScore'] >= DISPATCH_HIGH_PRIORITY_SCORE_THRESHOLD
        else 0
    )
    return max(
        1,
        min(
            ranked_count,
            DISPATCH_MAX_ROUTE_CANDIDATES_PER_DELIVERY + extra_candidates,
        ),
    )


def _rank_feasible_candidates(delivery, available_robots, explanation):
    pickup_lat = delivery['pickup']['lat']
    pickup_lon = delivery['pickup']['lon']
    feasible_candidates = []

    for robot in available_robots:
        pickup_distance = haversine_distance(
            robot['lat'], robot['lon'], pickup_lat, pickup_lon
        )
        approx_score = _approximate_robot_score(robot, pickup_distance)
        candidate = build_candidate_record(robot, pickup_distance, approx_score)
        rejections = constraint_rejections(robot, pickup_distance)
        if rejections:
            reject_candidate(explanation, candidate, robot, rejections)
            continue

        explanation["candidates"].append(candidate)
        feasible_candidates.append((robot, candidate))

    return sorted(feasible_candidates, key=lambda item: item[1]["approximateScore"])


def _delivery_id(delivery):
    return delivery.get("id")


def _max_vrp_orders_for_robot(robot):
    capacity = robot.get("capacity")
    current_load = robot.get("currentLoad", 0)
    max_orders = VRP_MAX_ORDERS_PER_ROBOT
    if capacity is not None:
        max_orders = min(max_orders, max(0, capacity - current_load))
    return max(1, max_orders)


def _select_vrp_batch(
    first_delivery,
    deliveries,
    assigned_delivery_ids,
    robot,
    remaining_robot_count,
):
    if not VRP_ENABLED:
        return [first_delivery]

    max_orders = _max_vrp_orders_for_robot(robot)
    if max_orders <= 1:
        return [first_delivery]

    unassigned = [
        delivery
        for delivery in deliveries
        if _delivery_id(delivery) not in assigned_delivery_ids
        and _delivery_id(delivery) != _delivery_id(first_delivery)
    ]
    overflow_count = max(0, len(unassigned) - max(0, remaining_robot_count - 1))
    if overflow_count <= 0:
        return [first_delivery]

    batch = [first_delivery]
    for delivery in unassigned:
        if len(batch) >= max_orders:
            break
        batch.append(delivery)
        if len(batch) - 1 >= overflow_count:
            break

    return batch


def _point_node(graph, point, nearest_node_id_fn, app_state):
    return nearest_node_id_fn(graph, point["lat"], point["lon"], app_state["ox"])


def _route_between_points(
    graph,
    from_point,
    to_point,
    nearest_node_id_fn,
    app_state,
    weight_fn,
    algo,
    traffic_penalty_fn,
    rain_penalty_fn,
    obstacle_penalty_fn,
):
    start_t = time.time()
    start_node = _point_node(graph, from_point, nearest_node_id_fn, app_state)
    end_node = _point_node(graph, to_point, nearest_node_id_fn, app_state)
    route_nodes, nodes_explored = run_weighted_route_search(
        graph,
        start_node,
        end_node,
        to_point["lat"],
        to_point["lon"],
        weight_fn,
        algo,
    )
    calc_time = (time.time() - start_t) * TIMESTAMP_MS_MULTIPLIER
    route_payload = build_route_response(
        graph,
        route_nodes,
        traffic_penalty_fn,
        rain_penalty_fn,
        obstacle_penalty_fn,
    )
    attach_route_metadata(
        route_payload,
        graph,
        start_node,
        end_node,
        algo,
        calc_time,
        nodes_explored,
    )
    return route_payload


def _build_vrp_distance_matrix(
    graph,
    robot,
    stops,
    nearest_node_id_fn,
    app_state,
    weight_fn,
    algo,
    traffic_penalty_fn,
    rain_penalty_fn,
    obstacle_penalty_fn,
):
    start_point = {
        "stopId": START_NODE_ID,
        "lat": robot["lat"],
        "lon": robot["lon"],
    }
    points = [start_point, *stops]
    matrix = {point["stopId"]: {} for point in points}
    route_cache = {}

    for from_point in points:
        for to_point in points:
            from_key = from_point["stopId"]
            to_key = to_point["stopId"]
            if from_key == to_key:
                matrix[from_key][to_key] = 0.0
                continue
            try:
                route_payload = _route_between_points(
                    graph,
                    from_point,
                    to_point,
                    nearest_node_id_fn,
                    app_state,
                    weight_fn,
                    algo,
                    traffic_penalty_fn,
                    rain_penalty_fn,
                    obstacle_penalty_fn,
                )
            except Exception:
                matrix[from_key][to_key] = math.inf
                continue

            route_cache[(from_key, to_key)] = route_payload
            breakdown = route_payload.get("costBreakdown", {})
            matrix[from_key][to_key] = breakdown.get(
                "totalCost", route_payload.get("distance", 0.0)
            )

    return matrix, route_cache


def _batch_breakdown(total_cost):
    return {
        "baseDistance": round(total_cost, 1),
        "trafficPenalty": 0.0,
        "rainPenalty": 0.0,
        "obstaclePenalty": 0.0,
        "totalCost": round(total_cost, 1),
        "estimatedMinutes": round(total_cost / ESTIMATED_SPEED_METERS_PER_MINUTE, 1),
    }


def _safe_log_vrp_result(payload):
    try:
        append_app_event({"type": "vrp_result", **payload})
    except Exception:
        pass


def _build_vrp_explanation_payload(best, batch, vrp_result):
    return {
        "deliveryIds": best["deliveryIds"],
        "orderCount": len(batch),
        "sequence": vrp_result["sequenceLabels"],
        "initialCost": round(vrp_result["initialCost"], 1),
        "finalCost": best["vrpCost"],
        "improvementRatio": best["vrpImprovementRatio"],
        "usedSimulatedAnnealing": vrp_result["usedSimulatedAnnealing"],
        "stats": vrp_result["stats"],
    }


def _apply_vrp_batch_to_assignment(
    best,
    robot,
    batch,
    graph,
    nearest_node_id_fn,
    app_state,
    weight_fn,
    algo,
    traffic_penalty_fn,
    rain_penalty_fn,
    obstacle_penalty_fn,
    explanation,
):
    if len(batch) <= 1:
        best["deliveryIds"] = [best["deliveryId"]]
        best["orderSequence"] = build_order_stops(batch)
        return best

    stops = build_order_stops(batch)
    distance_matrix, route_cache = _build_vrp_distance_matrix(
        graph,
        robot,
        stops,
        nearest_node_id_fn,
        app_state,
        weight_fn,
        algo,
        traffic_penalty_fn,
        rain_penalty_fn,
        obstacle_penalty_fn,
    )
    vrp_result = solve_vrp_sa(
        {"lat": robot["lat"], "lon": robot["lon"]},
        batch,
        distance_matrix,
    )
    first_stop = vrp_result["sequence"][0]
    batch_cost = vrp_result["finalCost"]
    if not math.isfinite(batch_cost):
        raise ValueError("No finite VRP route sequence found.")

    first_route = route_cache.get((START_NODE_ID, first_stop["stopId"]))
    if not first_route:
        raise ValueError("No route to first VRP stop.")

    batch_priority = sum(delivery["priorityScore"] for delivery in batch)
    batch_battery_risk = max(
        0,
        (batch_cost / 1000.0) * DISPATCH_BATTERY_DRAIN_PER_KM
        - robot.get("battery", 0) * DISPATCH_BATTERY_SAFETY_MARGIN,
    )
    batch_eta_minutes = batch_cost / ESTIMATED_SPEED_METERS_PER_MINUTE
    batch_constraints = evaluate_post_route_constraints(
        robot,
        batch_cost,
        batch_eta_minutes / len(batch),
    )
    if not batch_constraints["passed"]:
        best["deliveryIds"] = [best["deliveryId"]]
        best["orderSequence"] = build_order_stops([batch[0]])
        add_timeline_step(
            explanation,
            "vrp_batch",
            "rejected",
            (
                f"VRP batch rejected for {robot.get('name', robot.get('id'))}: "
                f"{', '.join(item['code'] for item in batch_constraints['rejections'])}."
            ),
            robot.get("id"),
        )
        return best

    best["deliveryIds"] = [_delivery_id(delivery) for delivery in batch]
    best["orderSequence"] = vrp_result["sequence"]
    best["routeSequence"] = vrp_result["sequence"]
    best["vrpStats"] = vrp_result["stats"]
    best["vrpCost"] = round(batch_cost, 1)
    best["vrpInitialCost"] = round(vrp_result["initialCost"], 1)
    best["vrpImprovementRatio"] = round(vrp_result["improvementRatio"], 4)
    best["vrpBreakdown"] = _batch_breakdown(batch_cost)
    best["route"] = first_route
    best["breakdown"] = first_route.get("costBreakdown", {})
    best["batteryRisk"] = batch_battery_risk
    best["totalScore"] = (
        batch_cost
        + batch_battery_risk * DISPATCH_BATTERY_RISK_WEIGHT
        - batch_priority * DISPATCH_PRIORITY_WEIGHT
    )
    best["priorityScore"] = batch_priority
    explanation["vrp"] = _build_vrp_explanation_payload(best, batch, vrp_result)

    labels = " -> ".join(vrp_result["sequenceLabels"])
    improvement_pct = vrp_result["improvementRatio"] * 100
    add_timeline_step(
        explanation,
        "vrp_sequence",
        "selected",
        (
            f"VRP assigned {len(batch)} order(s) to "
            f"{robot.get('name', robot.get('id'))}: {labels}; "
            f"cost {vrp_result['initialCost']:.1f}m -> {batch_cost:.1f}m "
            f"({improvement_pct:.1f}% better)."
        ),
        robot.get("id"),
    )
    _safe_log_vrp_result(
        {
            "robotId": robot.get("id"),
            "robotName": robot.get("name", ""),
            "deliveryIds": best["deliveryIds"],
            "sequence": vrp_result["sequenceLabels"],
            "initialCost": round(vrp_result["initialCost"], 1),
            "finalCost": round(batch_cost, 1),
            "improvementRatio": round(vrp_result["improvementRatio"], 4),
            "stats": vrp_result["stats"],
        }
    )
    return best


def assign_deliveries(
    app_state, graph, robots, deliveries, current_time_ms,
    nearest_node_id_fn, edge_weight_with_traffic_fn, 
    traffic_penalty_fn, rain_penalty_fn, obstacle_penalty_fn,
    record_route_metrics_fn, metrics, return_explanations=False
):
    base_weight_cache = {}
    memory_key_cache = {}
    robot_node_cache = {}
    pickup_node_cache = {}

    def cached_base_weight(from_node, to_node, edge_data):
        key = (from_node, to_node)
        if key not in base_weight_cache:
            base_weight_cache[key] = edge_weight_with_traffic_fn(
                from_node, to_node, edge_data
            )
        return base_weight_cache[key]

    def cached_robot_node(robot):
        key = (robot.get('id'), robot['lat'], robot['lon'])
        if key not in robot_node_cache:
            robot_node_cache[key] = nearest_node_id_fn(
                graph, robot['lat'], robot['lon'], app_state["ox"]
            )
        return robot_node_cache[key]

    def cached_pickup_node(delivery):
        pickup = delivery['pickup']
        key = (delivery.get('id'), pickup['lat'], pickup['lon'])
        if key not in pickup_node_cache:
            pickup_node_cache[key] = nearest_node_id_fn(
                graph, pickup['lat'], pickup['lon'], app_state["ox"]
            )
        return pickup_node_cache[key]

    for d in deliveries:
        d['priorityScore'] = calculate_priority_score(d, current_time_ms)
        
    deliveries.sort(key=lambda x: x['priorityScore'], reverse=True)
    
    assignments = []
    explanations = []
    available_robots = list(robots)
    assigned_delivery_ids = set()
    
    for delivery in deliveries:
        if _delivery_id(delivery) in assigned_delivery_ids:
            continue
        if not available_robots:
            break
            
        best = None
        pickup_lat = delivery['pickup']['lat']
        pickup_lon = delivery['pickup']['lon']
        end_node = cached_pickup_node(delivery)
        explanation = build_dispatch_explanation(delivery, current_time_ms)
        ranked_candidates = _rank_feasible_candidates(
            delivery, available_robots, explanation
        )
        limit = _candidate_limit(delivery, len(ranked_candidates))
        routed_candidates = ranked_candidates[:limit]
        routed_robot_ids = {robot.get('id') for robot, _ in routed_candidates}

        for robot, candidate in ranked_candidates[limit:]:
            mark_candidate_pruned(candidate, limit)

        add_candidate_pruning_step(
            explanation, len(ranked_candidates), len(routed_candidates)
        )
        
        for robot, candidate in routed_candidates:
            try:
                start_node = cached_robot_node(robot)
                road_memory = robot.get('roadMemory', {})
                algo = _normalize_route_algorithm(robot.get('routeAlgorithm'))
                weight_fn = build_memory_weight_fn(
                    graph,
                    cached_base_weight,
                    road_memory,
                    DEFAULT_ROAD_MEMORY_PENALTY,
                    memory_key_cache,
                )
                
                start_t = time.time()
                route_nodes, nodes_explored = run_weighted_route_search(
                    graph, start_node, end_node, pickup_lat, pickup_lon, weight_fn, algo
                )
                calc_time = (time.time() - start_t) * 1000
                
                route_payload = build_route_response(
                    graph, route_nodes, traffic_penalty_fn, rain_penalty_fn, obstacle_penalty_fn
                )
                attach_route_metadata(
                    route_payload,
                    graph,
                    start_node,
                    end_node,
                    algo,
                    calc_time,
                    nodes_explored,
                )
                breakdown = route_payload.get("costBreakdown", {})
                total_cost = breakdown.get("totalCost", route_payload.get("distance", 0.0))
                
                record_route_metrics_fn(metrics, calc_time, nodes_explored, len(route_nodes))
                
                projected_drain = (total_cost / 1000.0) * DISPATCH_BATTERY_DRAIN_PER_KM
                battery_risk = max(
                    0,
                    projected_drain
                    - robot.get('battery', 0) * DISPATCH_BATTERY_SAFETY_MARGIN,
                )
                
                total_score = (
                    total_cost
                    + battery_risk * DISPATCH_BATTERY_RISK_WEIGHT
                    - delivery['priorityScore'] * DISPATCH_PRIORITY_WEIGHT
                )
                post_route_constraints = evaluate_post_route_constraints(
                    robot, total_cost, breakdown.get("estimatedMinutes")
                )
                mark_candidate_scored(
                    candidate,
                    total_cost,
                    battery_risk,
                    total_score,
                    algo,
                    delivery['priorityScore'],
                    route_payload,
                )
                apply_constraint_result(candidate, post_route_constraints)
                if not post_route_constraints["passed"]:
                    mark_post_route_constraint_failure(
                        explanation,
                        candidate,
                        robot,
                        post_route_constraints["rejections"],
                    )
                    continue

                add_scoring_step(
                    explanation, robot, total_score, algo, total_cost
                )
                
                if best is None or total_score < best['totalScore']:
                    best = {
                        "robotId": robot['id'],
                        "robotName": robot.get('name', ''),
                        "deliveryId": delivery['id'],
                        "priorityScore": delivery['priorityScore'],
                        "batteryRisk": battery_risk,
                        "totalScore": total_score,
                        "breakdown": breakdown,
                        "pickupName": delivery['pickup'].get('name', ''),
                        "destinationName": delivery['destination'].get('name', ''),
                        "route": route_payload,
                        "_robot": robot,
                        "_weightFn": weight_fn,
                        "_algo": algo,
                    }
            except Exception:
                mark_route_failure(explanation, candidate, robot)
                
        if best:
            selected_robot = best.pop("_robot")
            selected_weight_fn = best.pop("_weightFn")
            selected_algo = best.pop("_algo")
            batch = _select_vrp_batch(
                delivery,
                deliveries,
                assigned_delivery_ids,
                selected_robot,
                len(available_robots),
            )
            try:
                best = _apply_vrp_batch_to_assignment(
                    best,
                    selected_robot,
                    batch,
                    graph,
                    nearest_node_id_fn,
                    app_state,
                    selected_weight_fn,
                    selected_algo,
                    traffic_penalty_fn,
                    rain_penalty_fn,
                    obstacle_penalty_fn,
                    explanation,
                )
            except Exception as exc:
                best["deliveryIds"] = [best["deliveryId"]]
                best["orderSequence"] = build_order_stops([delivery])
                add_timeline_step(
                    explanation,
                    "vrp_sequence",
                    "rejected",
                    (
                        "VRP batch optimization failed "
                        f"({exc}); falling back to single order."
                    ),
                    selected_robot.get("id"),
                )
            mark_selection(explanation, best, delivery, routed_robot_ids)
            best["explanation"] = explanation
            assignments.append(best)
            assigned_delivery_ids.update(best.get("deliveryIds", [best["deliveryId"]]))
            available_robots = [r for r in available_robots if r['id'] != best['robotId']]
        else:
            mark_no_selection(explanation, delivery)

        explanations.append(explanation)
            
    if return_explanations:
        return {"assignments": assignments, "explanations": explanations}

    return assignments
