import heapq
import time
from collections import deque

import numpy as np

from ..config import (
    ASTEP_MAX_STEPS,
    INSIDER_COORD_ROUND_DECIMALS,
    INSIDER_FALLBACK_EDGE_LENGTH,
    INSIDER_SCORE_ROUND_DECIMALS,
    INSIDER_TIME_ROUND_DECIMALS,
    TIMESTAMP_MS_MULTIPLIER,
)
from ..utils.geo import haversine_distance


def json_safe_node_id(node_id):
    if isinstance(node_id, np.integer):
        return int(node_id)
    return node_id


def run_astep_demo(
    graph,
    start_node,
    end_node,
    to_lat,
    to_lon,
    traffic_penalty_for_point,
    rain_penalty_for_point,
    obstacle_penalty_for_point,
    max_steps=ASTEP_MAX_STEPS,
):
    start_t = time.time()
    open_set = [(0, start_node)]
    came_from = {}
    g_score = {start_node: 0}
    h_score = {
        start_node: haversine_distance(
            graph.nodes[start_node]["y"], graph.nodes[start_node]["x"], to_lat, to_lon
        )
    }
    f_score = {start_node: h_score[start_node]}
    closed_set = set()
    steps = []
    explored_nodes = []

    step_count = 0
    while open_set and step_count < max_steps:
        step_count += 1
        _, current = heapq.heappop(open_set)

        if current == end_node:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            path_coords = [{"lat": graph.nodes[n]["y"], "lon": graph.nodes[n]["x"]} for n in path]

            return {
                "success": True,
                "path": path_coords,
                "pathLength": len(path),
                "steps": steps,
                "exploredPath": [
                    {"lat": graph.nodes[node]["y"], "lon": graph.nodes[node]["x"]}
                    for node in explored_nodes
                ],
                "totalSteps": step_count,
                "calcTime": round(
                    (time.time() - start_t) * TIMESTAMP_MS_MULTIPLIER,
                    INSIDER_TIME_ROUND_DECIMALS,
                ),
                "startNode": json_safe_node_id(start_node),
                "endNode": json_safe_node_id(end_node),
                "openSetSize": len(open_set),
                "closedSetSize": len(closed_set),
            }

        if current in closed_set:
            continue
        closed_set.add(current)
        explored_nodes.append(current)

        current_lat = graph.nodes[current]["y"]
        current_lon = graph.nodes[current]["x"]
        h_current = haversine_distance(current_lat, current_lon, to_lat, to_lon)
        steps.append(
            {
                "step": step_count,
                "currentNode": json_safe_node_id(current),
                "currentCoords": {
                    "lat": round(current_lat, INSIDER_COORD_ROUND_DECIMALS),
                    "lon": round(current_lon, INSIDER_COORD_ROUND_DECIMALS),
                },
                "g": round(g_score.get(current, 0), INSIDER_SCORE_ROUND_DECIMALS),
                "h": round(h_current, INSIDER_SCORE_ROUND_DECIMALS),
                "f": round(f_score.get(current, 0), INSIDER_SCORE_ROUND_DECIMALS),
                "openSetSize": len(open_set),
                "closedSetSize": len(closed_set),
                "formula": (
                    f"f(n) = {g_score.get(current, 0):.0f} + {h_current:.0f} = "
                    f"{f_score.get(current, 0):.0f}"
                ),
            }
        )

        for neighbor in graph.neighbors(current):
            if neighbor in closed_set:
                continue

            edge_data = graph[current][neighbor]
            edge_length = min(
                d.get("length", INSIDER_FALLBACK_EDGE_LENGTH)
                for d in edge_data.values()
            )
            mid_lat = (graph.nodes[current]["y"] + graph.nodes[neighbor]["y"]) / 2
            mid_lon = (graph.nodes[current]["x"] + graph.nodes[neighbor]["x"]) / 2
            traffic_pen = traffic_penalty_for_point(mid_lat, mid_lon)
            rain_pen = rain_penalty_for_point(mid_lat, mid_lon)
            obs_pen = obstacle_penalty_for_point(mid_lat, mid_lon)
            total_weight = edge_length * traffic_pen * rain_pen * obs_pen
            tentative_g = g_score[current] + total_weight

            if tentative_g < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                h_neighbor = haversine_distance(
                    graph.nodes[neighbor]["y"],
                    graph.nodes[neighbor]["x"],
                    to_lat,
                    to_lon,
                )
                h_score[neighbor] = h_neighbor
                f_score[neighbor] = tentative_g + h_neighbor
                heapq.heappush(open_set, (f_score[neighbor], neighbor))

    return {
        "success": False,
        "steps": steps,
        "exploredPath": [
            {"lat": graph.nodes[node]["y"], "lon": graph.nodes[node]["x"]}
            for node in explored_nodes
        ],
        "totalSteps": step_count,
        "calcTime": round(
            (time.time() - start_t) * TIMESTAMP_MS_MULTIPLIER,
            INSIDER_TIME_ROUND_DECIMALS,
        ),
    }


