import time
from ...utils.route_analysis import build_route_response
from ...algorithms.weighted_search import run_weighted_route_search


def calculate_priority_score(delivery, current_time_ms):
    wait_minutes = (current_time_ms - delivery.get('createdAt', 0)) / 60000.0
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


def assign_deliveries(
    app_state, graph, robots, deliveries, current_time_ms,
    nearest_node_id_fn, edge_weight_with_traffic_fn, 
    traffic_penalty_fn, rain_penalty_fn, obstacle_penalty_fn,
    record_route_metrics_fn, metrics
):
    for d in deliveries:
        d['priorityScore'] = calculate_priority_score(d, current_time_ms)
        
    deliveries.sort(key=lambda x: x['priorityScore'], reverse=True)
    
    assignments = []
    available_robots = list(robots)
    
    for delivery in deliveries:
        if not available_robots:
            break
            
        best = None
        pickup_lat = delivery['pickup']['lat']
        pickup_lon = delivery['pickup']['lon']
        end_node = nearest_node_id_fn(graph, pickup_lat, pickup_lon, app_state["ox"])
        
        for robot in available_robots:
            try:
                start_node = nearest_node_id_fn(graph, robot['lat'], robot['lon'], app_state["ox"])
                road_memory = robot.get('roadMemory', {})
                algo = robot.get('routeAlgorithm', 'astar')
                
                def edge_weight_with_memory(from_node, to_node, edge_data):
                    base = edge_weight_with_traffic_fn(from_node, to_node, edge_data)
                    from_data = graph.nodes[from_node]
                    to_data = graph.nodes[to_node]
                    key = f"{from_data['y']:.4f},{from_data['x']:.4f}->{to_data['y']:.4f},{to_data['x']:.4f}"
                    memory_penalty = road_memory.get(key, 1.0)
                    return base * memory_penalty
                    
                weight_fn = edge_weight_with_memory if road_memory else edge_weight_with_traffic_fn
                
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
                
                projected_drain = (total_cost / 1000.0) * 4.5
                battery_risk = max(0, projected_drain - robot['battery'] * 0.35)
                
                total_score = total_cost + battery_risk * 120 - delivery['priorityScore'] * 18
                
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
                # NetworkXNoPath or other routing error
                pass
                
        if best:
            assignments.append(best)
            available_robots = [r for r in available_robots if r['id'] != best['robotId']]
            
    return assignments
