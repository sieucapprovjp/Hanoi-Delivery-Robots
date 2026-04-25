import time as py_time
from collections import deque

def run_bfs(graph, start_node, end_node):
    """Executes BFS (blind search)."""
    t0 = py_time.time()
    queue = deque([start_node])
    came_from = {start_node: None}
    visited = set([start_node])
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
                "time_ms": round((py_time.time() - t0) * 1000, 2),
                "optimal": True,
                "path": path,
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
        "time_ms": round((py_time.time() - t0) * 1000, 2),
        "optimal": False,
        "path": [],
    }
