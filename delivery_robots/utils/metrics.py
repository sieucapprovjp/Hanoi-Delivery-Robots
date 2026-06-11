from ..config import METRICS_INITIAL_MIN_CALC_TIME, METRICS_PATH_LENGTHS_MAX_SIZE


def create_metrics():
    return {
        "totalCalculations": 0,
        "avgCalculationTime": 0,
        "lastCalculationTime": 0,
        "minCalculationTime": METRICS_INITIAL_MIN_CALC_TIME,
        "maxCalculationTime": 0,
        "avgNodesExplored": 0,
        "totalCalculationTime": 0,
        "totalNodesExplored": 0,
        "pathLengths": [],
        "failedOrders": 0,
    }


def record_route_metrics(metrics, calc_time_ms, nodes_explored, path_length):
    metrics["totalCalculations"] += 1
    metrics["lastCalculationTime"] = calc_time_ms
    metrics["minCalculationTime"] = min(metrics["minCalculationTime"], calc_time_ms)
    metrics["maxCalculationTime"] = max(metrics["maxCalculationTime"], calc_time_ms)
    metrics["totalCalculationTime"] += calc_time_ms
    metrics["avgCalculationTime"] = (
        metrics["totalCalculationTime"] / metrics["totalCalculations"]
    )
    metrics["totalNodesExplored"] += nodes_explored
    metrics["avgNodesExplored"] = (
        metrics["totalNodesExplored"] / metrics["totalCalculations"]
    )
    metrics["pathLengths"].append(path_length)
    if len(metrics["pathLengths"]) > METRICS_PATH_LENGTHS_MAX_SIZE:
        metrics["pathLengths"] = metrics["pathLengths"][-METRICS_PATH_LENGTHS_MAX_SIZE:]


def build_metrics_payload(
    metrics, graph, rain_count, traffic_count, obstacle_count, include_static=False
):
    avg_path = (
        sum(metrics["pathLengths"]) / len(metrics["pathLengths"])
        if metrics["pathLengths"]
        else 0
    )
    payload = {
        "pathfinding": {
            "totalCalculations": metrics["totalCalculations"],
            "avgCalculationTime": round(metrics["avgCalculationTime"], 2),
            "lastCalculationTime": round(metrics["lastCalculationTime"], 2),
            "minCalculationTime": round(metrics["minCalculationTime"], 2)
            if metrics["minCalculationTime"] < METRICS_INITIAL_MIN_CALC_TIME
            else 0,
            "maxCalculationTime": round(metrics["maxCalculationTime"], 2),
            "avgNodesExplored": round(metrics["avgNodesExplored"], 1),
            "avgPathLength": round(avg_path, 1),
        },
        "activeFactors": {
            "rainZones": rain_count,
            "trafficRoutes": traffic_count,
            "obstacles": obstacle_count,
        },
        "failureMetrics": {
            "failedOrders": metrics.get("failedOrders", 0),
        },
    }

    if include_static:
        payload["graph"] = {
            "totalNodes": graph.number_of_nodes() if graph else 0,
            "totalEdges": graph.number_of_edges() if graph else 0,
        }

    return payload
