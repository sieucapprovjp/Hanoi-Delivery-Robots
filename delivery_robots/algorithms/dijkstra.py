import heapq
import time as py_time

def run_dijkstra(graph, start_node, end_node):
    """Executes Dijkstra (uninformed) search."""
    t0 = py_time.time()
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
                "time_ms": round((py_time.time() - t0) * 1000, 2),
                "optimal": True,
                "path": path,
            }
            
        if current in visited:
            continue
        visited.add(current)
        nodes_explored += 1

        for neighbor in graph.neighbors(current):
            if neighbor in visited:
                continue
            edge_data = graph[current][neighbor]
            w = min(data.get("length", 10) for data in edge_data.values())
            nd = dist[current] + w
            if nd < dist.get(neighbor, float("inf")):
                dist[neighbor] = nd
                came_from[neighbor] = current
                heapq.heappush(open_set, (nd, neighbor))
                
    return {
        "path_length": 0,
        "nodes_explored": nodes_explored,
        "time_ms": round((py_time.time() - t0) * 1000, 2),
        "optimal": False,
        "path": [],
    }
