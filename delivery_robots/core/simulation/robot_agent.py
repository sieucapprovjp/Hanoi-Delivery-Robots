import typing
from ...config import (
    ROBOT_STATUS_IDLE,
    ROBOT_STATUS_MOVING_TO_PICKUP,
    ROBOT_STATUS_MOVING_TO_DROPOFF,
    SPEED_METERS_PER_SECOND,
    BATTERY_DRAIN_RATE,
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

    def execute_task(self, task: dict) -> typing.Generator:
        # Initialize execution trace tracking
        gps_trace: list = [(self.lat, self.lon)]
        start_battery: float = self.battery
        start_time: float = self.env.now

        # 1. Move to pickup
        self.status = ROBOT_STATUS_MOVING_TO_PICKUP
        self.current_path = task["pickup_path"]
        self.geometry_path = task.get("pickup_geometry_path", [])
        self.segment_geometry = task.get("pickup_segment_geometry", [])
        self.path_index = 0
        self.route_target = "Pickup"
        self.segment_duration = 0
        self._emit_state()
        yield from self.traverse_path(self.current_path, gps_trace)

        # 2. Pick up item (simulate a short delay)
        yield self.env.timeout(30)  # 30 sim seconds
        gps_trace.append((self.lat, self.lon))

        # 3. Move to dropoff
        self.status = ROBOT_STATUS_MOVING_TO_DROPOFF
        self.current_path = task["dropoff_path"]
        self.geometry_path = task.get("dropoff_geometry_path", [])
        self.segment_geometry = task.get("dropoff_segment_geometry", [])
        self.path_index = 0
        self.route_target = "Dropoff"
        self.segment_duration = 0
        self._emit_state()
        yield from self.traverse_path(self.current_path, gps_trace)

        # 4. Drop off item
        yield self.env.timeout(30)
        gps_trace.append((self.lat, self.lon))

        from ...algorithms.base import ExecutionTrace
        actual_energy_consumed = start_battery - self.battery
        actual_travel_time = self.env.now - start_time

        task["execution_trace"] = ExecutionTrace(
            gps_coords=gps_trace,
            energy_consumed=actual_energy_consumed,
            travel_time=actual_travel_time,
        )

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

    def traverse_path(self, path_nodes: list, gps_trace: list | None = None) -> typing.Generator:
        """Move along a sequence of node IDs.

        This method simulates physical movement of the robot along a given path,
        depleting battery based on physical distance (not traffic) and waiting
        according to traffic-adjusted segment durations.

        Args:
            path_nodes (list): The list of node IDs defining the routing path.
            gps_trace (list | None): Optional list to record traversed GPS coordinates.

        Returns:
            typing.Generator: A generator that yields SimPy timeout events.
        """
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
                if gps_trace is not None:
                    gps_trace.append((self.lat, self.lon))

                # Calculate time to traverse
                weight = edge_weight_with_traffic(
                    self.app_state, from_node, to_node, edge_data
                )
                self.segment_duration = weight / SPEED_METERS_PER_SECOND

                # Emit state BEFORE yielding. Frontend knows we are at `i` and moving to `i+1`
                self._emit_state()

                # Calculate battery cost using physical length: BatteryCost(e) = Length(e) / v * r_drain
                if "length" in edge_data:
                    edge_length = edge_data.get("length", 0.0)
                else:
                    edge_length = min(
                        (data.get("length", 0.0) for data in edge_data.values()),
                        default=0.0
                    )

                battery_cost = (edge_length / SPEED_METERS_PER_SECOND) * BATTERY_DRAIN_RATE
                self.battery = max(0.0, self.battery - battery_cost)

                yield self.env.timeout(self.segment_duration)

        # Final node
        final_node = path_nodes[-1]
        self.lat = graph.nodes[final_node]["y"]
        self.lon = graph.nodes[final_node]["x"]
        if gps_trace is not None:
            gps_trace.append((self.lat, self.lon))
        self.path_index = len(path_nodes) - 1
        self.segment_duration = 0
        self._emit_state()
        return

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