def run_insider_comparison(
    graph,
    start_node,
    end_node,
    to_lat,
    to_lon,
    traffic_penalty_for_point,
    rain_penalty_for_point,
    obstacle_penalty_for_point,
):
    def run_astar():
        t0 = time.time()
        open_set = [(0, start_node)]
        came_from = {}
        g_score = {start_node: 0}
        h_val = {
            start_node: haversine_distance(
                graph.nodes[start_node]["y"], graph.nodes[start_node]["x"], to_lat, to_lon
            )
        }
        f_score = {start_node: h_val[start_node]}
        closed = set()
        nodes_explored = 0

        while open_set:
            _, current = heapq.heappop(open_set)
            if current == end_node:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start_node)
                path.reverse()
                return {
                    "path_length": len(path),
                    "nodes_explored": nodes_explored,
                    "time_ms": round(
                        (time.time() - t0) * TIMESTAMP_MS_MULTIPLIER,
                        INSIDER_TIME_ROUND_DECIMALS,
                    ),
                    "optimal": True,
                }
            if current in closed:
                continue
            closed.add(current)
            nodes_explored += 1

            for neighbor in graph.neighbors(current):
                if neighbor in closed:
                    continue
                edge_data = graph[current][neighbor]
                edge_len = min(
                    d.get("length", INSIDER_FALLBACK_EDGE_LENGTH)
                    for d in edge_data.values()
                )
                mid_lat = (graph.nodes[current]["y"] + graph.nodes[neighbor]["y"]) / 2
                mid_lon = (graph.nodes[current]["x"] + graph.nodes[neighbor]["x"]) / 2
                w = (
                    edge_len
                    * traffic_penalty_for_point(mid_lat, mid_lon)
                    * rain_penalty_for_point(mid_lat, mid_lon)
                    * obstacle_penalty_for_point(mid_lat, mid_lon)
                )
                tg = g_score[current] + w
                if tg < g_score.get(neighbor, float("inf")):
                    came_from[neighbor] = current
                    g_score[neighbor] = tg
                    h = haversine_distance(
                        graph.nodes[neighbor]["y"],
                        graph.nodes[neighbor]["x"],
                        to_lat,
                        to_lon,
                    )
                    heapq.heappush(open_set, (tg + h, neighbor))
        return {
            "path_length": 0,
            "nodes_explored": nodes_explored,
            "time_ms": round(
                (time.time() - t0) * TIMESTAMP_MS_MULTIPLIER,
                INSIDER_TIME_ROUND_DECIMALS,
            ),
            "optimal": False,
        }

    def run_dijkstra():
        t0 = time.time()
        open_set = [(0, start_node)]
        dist = {start_node: 0}
        came_from = {}
        visited = set()
        nodes_explored = 0

        while open_set:
            d, current = heapq.heappop(open_set)
            if current == end_node:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start_node)
                path.reverse()
                return {
                    "path_length": len(path),
                    "nodes_explored": nodes_explored,
                    "time_ms": round(
                        (time.time() - t0) * TIMESTAMP_MS_MULTIPLIER,
                        INSIDER_TIME_ROUND_DECIMALS,
                    ),
                    "optimal": True,
                }
            if current in visited:
                continue
            visited.add(current)
            nodes_explored += 1

            for neighbor in graph.neighbors(current):
                if neighbor in visited:
                    continue
                edge_data = graph[current][neighbor]
                w = min(
                    val.get("length", INSIDER_FALLBACK_EDGE_LENGTH)
                    for val in edge_data.values()
                )
                nd = dist[current] + w
                if nd < dist.get(neighbor, float("inf")):
                    dist[neighbor] = nd
                    came_from[neighbor] = current
                    heapq.heappush(open_set, (nd, neighbor))
        return {
            "path_length": 0,
            "nodes_explored": nodes_explored,
            "time_ms": round(
                (time.time() - t0) * TIMESTAMP_MS_MULTIPLIER,
                INSIDER_TIME_ROUND_DECIMALS,
            ),
            "optimal": False,
        }

    def run_greedy():
        t0 = time.time()
        h_start = haversine_distance(
            graph.nodes[start_node]["y"], graph.nodes[start_node]["x"], to_lat, to_lon
        )
        open_set = [(h_start, start_node)]
        came_from = {}
        visited = set()
        nodes_explored = 0

        while open_set:
            _, current = heapq.heappop(open_set)
            if current == end_node:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start_node)
                path.reverse()
                return {
                    "path_length": len(path),
                    "nodes_explored": nodes_explored,
                    "time_ms": round(
                        (time.time() - t0) * TIMESTAMP_MS_MULTIPLIER,
                        INSIDER_TIME_ROUND_DECIMALS,
                    ),
                    "optimal": False,
                }
            if current in visited:
                continue
            visited.add(current)
            nodes_explored += 1

            for neighbor in graph.neighbors(current):
                if neighbor in visited:
                    continue
                h = haversine_distance(
                    graph.nodes[neighbor]["y"],
                    graph.nodes[neighbor]["x"],
                    to_lat,
                    to_lon,
                )
                came_from[neighbor] = current
                heapq.heappush(open_set, (h, neighbor))
        return {
            "path_length": 0,
            "nodes_explored": nodes_explored,
            "time_ms": round(
                (time.time() - t0) * TIMESTAMP_MS_MULTIPLIER,
                INSIDER_TIME_ROUND_DECIMALS,
            ),
            "optimal": False,
        }

    def run_bfs():
        t0 = time.time()
        queue = deque([start_node])
        came_from = {start_node: None}
        visited = {start_node}
        nodes_explored = 0

        while queue:
            current = queue.popleft()
            if current == end_node:
                path = []
                while current is not None:
                    path.append(current)
                    current = came_from[current]
                path.reverse()
                return {
                    "path_length": len(path),
                    "nodes_explored": nodes_explored,
                    "time_ms": round(
                        (time.time() - t0) * TIMESTAMP_MS_MULTIPLIER,
                        INSIDER_TIME_ROUND_DECIMALS,
                    ),
                    "optimal": True,
                }
            nodes_explored += 1
            for neighbor in graph.neighbors(current):
                if neighbor not in visited:
                    visited.add(neighbor)
                    came_from[neighbor] = current
                    queue.append(neighbor)
        return {
            "path_length": 0,
            "nodes_explored": nodes_explored,
            "time_ms": round(
                (time.time() - t0) * TIMESTAMP_MS_MULTIPLIER,
                INSIDER_TIME_ROUND_DECIMALS,
            ),
            "optimal": False,
        }

    astar = run_astar()
    dijkstra = run_dijkstra()
    greedy = run_greedy()
    bfs = run_bfs()
    best_path = min(
        result["path_length"]
        for result in [astar, dijkstra, greedy, bfs]
        if result["path_length"] > 0
    )
    return {
        "algorithms": {
            "A*": astar,
            "Dijkstra": dijkstra,
            "Greedy Best-First": greedy,
            "BFS": bfs,
        },
        "best_path_length": best_path,
    }
