import heapq
import time
from collections import deque

from ..utils.geo import haversine_distance


def _edge_length(graph, from_node, to_node):
    edge_data = graph[from_node][to_node]
    if "length" in edge_data:
        return float(edge_data.get("length", 1.0))
    return min(float(d.get("length", 1.0)) for d in edge_data.values())


def _reconstruct_path(came_from, current):
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path


def _path_cost(graph, path):
    if len(path) < 2:
        return 0.0
    total = 0.0
    for idx in range(len(path) - 1):
        total += _edge_length(graph, path[idx], path[idx + 1])
    return total


def run_dijkstra(graph, start_node, end_node):
    started = time.time()
    open_set = [(0.0, start_node)]
    dist = {start_node: 0.0}
    came_from = {}
    visited = set()
    nodes_explored = 0

    while open_set:
        current_dist, current = heapq.heappop(open_set)
        if current in visited:
            continue
        visited.add(current)
        nodes_explored += 1

        if current == end_node:
            path = _reconstruct_path(came_from, current)
            return {
                "found": True,
                "path": path,
                "pathLength": len(path),
                "pathCost": round(current_dist, 2),
                "nodesExplored": nodes_explored,
                "timeMs": round((time.time() - started) * 1000, 2),
                "expectedOptimal": True,
            }

        for neighbor in graph.neighbors(current):
            if neighbor in visited:
                continue
            next_dist = dist[current] + _edge_length(graph, current, neighbor)
            if next_dist < dist.get(neighbor, float("inf")):
                dist[neighbor] = next_dist
                came_from[neighbor] = current
                heapq.heappush(open_set, (next_dist, neighbor))

    return {
        "found": False,
        "path": [],
        "pathLength": 0,
        "pathCost": 0.0,
        "nodesExplored": nodes_explored,
        "timeMs": round((time.time() - started) * 1000, 2),
        "expectedOptimal": True,
    }


def run_astar(graph, start_node, end_node, goal_lat, goal_lon):
    started = time.time()
    open_set = [(0.0, start_node)]
    came_from = {}
    g_score = {start_node: 0.0}
    closed = set()
    nodes_explored = 0

    while open_set:
        _, current = heapq.heappop(open_set)
        if current in closed:
            continue
        closed.add(current)
        nodes_explored += 1

        if current == end_node:
            path = _reconstruct_path(came_from, current)
            return {
                "found": True,
                "path": path,
                "pathLength": len(path),
                "pathCost": round(_path_cost(graph, path), 2),
                "nodesExplored": nodes_explored,
                "timeMs": round((time.time() - started) * 1000, 2),
                "expectedOptimal": True,
            }

        for neighbor in graph.neighbors(current):
            if neighbor in closed:
                continue
            tentative_g = g_score[current] + _edge_length(graph, current, neighbor)
            if tentative_g < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                heuristic = haversine_distance(
                    graph.nodes[neighbor]["y"],
                    graph.nodes[neighbor]["x"],
                    goal_lat,
                    goal_lon,
                )
                heapq.heappush(open_set, (tentative_g + heuristic, neighbor))

    return {
        "found": False,
        "path": [],
        "pathLength": 0,
        "pathCost": 0.0,
        "nodesExplored": nodes_explored,
        "timeMs": round((time.time() - started) * 1000, 2),
        "expectedOptimal": True,
    }


def run_greedy_best_first(graph, start_node, end_node, goal_lat, goal_lon):
    started = time.time()
    open_set = []
    start_h = haversine_distance(
        graph.nodes[start_node]["y"],
        graph.nodes[start_node]["x"],
        goal_lat,
        goal_lon,
    )
    heapq.heappush(open_set, (start_h, start_node))
    came_from = {}
    visited = set()
    nodes_explored = 0

    while open_set:
        _, current = heapq.heappop(open_set)
        if current in visited:
            continue
        visited.add(current)
        nodes_explored += 1

        if current == end_node:
            path = _reconstruct_path(came_from, current)
            return {
                "found": True,
                "path": path,
                "pathLength": len(path),
                "pathCost": round(_path_cost(graph, path), 2),
                "nodesExplored": nodes_explored,
                "timeMs": round((time.time() - started) * 1000, 2),
                "expectedOptimal": False,
            }

        for neighbor in graph.neighbors(current):
            if neighbor in visited:
                continue
            if neighbor not in came_from:
                came_from[neighbor] = current
            heuristic = haversine_distance(
                graph.nodes[neighbor]["y"],
                graph.nodes[neighbor]["x"],
                goal_lat,
                goal_lon,
            )
            heapq.heappush(open_set, (heuristic, neighbor))

    return {
        "found": False,
        "path": [],
        "pathLength": 0,
        "pathCost": 0.0,
        "nodesExplored": nodes_explored,
        "timeMs": round((time.time() - started) * 1000, 2),
        "expectedOptimal": False,
    }


def run_bfs(graph, start_node, end_node):
    started = time.time()
    queue = deque([start_node])
    came_from = {start_node: None}
    nodes_explored = 0

    while queue:
        current = queue.popleft()
        nodes_explored += 1

        if current == end_node:
            path = [current]
            while came_from[current] is not None:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return {
                "found": True,
                "path": path,
                "pathLength": len(path),
                "pathCost": round(_path_cost(graph, path), 2),
                "nodesExplored": nodes_explored,
                "timeMs": round((time.time() - started) * 1000, 2),
                "expectedOptimal": False,
            }

        for neighbor in graph.neighbors(current):
            if neighbor not in came_from:
                came_from[neighbor] = current
                queue.append(neighbor)

    return {
        "found": False,
        "path": [],
        "pathLength": 0,
        "pathCost": 0.0,
        "nodesExplored": nodes_explored,
        "timeMs": round((time.time() - started) * 1000, 2),
        "expectedOptimal": False,
    }


def compare_classical_algorithms(graph, start_node, end_node, goal_lat, goal_lon):
    results = {
        "Dijkstra": run_dijkstra(graph, start_node, end_node),
        "A*": run_astar(graph, start_node, end_node, goal_lat, goal_lon),
        "Greedy Best-First": run_greedy_best_first(
            graph, start_node, end_node, goal_lat, goal_lon
        ),
        "BFS": run_bfs(graph, start_node, end_node),
    }

    found_costs = [res["pathCost"] for res in results.values() if res["found"]]
    best_cost = min(found_costs) if found_costs else 0.0
    for res in results.values():
        res["isBestCost"] = bool(res["found"] and best_cost and res["pathCost"] == best_cost)
        if not best_cost:
            res["isBestCost"] = False
        res["pathNodeIds"] = res.pop("path")

    return {"algorithms": results, "bestPathCost": best_cost}
