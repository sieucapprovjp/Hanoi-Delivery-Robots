import heapq
import time as py_time
from ..geo_utils import haversine_distance

def run_greedy(graph, start_node, end_node, to_lat, to_lon):
    """Executes Greedy Best-First (only heuristic) search."""
    t0 = py_time.time()
    
    start_lat = graph.nodes[start_node]["y"]
    start_lon = graph.nodes[start_node]["x"]
    h_start = haversine_distance(start_lat, start_lon, to_lat, to_lon)
    
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
                "time_ms": round((py_time.time() - t0) * 1000, 2),
                "optimal": False,
                "path": path,
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
        "time_ms": round((py_time.time() - t0) * 1000, 2),
        "optimal": False,
        "path": [],
    }
