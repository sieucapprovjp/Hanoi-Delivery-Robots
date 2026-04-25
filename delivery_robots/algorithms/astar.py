import heapq
import time as py_time
from ..geo_utils import haversine_distance

def run_astar(graph, start_node, end_node, to_lat, to_lon, environment_manager):
    """Executes A* algorithm with environment penalties."""
    t0 = py_time.time()
    open_set = [(0, start_node)]
    came_from = {}
    g_score = {start_node: 0}
    
    start_lat = graph.nodes[start_node]["y"]
    start_lon = graph.nodes[start_node]["x"]
    h_val = {start_node: haversine_distance(start_lat, start_lon, to_lat, to_lon)}
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
                "time_ms": round((py_time.time() - t0) * 1000, 2),
                "optimal": True,
                "path": path,
            }
        
        if current in closed:
            continue
        closed.add(current)
        nodes_explored += 1

        for neighbor in graph.neighbors(current):
            if neighbor in closed:
                continue
            
            edge_data = graph[current][neighbor]
            weight = environment_manager.edge_weight_with_traffic(current, neighbor, edge_data, graph)
            tg = g_score[current] + weight
            
            if tg < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tg
                h = haversine_distance(
                    graph.nodes[neighbor]["y"],
                    graph.nodes[neighbor]["x"],
                    to_lat,
                    to_lon,
                )
                f = tg + h
                f_score[neighbor] = f
                heapq.heappush(open_set, (f, neighbor))
                
    return {
        "path_length": 0,
        "nodes_explored": nodes_explored,
        "time_ms": round((py_time.time() - t0) * 1000, 2),
        "optimal": False,
        "path": [],
    }
