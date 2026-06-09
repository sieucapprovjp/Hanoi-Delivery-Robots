import time

from ...algorithms.weighted_search import run_weighted_route_search
from ...config import (
    DISPATCH_BATTERY_DRAIN_PER_KM,
    DISPATCH_BATTERY_RISK_WEIGHT,
    DISPATCH_BATTERY_SAFETY_MARGIN,
    DISPATCH_HIGH_PRIORITY_EXTRA_CANDIDATES,
    DISPATCH_HIGH_PRIORITY_SCORE_THRESHOLD,
    DISPATCH_MAX_PICKUP_DISTANCE_METERS,
    DEFAULT_ROAD_MEMORY_PENALTY,
    DEFAULT_ROUTING_ALGORITHM,
    DISPATCH_MAX_ROUTE_CANDIDATES_PER_DELIVERY,
    DISPATCH_MIN_BATTERY_PERCENT,
    DISPATCH_PRIORITY_WEIGHT,
    DISPATCH_REQUIRED_ROBOT_STATUS,
    ROUTING_ALGORITHM_ALIASES,
    VALID_ROUTING_ALGORITHMS,
)
from ...utils.geo import haversine_distance
from ...utils.route_analysis import build_route_response


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


def _road_memory_key(graph, from_node, to_node):
    from_data = graph.nodes[from_node]
    to_data = graph.nodes[to_node]
    return (
        f"{from_data['y']:.4f},{from_data['x']:.4f}->"
        f"{to_data['y']:.4f},{to_data['x']:.4f}"
    )


def _constraint_rejections(robot, pickup_distance_meters):
    rejections = []
    status = robot.get('status')
    if status is not None and status != DISPATCH_REQUIRED_ROBOT_STATUS:
        rejections.append(
            {
                "code": "not_idle",
                "message": f"Robot status is {status}; expected idle.",
            }
        )

    capacity = robot.get('capacity')
    current_load = robot.get('currentLoad', 0)
    if capacity is not None and current_load >= capacity:
        rejections.append(
            {
                "code": "capacity_full",
                "message": f"Load {current_load}/{capacity} leaves no free capacity.",
            }
        )

    battery = robot.get('battery', 0)
    if battery < DISPATCH_MIN_BATTERY_PERCENT:
        rejections.append(
            {
                "code": "low_battery",
                "message": (
                    f"Battery {battery:.1f}% is below "
                    f"{DISPATCH_MIN_BATTERY_PERCENT}% minimum."
                ),
            }
        )

    if pickup_distance_meters > DISPATCH_MAX_PICKUP_DISTANCE_METERS:
        rejections.append(
            {
                "code": "pickup_too_far",
                "message": (
                    f"Pickup distance {pickup_distance_meters:.0f}m exceeds "
                    f"{DISPATCH_MAX_PICKUP_DISTANCE_METERS}m limit."
                ),
            }
        )

    return rejections


