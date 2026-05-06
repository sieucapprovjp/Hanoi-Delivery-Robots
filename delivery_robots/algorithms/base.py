def reconstruct_node_path(came_from, current):
    """Reconstructs the path from the start node to the current node."""
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path
