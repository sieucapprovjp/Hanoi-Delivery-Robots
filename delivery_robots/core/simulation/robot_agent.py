from ...config import (
    ROBOT_STATUS_IDLE,
    ROBOT_STATUS_MOVING_TO_PICKUP,
    ROBOT_STATUS_MOVING_TO_DROPOFF,
    SPEED_METERS_PER_SECOND,
)
from ..environment import edge_weight_with_traffic


class RobotAgent:
    def __init__(
        self,
        env,
        robot_id,
        name,
        color,
        start_lat,
        start_lon,
        app_state,
        on_state_change,
    ):
        self.env = env
        self.robot_id = robot_id
        self.name = name
        self.color = color
        self.lat = start_lat
        self.lon = start_lon
        self.app_state = app_state
        self.on_state_change = on_state_change

        self.status = ROBOT_STATUS_IDLE
        self.current_path = []
        self.path_index = 0
        self.route_target = None
        self.delivery_phase = None
        self.segment_duration = 0
        self.geometry_path = []      # flat [{lat,lon},...] — for drawing
        self.segment_geometry = []   # [[{lat,lon},...], ...] — per-node-segment for interpolation

        # Battery could be implemented here; for now we simulate basic movement
        self.battery = 100.0

        # Start the lifecycle process
        self.action = env.process(self.run())

        # Task queue for orders
        self.task_queue = []

    def assign_task(self, task):
        self.task_queue.append(task)
        if self.status == ROBOT_STATUS_IDLE:
            if self.action.is_alive and not self.action.triggered:
                self.action.interrupt()

    def run(self):
        while True:
            if not self.task_queue:
                self.status = ROBOT_STATUS_IDLE
                self._emit_state()
                try:
                    # Wait indefinitely for a task
                    yield self.env.timeout(999999)
                except Exception:  # Catch Interrupt
                    pass

            if self.task_queue:
                task = self.task_queue.pop(0)
                yield from self.execute_task(task)

    def execute_task(self, task):
        # 1. Move to pickup
        self.status = ROBOT_STATUS_MOVING_TO_PICKUP
        self.current_path = task["pickup_path"]
        self.geometry_path = task.get("pickup_geometry_path", [])
        self.segment_geometry = task.get("pickup_segment_geometry", [])
        self.path_index = 0
        self.route_target = "Pickup"
        self.segment_duration = 0
        self._emit_state()
        yield from self.traverse_path(self.current_path)

        # 2. Pick up item (simulate a short delay)
        yield self.env.timeout(30)  # 30 sim seconds

        # 3. Move to dropoff
        self.status = ROBOT_STATUS_MOVING_TO_DROPOFF
        self.current_path = task["dropoff_path"]
        self.geometry_path = task.get("dropoff_geometry_path", [])
        self.segment_geometry = task.get("dropoff_segment_geometry", [])
        self.path_index = 0
        self.route_target = "Dropoff"
        self.segment_duration = 0
        self._emit_state()
        yield from self.traverse_path(self.current_path)

        # 4. Drop off item
        yield self.env.timeout(30)

        history_lock = self.app_state.get("history_lock")
        delivery_history = self.app_state.get("delivery_history")
        if delivery_history is not None and "dropoff" in task:
            dropoff_coords = [task["dropoff"]["lat"], task["dropoff"]["lon"]]
            if history_lock is not None:
                with history_lock:
                    delivery_history.append(dropoff_coords)
            else:
                delivery_history.append(dropoff_coords)

        self.current_path = []
        self.geometry_path = []
        self.segment_geometry = []
        self.route_target = None
        self.segment_duration = 0
        self._emit_state()

    def traverse_path(self, path_nodes):
        """Move along a sequence of node IDs."""
        graph = self.app_state["road_graph"]
        if not graph or len(path_nodes) < 2:
            return

        for i in range(len(path_nodes) - 1):
            from_node = path_nodes[i]
            to_node = path_nodes[i + 1]
            self.path_index = i

            edge_data = graph.get_edge_data(from_node, to_node)
            if edge_data:
                # Update position to the current node BEFORE moving
                from_node_data = graph.nodes[from_node]
                self.lat = from_node_data["y"]
                self.lon = from_node_data["x"]

                # Calculate time to traverse
                weight = edge_weight_with_traffic(
                    self.app_state, from_node, to_node, edge_data
                )
                self.segment_duration = weight / SPEED_METERS_PER_SECOND

                # Emit state BEFORE yielding. Frontend knows we are at `i` and moving to `i+1`
                self._emit_state()

                # Deplete battery (e.g. 1% per 60 sim seconds of travel)
                self.battery = max(0.0, self.battery - (self.segment_duration / 60.0))

                yield self.env.timeout(self.segment_duration)

        # Final node
        final_node = path_nodes[-1]
        self.lat = graph.nodes[final_node]["y"]
        self.lon = graph.nodes[final_node]["x"]
        self.path_index = len(path_nodes) - 1
        self.segment_duration = 0
        self._emit_state()

    def _emit_state(self):
        # Notify the manager/frontend of a state change
        if self.on_state_change:
            self.on_state_change(self.get_state())

    def get_state(self):
        state = {
            "id": self.robot_id,
            "name": self.name,
            "color": self.color,
            "lat": self.lat,
            "lon": self.lon,
            "status": self.status,
            "path_index": self.path_index,
            "route_target": self.route_target,
            "battery": self.battery,
            "current_path_length": len(self.current_path),
            "segment_duration": self.segment_duration,
        }

        if self.geometry_path:
            state["geometry_path"] = self.geometry_path

        if self.segment_geometry:
            state["segment_geometry"] = self.segment_geometry

        return state