def _candidate_record(robot, pickup_distance_meters, approximate_score):
    return {
        "robotId": robot.get('id'),
        "robotName": robot.get('name', ''),
        "status": "candidate",
        "battery": round(robot.get('battery', 0), 1),
        "currentLoad": robot.get('currentLoad', 0),
        "capacity": robot.get('capacity'),
        "pickupDistance": round(pickup_distance_meters, 1),
        "approximateScore": round(approximate_score, 1),
        "reasons": [],
    }


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

    def approximate_robot_score(robot, distance):
        projected_drain = (distance / 1000.0) * DISPATCH_BATTERY_DRAIN_PER_KM
        battery_risk = max(
            0,
            projected_drain
            - robot.get('battery', 0) * DISPATCH_BATTERY_SAFETY_MARGIN,
        )
        return distance + battery_risk * DISPATCH_BATTERY_RISK_WEIGHT

    def candidate_limit(delivery, ranked_count):
        extra_candidates = (
            DISPATCH_HIGH_PRIORITY_EXTRA_CANDIDATES
            if delivery['priorityScore'] >= DISPATCH_HIGH_PRIORITY_SCORE_THRESHOLD
            else 0
        )
        limit = max(
            1,
            min(
                ranked_count,
                DISPATCH_MAX_ROUTE_CANDIDATES_PER_DELIVERY + extra_candidates,
            ),
        )
        return limit

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
        explanation = {
            "deliveryId": delivery['id'],
            "pickupName": delivery['pickup'].get('name', ''),
            "destinationName": delivery['destination'].get('name', ''),
            "priorityScore": round(delivery['priorityScore'], 2),
            "objective": (
                "minimize routeCost + batteryRisk*wBattery - priority*wPriority"
            ),
            "constraints": {
                "requiredStatus": DISPATCH_REQUIRED_ROBOT_STATUS,
                "minBatteryPercent": DISPATCH_MIN_BATTERY_PERCENT,
                "maxPickupDistanceMeters": DISPATCH_MAX_PICKUP_DISTANCE_METERS,
                "capacityRule": "currentLoad < capacity",
            },
            "timeline": [
                {
                    "stage": "priority",
                    "status": "info",
                    "message": (
                        f"Order #{delivery['id']} priority = "
                        f"{delivery['priorityScore']:.1f}."
                    ),
                }
            ],
            "candidates": [],
            "selectedRobotId": None,
        }
        feasible_candidates = []

        for robot in available_robots:
            pickup_distance = haversine_distance(
                robot['lat'], robot['lon'], pickup_lat, pickup_lon
            )
            approx_score = approximate_robot_score(robot, pickup_distance)
            candidate = _candidate_record(robot, pickup_distance, approx_score)
            rejections = _constraint_rejections(robot, pickup_distance)
            if rejections:
                candidate["status"] = "rejected"
                candidate["reasons"] = rejections
                explanation["candidates"].append(candidate)
                explanation["timeline"].append(
                    {
                        "stage": "csp",
                        "status": "rejected",
                        "robotId": robot.get('id'),
                        "message": (
                            f"{robot.get('name', robot.get('id'))} rejected by "
                            f"CSP: {', '.join(item['code'] for item in rejections)}."
                        ),
                    }
                )
                continue

            explanation["candidates"].append(candidate)
            feasible_candidates.append((robot, candidate))

        ranked_candidates = sorted(
            feasible_candidates, key=lambda item: item[1]["approximateScore"]
        )
        limit = candidate_limit(delivery, len(ranked_candidates))
        routed_candidates = ranked_candidates[:limit]
        routed_robot_ids = {robot.get('id') for robot, _ in routed_candidates}

        for robot, candidate in ranked_candidates[limit:]:
            candidate["status"] = "pruned"
            candidate["reasons"] = [
                {
                    "code": "outside_top_k_prescore",
                    "message": (
                        f"Not routed because only top {limit} feasible robots "
                        "are expanded."
                    ),
                }
            ]

        explanation["timeline"].append(
            {
                "stage": "candidate_pruning",
                "status": "info",
                "message": (
                    f"{len(ranked_candidates)} feasible robot(s); routing "
                    f"{len(routed_candidates)} after heuristic pre-score."
                ),
            }
        )
        
        for robot, candidate in routed_candidates:
            try:
                start_node = cached_robot_node(robot)
                road_memory = robot.get('roadMemory', {})
                algo = _normalize_route_algorithm(robot.get('routeAlgorithm'))
                
                def edge_weight_with_memory(from_node, to_node, edge_data):
                    base = cached_base_weight(from_node, to_node, edge_data)
                    edge_key = (from_node, to_node)
                    if edge_key not in memory_key_cache:
                        memory_key_cache[edge_key] = _road_memory_key(
                            graph, from_node, to_node
                        )
                    memory_penalty = road_memory.get(
                        memory_key_cache[edge_key], DEFAULT_ROAD_MEMORY_PENALTY
                    )
                    return base * memory_penalty
                    
                weight_fn = edge_weight_with_memory if road_memory else cached_base_weight
                
                start_t = time.time()
                route_nodes, nodes_explored = run_weighted_route_search(
                    graph, start_node, end_node, pickup_lat, pickup_lon, weight_fn, algo
                )
                calc_time = (time.time() - start_t) * 1000
                
                # Assemble payload similar to /api/route so frontend doesn't need to fetch it again
                route_payload = build_route_response(
                    graph, route_nodes, traffic_penalty_fn, rain_penalty_fn, obstacle_penalty_fn
                )
                route_payload["start"] = {"lat": graph.nodes[start_node]["y"], "lon": graph.nodes[start_node]["x"]}
                route_payload["end"] = {"lat": graph.nodes[end_node]["y"], "lon": graph.nodes[end_node]["x"]}
                route_payload["algo"] = algo
                route_payload["timeMs"] = round(calc_time, 2)
                route_payload["nodesExplored"] = nodes_explored
                breakdown = route_payload.get("costBreakdown", {})
                total_cost = breakdown.get("totalCost", route_payload.get("distance", 0.0))
                route_payload["pathCost"] = total_cost
                
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
                candidate["status"] = "scored"
                candidate["routeCost"] = round(total_cost, 1)
                candidate["batteryRisk"] = round(battery_risk, 2)
                candidate["totalScore"] = round(total_score, 2)
                candidate["algo"] = algo
                candidate["formula"] = (
                    f"{total_cost:.1f} + {battery_risk:.2f}*"
                    f"{DISPATCH_BATTERY_RISK_WEIGHT} - "
                    f"{delivery['priorityScore']:.1f}*{DISPATCH_PRIORITY_WEIGHT}"
                )
                explanation["timeline"].append(
                    {
                        "stage": "scoring",
                        "status": "info",
                        "robotId": robot.get('id'),
                        "message": (
                            f"{robot.get('name', robot.get('id'))}: score "
                            f"{total_score:.1f} using {algo.upper()} route cost "
                            f"{total_cost:.1f}m."
                        ),
                    }
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
                candidate["status"] = "rejected"
                candidate["reasons"] = [
                    {
                        "code": "route_failed",
                        "message": "No viable route found for this robot.",
                    }
                ]
                explanation["timeline"].append(
                    {
                        "stage": "routing",
                        "status": "rejected",
                        "robotId": robot.get('id'),
                        "message": (
                            f"{robot.get('name', robot.get('id'))} rejected: "
                            "route search failed."
                        ),
                    }
                )
                
        if best:
            explanation["selectedRobotId"] = best["robotId"]
            for candidate in explanation["candidates"]:
                if candidate["robotId"] == best["robotId"]:
                    candidate["status"] = "selected"
                    candidate["reasons"] = [
                        {
                            "code": "lowest_total_score",
                            "message": "Selected because it has the lowest final score.",
                        }
                    ]
                elif (
                    candidate["robotId"] in routed_robot_ids
                    and candidate["status"] == "scored"
                ):
                    candidate["status"] = "not_selected"
                    candidate["reasons"] = [
                        {
                            "code": "higher_total_score",
                            "message": "Feasible, but score is higher than selected robot.",
                        }
                    ]

            explanation["timeline"].append(
                {
                    "stage": "selection",
                    "status": "selected",
                    "robotId": best["robotId"],
                    "message": (
                        f"Selected {best['robotName']} for order #{delivery['id']} "
                        f"with score {best['totalScore']:.1f}."
                    ),
                }
            )
            best["explanation"] = explanation
            assignments.append(best)
            available_robots = [r for r in available_robots if r['id'] != best['robotId']]
        else:
            explanation["timeline"].append(
                {
                    "stage": "selection",
                    "status": "rejected",
                    "message": f"No feasible robot for order #{delivery['id']}.",
                }
            )

        explanations.append(explanation)
            
    if return_explanations:
        return {"assignments": assignments, "explanations": explanations}

    return assignments
