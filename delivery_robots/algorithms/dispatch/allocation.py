import time

from ...algorithms.weighted_search import run_weighted_route_search
from ...config import (
    DISPATCH_BATTERY_DRAIN_PER_KM,
    DISPATCH_BATTERY_RISK_WEIGHT,
    DISPATCH_BATTERY_SAFETY_MARGIN,
    DISPATCH_HIGH_PRIORITY_EXTRA_CANDIDATES,
    DISPATCH_HIGH_PRIORITY_SCORE_THRESHOLD,
    DEFAULT_ROAD_MEMORY_PENALTY,
    DEFAULT_ROUTING_ALGORITHM,
    DISPATCH_MAX_ROUTE_CANDIDATES_PER_DELIVERY,
    DISPATCH_PRIORITY_WEIGHT,
    ROUTING_ALGORITHM_ALIASES,
    VALID_ROUTING_ALGORITHMS,
)
from ...algorithms.dispatch.xai import (
    add_candidate_pruning_step,
    add_scoring_step,
    build_candidate_record,
    build_dispatch_explanation,
    constraint_rejections,
    mark_candidate_pruned,
    mark_candidate_scored,
    mark_no_selection,
    mark_route_failure,
    mark_selection,
    reject_candidate,
)
from ...utils.geo import haversine_distance
from ...utils.route_analysis import (
    attach_route_metadata,
    build_memory_weight_fn,
    build_route_response,
)


def calculate_priority_score(delivery, current_time_ms):
    created_at = delivery.get('createdAt') or current_time_ms
    wait_minutes = max(0, current_time_ms - created_at) / 60000.0
    pickup_weights = {
        'restaurant': 9, 'market': 7, 'retail': 6, 'office': 5,
        'hotel': 5, 'landmark': 3, 'residential': 4
    }
    drop_weights = {
        'residential': 8, 'hotel': 6, 'office': 5, 'retail': 4,
        'restaurant': 4, 'landmark': 2, 'market': 3
    }
    theme = delivery.get('theme', {})
    pickup_cat = theme.get('pickupCategory')
    drop_cat = theme.get('dropoffCategory')
    
    p_weight = pickup_weights.get(pickup_cat, 4)
    d_weight = drop_weights.get(drop_cat, 4)
    return p_weight + d_weight + wait_minutes * 2.8


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
    
    for delivery in deliveries:
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
                mark_candidate_scored(
                    candidate,
                    total_cost,
                    battery_risk,
                    total_score,
                    algo,
                    delivery['priorityScore'],
                    route_payload,
                )
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
                    }
            except Exception:
                mark_route_failure(explanation, candidate, robot)
                
        if best:
            mark_selection(explanation, best, delivery, routed_robot_ids)
            best["explanation"] = explanation
            assignments.append(best)
            available_robots = [r for r in available_robots if r['id'] != best['robotId']]
        else:
            mark_no_selection(explanation, delivery)

        explanations.append(explanation)
            
    if return_explanations:
        return {"assignments": assignments, "explanations": explanations}

    return assignments
