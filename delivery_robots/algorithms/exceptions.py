"""Custom exceptions for routing algorithms in the delivery_robots project.

Both exceptions inherit from networkx.NetworkXNoPath to maintain backward
compatibility with existing catch-blocks.
"""

import networkx as nx


class NoPathError(nx.NetworkXNoPath):
    """Exception raised when no path can be found between the start and end nodes.

    Attributes:
        nodes_explored (int): Number of nodes explored before failure.
    """

    def __init__(self, message: str = "", nodes_explored: int = 0) -> None:
        """Initialize the NoPathError.

        Args:
            message (str): The error message.
            nodes_explored (int): Number of nodes explored.
        """
        super().__init__(message)
        self.nodes_explored: int = nodes_explored


class RoutingTimeoutError(nx.NetworkXNoPath):
    """Exception raised when a routing query exceeds the maximum time limit.

    Attributes:
        nodes_explored (int): Number of nodes explored before timeout.
    """

    def __init__(self, message: str = "", nodes_explored: int = 0) -> None:
        """Initialize the RoutingTimeoutError.

        Args:
            message (str): The error message.
            nodes_explored (int): Number of nodes explored.
        """
        super().__init__(message)
        self.nodes_explored: int = nodes_explored
