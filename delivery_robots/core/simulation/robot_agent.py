import typing

import simpy

from ...config import (
    ROBOT_STATUS_IDLE,
    ROBOT_STATUS_MOVING_TO_PICKUP,
    ROBOT_STATUS_MOVING_TO_DROPOFF,
    SPEED_METERS_PER_SECOND,
    BATTERY_DRAIN_RATE,
    ROBOT_STATUS_MOVING_TO_CHARGE,
    ROBOT_STATUS_CHARGING,
    BATTERY_MAX,
    BATTERY_LOW,
    BATTERY_PROACTIVE,
    BATTERY_SAFETY_MARGIN,
    CHARGING_RATE_PERCENT_PER_MINUTE,
    W1_TRAVEL_COST_WEIGHT,
    W2_WAIT_TIME_WEIGHT,
    ORDER_STATUS_PENDING,
    ORDER_STATUS_ASSIGNED,
    ORDER_STATUS_IN_TRANSIT,
    ORDER_STATUS_DELIVERED,
    ROBOT_ORDER_CAPACITY,
)
from ..environment import edge_weight_with_traffic
from ...utils.route_analysis import (
    nearest_node_id,
    build_geometry_path,
    build_segment_geometry,
)
from ...algorithms import run_weighted_route_search
from ...utils.metrics import record_delivery_gap, record_battery_failure


class EmergencyChargingException(Exception):
    """Raised when the robot's battery falls below the safety-aware charging threshold."""

    pass


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
        self.geometry_path = []  # flat [{lat,lon},...] — for drawing
        self.segment_geometry = []  # [[{lat,lon},...], ...] — per-node-segment for interpolation

        # Battery could be implemented here; for now we simulate basic movement
        self.battery = BATTERY_MAX
        self.current_task = None
        self.charging_station_name: str | None = None

        # Start the lifecycle process
        self.action = env.process(self.run())

        # Task queue for orders
        self.task_queue = []
        self.capacity = ROBOT_ORDER_CAPACITY

    def _location_log_payload(self, location: dict | None) -> dict | None:
        if not isinstance(location, dict):
            return None
        try:
            lat = float(location["lat"])
            lon = float(location["lon"])
        except (KeyError, TypeError, ValueError):
            return None
        return {
            "lat": lat,
            "lon": lon,
            "name": location.get("name"),
            "category": location.get("category"),
        }

    def _record_completed_delivery(self, task: dict) -> None:
        pickup = self._location_log_payload(task.get("pickup"))
        dropoff = self._location_log_payload(task.get("dropoff"))
        if not pickup or not dropoff:
            return

        history_lock = self.app_state.get("history_lock")
        delivery_history = self.app_state.get("delivery_history")
        if delivery_history is not None:
            if history_lock is not None:
                with history_lock:
                    delivery_history.append([pickup["lat"], pickup["lon"]])
                    delivery_history.append([dropoff["lat"], dropoff["lon"]])
            else:
                delivery_history.append([pickup["lat"], pickup["lon"]])
                delivery_history.append([dropoff["lat"], dropoff["lon"]])

        if not self.app_state.get("persistent_log_enabled", False):
            return

        try:
            from ...utils.persistent_log import append_delivery_history

            payload = {
                "deliveryId": task.get("id"),
                "robotName": self.name,
                "pickup": pickup,
                "dropoff": dropoff,
                "createdAt": task.get("created_time"),
                "deliveredAt": self.env.now,
                "plannedCost": task.get("planned_cost"),
                "actualCost": task.get("actual_cost"),
                "planExecuteGap": task.get("plan_execute_gap"),
            }
            log_dir = self.app_state.get("persistent_log_dir")
            if log_dir:
                append_delivery_history(payload, log_dir=log_dir)
            else:
                append_delivery_history(payload)
        except Exception:
            return

    def assign_task(self, task):
        self.task_queue.append(task)
        if self.status == ROBOT_STATUS_IDLE:
            if self.action.is_alive and not self.action.triggered:
                self.action.interrupt()

    def run(self) -> typing.Generator:
        """Main robot agent process loop."""
        while True:
            # Check if battery is low (b_low = 30%)
            if self.battery < BATTERY_LOW:
                hub = self.select_optimal_hub()
                if hub:
                    yield from self.go_to_charge(hub)
                else:
                    yield self.env.timeout(10)
                continue

            if not self.task_queue:
                # Proactive charging check when IDLE
                if self.battery < BATTERY_PROACTIVE:
                    hub = self.select_optimal_hub()
                    if hub:
                        yield from self.go_to_charge(hub)
                        continue

                self.status = ROBOT_STATUS_IDLE
                self._emit_state()
                try:
                    # Wait indefinitely for a task
                    yield self.env.timeout(999999)
                except Exception:  # Catch Interrupt
                    pass

            if self.task_queue:
                # Double check if battery is low before taking a task
                if self.battery < BATTERY_LOW:
                    hub = self.select_optimal_hub()
                    if hub:
                        yield from self.go_to_charge(hub)
                    else:
                        yield self.env.timeout(10)
                    continue

                task = self.task_queue.pop(0)
                yield from self.execute_task(task)

    def execute_task(self, task: dict) -> typing.Generator:
        """Execute the full delivery task workflow (pickup -> dropoff).

        Args:
            task (dict): Dictionary representing the order details and routing paths.

        Returns:
            typing.Generator: A generator yielding SimPy timeout events.
        """
        if task.get("vrp_batch_orders"):
            yield from self.execute_vrp_batch(task)
            return

        # Initialize execution trace tracking
        gps_trace: list = [(self.lat, self.lon)]
        start_battery: float = self.battery
        start_time: float = self.env.now
        self.current_task = task
        self.charging_station_name = None

        order_manager = self.app_state.get("order_manager")
        if order_manager:
            order_manager.mark_assigned(task)
        else:
            task["status"] = ORDER_STATUS_ASSIGNED

        self.status = ROBOT_STATUS_MOVING_TO_PICKUP

        try:
            # 0. If this is a 3-leg task, go charge first
            if task.get("is_3_leg"):
                self.status = ROBOT_STATUS_MOVING_TO_CHARGE
                self.current_path = task.get("charge_path", [])
                self.geometry_path = task.get("charge_geometry_path", [])
                self.segment_geometry = task.get("charge_segment_geometry", [])
                self.path_index = 0
                hub = task.get("charging_station")
                hub_name = hub["name"] if hub else "Unknown Hub"
                self.route_target = f"Charging at {hub_name}"
                self.charging_station_name = hub_name
                self.segment_duration = 0
                self._emit_state()
                yield from self.traverse_path(
                    self.current_path, gps_trace, "charge_actual_cost"
                )

                # Charge the robot
                if hub:
                    yield from self.charge(hub)

            # Check safety threshold before starting pickup movement (skip if 3-leg since we just charged)
            if not task.get("is_3_leg") and self.battery < self.get_safety_threshold():
                raise EmergencyChargingException("Safety threshold violated")

            # 1. Move to pickup
            self.status = ROBOT_STATUS_MOVING_TO_PICKUP
            self.current_path = task["pickup_path"]
            self.geometry_path = task.get("pickup_geometry_path", [])
            self.segment_geometry = task.get("pickup_segment_geometry", [])
            self.path_index = 0
            self.route_target = "Pickup"
            self.segment_duration = 0
            self._emit_state()
            yield from self.traverse_path(
                self.current_path, gps_trace, "pickup_actual_cost"
            )

            # Arrive at pickup -> transition status to DELIVERING (moving_to_dropoff)
            self.status = ROBOT_STATUS_MOVING_TO_DROPOFF
            if order_manager:
                order_manager.mark_in_transit(task)
            else:
                task["status"] = ORDER_STATUS_IN_TRANSIT
            self.route_target = "Pickup (Loading)"
            self._emit_state()

            # 2. Pick up item (simulate a short delay)
            yield self.env.timeout(30)  # 30 sim seconds
            gps_trace.append((self.lat, self.lon))

            # Check safety threshold before starting dropoff movement
            if self.battery < self.get_safety_threshold():
                raise EmergencyChargingException("Safety threshold violated")

            # 3. Move to dropoff
            self.current_path = task["dropoff_path"]
            self.geometry_path = task.get("dropoff_geometry_path", [])
            self.segment_geometry = task.get("dropoff_segment_geometry", [])
            self.path_index = 0
            self.route_target = "Dropoff"
            self.segment_duration = 0
            self._emit_state()
            yield from self.traverse_path(
                self.current_path, gps_trace, "dropoff_actual_cost"
            )

            # 4. Drop off item
            yield self.env.timeout(30)
            gps_trace.append((self.lat, self.lon))

            if order_manager:
                order_manager.mark_delivered(task)
            else:
                task["status"] = ORDER_STATUS_DELIVERED

            from ...algorithms.base import ExecutionTrace

            actual_energy_consumed = start_battery - self.battery
            actual_travel_time = self.env.now - start_time

            task["execution_trace"] = ExecutionTrace(
                gps_coords=gps_trace,
                energy_consumed=actual_energy_consumed,
                travel_time=actual_travel_time,
            )

            # Calculate and store Plan-Execute Gap metrics
            planned_cost = task.get("pickup_planned_cost", 0.0) + task.get(
                "dropoff_planned_cost", 0.0
            )
            if task.get("is_3_leg"):
                planned_cost += task.get("charge_planned_cost", 0.0)

            actual_cost = (
                task.get("charge_actual_cost", 0.0)
                + task.get("pickup_actual_cost", 0.0)
                + task.get("dropoff_actual_cost", 0.0)
            )
            gap = actual_cost - planned_cost

            task["planned_cost"] = planned_cost
            task["actual_cost"] = actual_cost
            task["plan_execute_gap"] = gap

            metrics = self.app_state.get("metrics")
            metrics_lock = self.app_state.get("metrics_lock")
            if metrics is not None:
                if metrics_lock is not None:
                    with metrics_lock:
                        record_delivery_gap(metrics, gap)
                else:
                    record_delivery_gap(metrics, gap)

            self._record_completed_delivery(task)

            # DELIVERING -> IDLE / GOING_TO_CHARGE
            if self.battery < BATTERY_LOW:
                self.status = ROBOT_STATUS_MOVING_TO_CHARGE
            else:
                self.status = ROBOT_STATUS_IDLE

        except EmergencyChargingException:
            # Dynamic safety threshold violated! Return task to order queue
            if order_manager:
                order_manager.requeue_order(task)
            else:
                order_queue = self.app_state.get("order_queue")
                if order_queue is not None:
                    task["status"] = ORDER_STATUS_PENDING
                    order_queue.insert(0, task)

            metrics = self.app_state.get("metrics")
            metrics_lock = self.app_state.get("metrics_lock")
            if metrics is not None:
                if metrics_lock is not None:
                    with metrics_lock:
                        record_battery_failure(metrics)
                else:
                    record_battery_failure(metrics)

            self.status = ROBOT_STATUS_MOVING_TO_CHARGE
            self.charging_station_name = None
            self.current_path = []
            self.geometry_path = []
            self.segment_geometry = []
            self.route_target = None
            self.segment_duration = 0
            self.current_task = None
            self._emit_state()
            return
        except simpy.Interrupt as exc:
            if exc.cause == "reassignment":
                self.status = ROBOT_STATUS_IDLE
                self.charging_station_name = None
                self.current_path = []
                self.geometry_path = []
                self.segment_geometry = []
                self.route_target = None
                self.segment_duration = 0
                self.current_task = None
                self._emit_state()
                return
            else:
                raise exc

        self.current_path = []
        self.geometry_path = []
        self.segment_geometry = []
        self.route_target = None
        self.charging_station_name = None
        self.segment_duration = 0
        self.current_task = None
        self._emit_state()
        return

    def _batch_order_by_id(self, task: dict) -> dict:
        orders = task.get("vrp_batch_orders") or []
        return {str(order.get("id")): order for order in orders}

    def execute_vrp_batch(self, task: dict) -> typing.Generator:
        """Execute a VRP batch task with pickup/dropoff precedence."""
        orders = task.get("vrp_batch_orders") or []
        sequence = task.get("vrp_sequence") or []
        segments = task.get("vrp_segments") or []
        order_by_id = self._batch_order_by_id(task)
        order_manager = self.app_state.get("order_manager")

        self.current_task = task
        self.charging_station_name = None

        for order in orders:
            order["robot_name"] = self.name
            if order_manager:
                order_manager.mark_assigned(order)
            else:
                order["status"] = ORDER_STATUS_ASSIGNED

        try:
            for index, stop in enumerate(sequence):
                segment = segments[index] if index < len(segments) else {}
                stop_type = stop.get("type")
                order = order_by_id.get(str(stop.get("deliveryId")))
                if stop_type == "pickup":
                    self.status = ROBOT_STATUS_MOVING_TO_PICKUP
                    self.route_target = f"Pickup {stop.get('deliveryId')}"
                else:
                    self.status = ROBOT_STATUS_MOVING_TO_DROPOFF
                    self.route_target = f"Dropoff {stop.get('deliveryId')}"

                self.current_path = segment.get("path", [])
                self.geometry_path = segment.get("geometry_path", [])
                self.segment_geometry = segment.get("segment_geometry", [])
                self.path_index = 0
                self.segment_duration = 0
                self._emit_state()
                yield from self.traverse_path(self.current_path)

                if stop_type == "pickup":
                    if order:
                        if order_manager:
                            order_manager.mark_in_transit(order)
                        else:
                            order["status"] = ORDER_STATUS_IN_TRANSIT
                    self.route_target = f"Loaded {stop.get('deliveryId')}"
                    self._emit_state()
                    yield self.env.timeout(30)
                elif stop_type == "dropoff":
                    if order:
                        if order_manager:
                            order_manager.mark_delivered(order)
                        else:
                            order["status"] = ORDER_STATUS_DELIVERED
                        self._record_completed_delivery(order)
                    self.route_target = f"Delivered {stop.get('deliveryId')}"
                    self._emit_state()
                    yield self.env.timeout(30)
        except EmergencyChargingException:
            for order in orders:
                if order.get("status") != ORDER_STATUS_DELIVERED:
                    if order_manager:
                        order_manager.requeue_order(order)
                    else:
                        order["status"] = ORDER_STATUS_PENDING
                        order_queue = self.app_state.get("order_queue")
                        if order_queue is not None:
                            order_queue.insert(0, order)
            self.status = ROBOT_STATUS_MOVING_TO_CHARGE
            self.current_path = []
            self.geometry_path = []
            self.segment_geometry = []
            self.route_target = None
            self.current_task = None
            self._emit_state()
            return
        except simpy.Interrupt as exc:
            if exc.cause == "reassignment":
                self.status = ROBOT_STATUS_IDLE
                self.current_path = []
                self.geometry_path = []
                self.segment_geometry = []
                self.route_target = None
                self.current_task = None
                self._emit_state()
                return
            raise exc

        self.status = ROBOT_STATUS_MOVING_TO_CHARGE if self.battery < BATTERY_LOW else ROBOT_STATUS_IDLE
        self.current_path = []
        self.geometry_path = []
        self.segment_geometry = []
        self.route_target = None
        self.charging_station_name = None
        self.segment_duration = 0
        self.current_task = None
        self._emit_state()
        return

    def traverse_path(
        self,
        path_nodes: list,
        gps_trace: list | None = None,
        cost_key: str | None = None,
    ) -> typing.Generator:
        """Move along a sequence of node IDs.

        This method simulates physical movement of the robot along a given path,
        depleting battery based on physical distance (not traffic) and waiting
        according to traffic-adjusted segment durations.

        Args:
            path_nodes (list): The list of node IDs defining the routing path.
            gps_trace (list | None): Optional list to record traversed GPS coordinates.
            cost_key (str | None): Optional key to record traversed path costs.

        Returns:
            typing.Generator: A generator that yields SimPy timeout events.
        """
        from ...config import REPLANNING_THRESHOLD
        from ..environment import SnapFactory

        graph = self.app_state["road_graph"]
        if not graph or len(path_nodes) < 2:
            return

        # Dynamically determine phase from self.status
        phase = None
        if self.status == ROBOT_STATUS_MOVING_TO_PICKUP:
            phase = "pickup"
        elif self.status == ROBOT_STATUS_MOVING_TO_DROPOFF:
            phase = "dropoff"
        elif self.status == ROBOT_STATUS_MOVING_TO_CHARGE:
            phase = "charge"

        # Initialize actual cost key on task if needed
        if cost_key and self.current_task is not None:
            if cost_key not in self.current_task:
                self.current_task[cost_key] = 0.0

        # Dynamically populate planned cost and edge planned costs if missing (e.g. for unit tests)
        if phase and self.current_task is not None:
            if f"{phase}_edge_planned_costs" not in self.current_task:
                edge_planned_costs = []
                for u, v in zip(path_nodes[:-1], path_nodes[1:]):
                    edge_data = graph.get_edge_data(u, v)
                    if edge_data:
                        weight = edge_weight_with_traffic(
                            self.app_state, u, v, edge_data
                        )
                        edge_planned_costs.append(weight)
                    else:
                        edge_planned_costs.append(0.0)
                self.current_task[f"{phase}_edge_planned_costs"] = edge_planned_costs
                self.current_task[f"{phase}_planned_cost"] = sum(edge_planned_costs)

        i = 0
        while i < len(path_nodes) - 1:
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

                # Check if replanning is needed
                if phase and self.current_task is not None:
                    edge_planned_costs = self.current_task.get(
                        f"{phase}_edge_planned_costs", []
                    )
                    actual_cost_so_far = self.current_task.get(cost_key, 0.0)

                    # Remaining current cost (along current path nodes on active environment)
                    remaining_path = path_nodes[i:]
                    remaining_current_cost = 0.0
                    for u, v in zip(remaining_path[:-1], remaining_path[1:]):
                        ed = graph.get_edge_data(u, v)
                        if ed:
                            remaining_current_cost += edge_weight_with_traffic(
                                self.app_state, u, v, ed
                            )

                    # Compute projected gap
                    projected_gap = (
                        actual_cost_so_far + remaining_current_cost
                    ) - self.current_task.get(f"{phase}_planned_cost", 0.0)

                    if projected_gap > REPLANNING_THRESHOLD:
                        # Trigger replanning!
                        snap_graph = SnapFactory.create_snapshot(
                            self.app_state, self.env.now
                        )
                        destination_node = path_nodes[-1]
                        dest_node_data = snap_graph.nodes[destination_node]
                        destination_lat = dest_node_data["y"]
                        destination_lon = dest_node_data["x"]

                        def weight_fn(u, v, d):
                            return snap_graph.get_edge_weight(u, v, d)

                        try:
                            route_result = run_weighted_route_search(
                                snap_graph,
                                from_node,
                                destination_node,
                                destination_lat,
                                destination_lon,
                                weight_fn,
                                "astar",
                                skip_diagnostics=True,
                            )
                            new_path = route_result.path

                            # Log the replanning trigger
                            api_logs_lock = self.app_state.get("api_logs_lock")
                            api_logs = self.app_state.get("api_logs")
                            if api_logs is not None:
                                entry = {
                                    "ts": round(self.env.now),
                                    "message": f"Robot {self.name} triggered replanning for {phase}. Projected gap: {projected_gap:.2f} > threshold: {REPLANNING_THRESHOLD}.",
                                    "level": "info",
                                    "source": "simulation",
                                }
                                if api_logs_lock is not None:
                                    with api_logs_lock:
                                        api_logs.append(entry)
                                else:
                                    api_logs.append(entry)

                            # If a new path is found, update the task's path and planned costs
                            if new_path and len(new_path) >= 2:
                                # Re-calculate planned costs for the new remaining path on snap_graph
                                remaining_new_edge_costs = [
                                    snap_graph.get_edge_weight(
                                        u, v, snap_graph.get_edge_data(u, v)
                                    )
                                    for u, v in zip(new_path[:-1], new_path[1:])
                                ]

                                # Update path_nodes list dynamically (the while loop is controlled by len(path_nodes))
                                path_nodes = path_nodes[:i] + new_path
                                self.current_path = path_nodes

                                # Update the task path keys and planned cost info
                                self.current_task[f"{phase}_path"] = path_nodes
                                self.current_task[f"{phase}_edge_planned_costs"] = (
                                    edge_planned_costs[:i] + remaining_new_edge_costs
                                )
                                self.current_task[f"{phase}_planned_cost"] = sum(
                                    self.current_task[f"{phase}_edge_planned_costs"]
                                )

                                # Update geometry paths so the front-end renders the new path
                                self.geometry_path = build_geometry_path(
                                    graph, self.current_path
                                )
                                self.segment_geometry = build_segment_geometry(
                                    graph, self.current_path
                                )
                                self.current_task[f"{phase}_geometry_path"] = (
                                    self.geometry_path
                                )
                                self.current_task[f"{phase}_segment_geometry"] = (
                                    self.segment_geometry
                                )

                                # Re-evaluate from_node and to_node for the next traversal step
                                from_node = path_nodes[i]
                                to_node = path_nodes[i + 1]
                                edge_data = graph.get_edge_data(from_node, to_node)
                        except Exception:
                            # If route search fails, keep using current path
                            pass

                # Calculate time to traverse the edge
                weight = edge_weight_with_traffic(
                    self.app_state, from_node, to_node, edge_data
                )
                if cost_key and self.current_task is not None:
                    self.current_task[cost_key] = (
                        self.current_task.get(cost_key, 0.0) + weight
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
                        default=0.0,
                    )

                battery_cost = (
                    edge_length / SPEED_METERS_PER_SECOND
                ) * BATTERY_DRAIN_RATE
                self.battery = max(0.0, self.battery - battery_cost)

                if self.status in (
                    ROBOT_STATUS_MOVING_TO_PICKUP,
                    ROBOT_STATUS_MOVING_TO_DROPOFF,
                ):
                    if self.battery < self.get_safety_threshold():
                        raise EmergencyChargingException("Safety threshold violated")

                yield self.env.timeout(self.segment_duration)
            else:
                pass
            i += 1

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

    def get_path_battery_cost(self, path: list, start_idx: int = 0) -> float:
        """Estimate the battery cost of a path from a given start index.

        Args:
            path (list): The list of node IDs defining the routing path.
            start_idx (int): The starting node index of the path to estimate from.

        Returns:
            float: Total estimated battery percentage depleted.
        """
        graph = self.app_state["road_graph"]
        if not graph or len(path) < 2 or start_idx >= len(path) - 1:
            return 0.0

        total_battery_cost = 0.0
        for i in range(start_idx, len(path) - 1):
            from_node = path[i]
            to_node = path[i + 1]
            edge_data = graph.get_edge_data(from_node, to_node)
            if edge_data:
                if "length" in edge_data:
                    edge_length = edge_data.get("length", 0.0)
                else:
                    edge_length = min(
                        (data.get("length", 0.0) for data in edge_data.values()),
                        default=0.0,
                    )
                battery_cost = (
                    edge_length / SPEED_METERS_PER_SECOND
                ) * BATTERY_DRAIN_RATE
                total_battery_cost += battery_cost
        return total_battery_cost

    def is_path_feasible(self, path: list) -> bool:
        """Evaluate if the robot has enough energy to complete the given path.

        Estimates the total battery cost of traversing the path based on physical
        distance and base drain rate, and compares it against the current battery level.

        Args:
            path (list): The list of node IDs defining the routing path.

        Returns:
            bool: True if the current battery is sufficient to cover the total
                estimated battery cost, False otherwise.
        """
        return self.battery >= self.get_path_battery_cost(path)

    def get_safety_threshold(self) -> float:
        """Calculate the dynamic safety-aware battery threshold.

        Safety-Aware Threshold = B_complete_current + B_to_nearest_hub + B_safety_margin

        Returns:
            float: The dynamic safety threshold percentage.
        """
        b_complete_current = 0.0
        if (
            self.status == ROBOT_STATUS_MOVING_TO_PICKUP
            and hasattr(self, "current_task")
            and self.current_task
        ):
            b_complete_current = self.get_path_battery_cost(
                self.current_task.get("pickup_path", []), self.path_index
            ) + self.get_path_battery_cost(self.current_task.get("dropoff_path", []))
        elif (
            self.status == ROBOT_STATUS_MOVING_TO_DROPOFF
            and hasattr(self, "current_task")
            and self.current_task
        ):
            b_complete_current = self.get_path_battery_cost(
                self.current_task.get("dropoff_path", []), self.path_index
            )

        target_lat, target_lon = self.lat, self.lon
        graph = self.app_state.get("road_graph")
        final_node = None

        if hasattr(self, "current_task") and self.current_task and graph:
            dropoff_path = self.current_task.get("dropoff_path", [])
            if dropoff_path:
                final_node = dropoff_path[-1]
                if final_node in graph.nodes:
                    target_lat = graph.nodes[final_node]["y"]
                    target_lon = graph.nodes[final_node]["x"]

        task_id = (
            self.current_task.get("id")
            if (hasattr(self, "current_task") and self.current_task)
            else None
        )
        cache_key = (
            (task_id, final_node)
            if (task_id is not None and final_node is not None)
            else None
        )

        if (
            cache_key is not None
            and hasattr(self, "_cached_safety_key")
            and self._cached_safety_key == cache_key
            and hasattr(self, "_cached_b_to_nearest_hub")
            and self._cached_b_to_nearest_hub is not None
        ):
            b_to_nearest_hub = self._cached_b_to_nearest_hub
        else:
            hubs = self.app_state.get("charging_stations", [])
            from ...utils.geo import haversine_distance

            nearest_hub = None
            min_dist = float("inf")
            for hub in hubs:
                dist = haversine_distance(
                    target_lat, target_lon, hub["lat"], hub["lon"]
                )
                if dist < min_dist:
                    min_dist = dist
                    nearest_hub = hub

            b_to_nearest_hub = 0.0
            if nearest_hub and graph:
                try:
                    dest_node = nearest_node_id(
                        graph, target_lat, target_lon, self.app_state
                    )
                    hub_node = nearest_node_id(
                        graph, nearest_hub["lat"], nearest_hub["lon"], self.app_state
                    )

                    def weight_fn(u, v, d):
                        return edge_weight_with_traffic(self.app_state, u, v, d)

                    route_result = run_weighted_route_search(
                        graph,
                        dest_node,
                        hub_node,
                        nearest_hub["lat"],
                        nearest_hub["lon"],
                        weight_fn,
                        "astar",
                        skip_diagnostics=True,
                    )
                    b_to_nearest_hub = self.get_path_battery_cost(route_result.path)
                except Exception:
                    b_to_nearest_hub = (
                        min_dist / SPEED_METERS_PER_SECOND
                    ) * BATTERY_DRAIN_RATE

            if cache_key is not None:
                self._cached_safety_key = cache_key
                self._cached_b_to_nearest_hub = b_to_nearest_hub

        return b_complete_current + b_to_nearest_hub + BATTERY_SAFETY_MARGIN

    def select_optimal_hub(self) -> dict | None:
        """Select the optimal charging station (hub) h* to minimize travel cost and wait time.

        h* = argmin_{h in H} [ w1 * TravelCost(r_i, h) + w2 * WaitTime(h) ]

        Returns:
            dict | None: The optimal charging station dict, or None if no stations exist.
        """
        hubs = self.app_state.get("charging_stations", [])
        if not hubs:
            return None

        graph = self.app_state.get("road_graph")
        if not graph:
            return hubs[0]

        from ...utils.geo import haversine_distance

        best_hub = None
        best_cost = float("inf")

        robot_node = nearest_node_id(graph, self.lat, self.lon, self.app_state)
        avg_charge_time = (
            (BATTERY_MAX - BATTERY_LOW) / CHARGING_RATE_PERCENT_PER_MINUTE
        ) * 60.0

        for hub in hubs:
            travel_cost = 0.0
            try:
                hub_node = nearest_node_id(
                    graph, hub["lat"], hub["lon"], self.app_state
                )

                def weight_fn(u, v, d):
                    return edge_weight_with_traffic(self.app_state, u, v, d)

                route_result = run_weighted_route_search(
                    graph,
                    robot_node,
                    hub_node,
                    hub["lat"],
                    hub["lon"],
                    weight_fn,
                    "astar",
                    skip_diagnostics=True,
                )
                total_weight = 0.0
                path = route_result.path
                for i in range(len(path) - 1):
                    edge_data = graph.get_edge_data(path[i], path[i + 1])
                    if edge_data:
                        total_weight += edge_weight_with_traffic(
                            self.app_state, path[i], path[i + 1], edge_data
                        )
                travel_cost = total_weight / SPEED_METERS_PER_SECOND
            except Exception:
                dist = haversine_distance(self.lat, self.lon, hub["lat"], hub["lon"])
                travel_cost = dist / SPEED_METERS_PER_SECOND

            hub_resources = self.app_state.get("hub_resources", {})
            resource = hub_resources.get(hub["name"])

            wait_time = 0.0
            if resource:
                # Number of robots waiting or charging at the hub
                robots_charging_or_waiting = resource.count + len(resource.queue)
                wait_time = robots_charging_or_waiting * avg_charge_time

            cost = W1_TRAVEL_COST_WEIGHT * travel_cost + W2_WAIT_TIME_WEIGHT * wait_time

            if cost < best_cost:
                best_cost = cost
                best_hub = hub

        return best_hub

    def go_to_charge(self, station: dict) -> typing.Generator:
        """Move the robot to a charging station, wait in queue if needed, and charge to 100%.

        Args:
            station (dict): Dictionary representing the destination hub.

        Yields:
            typing.Generator: A generator yielding SimPy events.
        """
        graph = self.app_state["road_graph"]
        self.status = ROBOT_STATUS_MOVING_TO_CHARGE
        self.route_target = f"Charging at {station['name']}"
        self.charging_station_name = station["name"]
        self.path_index = 0

        start_node = nearest_node_id(graph, self.lat, self.lon, self.app_state)
        hub_node = nearest_node_id(
            graph, station["lat"], station["lon"], self.app_state
        )

        def weight_fn(u, v, d):
            return edge_weight_with_traffic(self.app_state, u, v, d)

        try:
            route_result = run_weighted_route_search(
                graph,
                start_node,
                hub_node,
                station["lat"],
                station["lon"],
                weight_fn,
                "astar",
                skip_diagnostics=True,
            )
            self.current_path = route_result.path
            self.geometry_path = build_geometry_path(graph, self.current_path)
            self.segment_geometry = build_segment_geometry(graph, self.current_path)
            yield from self.traverse_path(self.current_path)
        except Exception:
            # If pathfinding fails, warp/teleport to the charging station node to prevent simulation lock
            self.lat = station["lat"]
            self.lon = station["lon"]
            self._emit_state()

        yield from self.charge(station)
        return

    def charge(self, station: dict) -> typing.Generator:
        """Queue up for free charging spots and charge the battery.

        Args:
            station (dict): Dictionary representing the target charging station.

        Yields:
            typing.Generator: A generator yielding SimPy events.
        """
        self.status = ROBOT_STATUS_CHARGING
        self.route_target = f"Charging at {station['name']}"
        self.charging_station_name = station["name"]
        self.current_path = []
        self.geometry_path = []
        self.segment_geometry = []
        self._emit_state()

        hub_resources = self.app_state.get("hub_resources", {})
        resource = hub_resources.get(station["name"])

        r_charge = (
            CHARGING_RATE_PERCENT_PER_MINUTE / 60.0
        )  # converted to percent per second

        if resource:
            # Determine priority if it is a PriorityResource (lower battery = higher priority)
            if isinstance(resource, simpy.PriorityResource):
                req = resource.request(priority=int(self.battery))
            else:
                req = resource.request()

            with req:
                yield req
                b_0 = self.battery
                t_0 = self.env.now
                self.status = ROBOT_STATUS_CHARGING
                self.route_target = f"Charging at {station['name']}"
                self._emit_state()

                while self.battery < BATTERY_MAX:
                    yield self.env.timeout(1)
                    delta_t = self.env.now - t_0
                    self.battery = min(BATTERY_MAX, b_0 + r_charge * delta_t)
                    self._emit_state()
        else:
            b_0 = self.battery
            t_0 = self.env.now
            while self.battery < BATTERY_MAX:
                yield self.env.timeout(1)
                delta_t = self.env.now - t_0
                self.battery = min(BATTERY_MAX, b_0 + r_charge * delta_t)
                self._emit_state()

        self.status = ROBOT_STATUS_IDLE
        self.route_target = None
        self.charging_station_name = None
        self._emit_state()
        return

    def _emit_state(self):
        # Notify the manager/frontend of a state change
        if self.on_state_change:
            self.on_state_change(self.get_state())

    def get_remaining_charge_time(self) -> float:
        """Calculate the remaining time required to reach full charge (100%).

        Args:
            None

        Returns:
            float: Remaining charge time in simulation seconds, or 0.0 if not charging.
        """
        if self.status != ROBOT_STATUS_CHARGING:
            return 0.0
        r_charge = CHARGING_RATE_PERCENT_PER_MINUTE / 60.0
        return max(0.0, (BATTERY_MAX - self.battery) / r_charge)

    def get_state(self):
        active_orders = []
        if self.current_task and self.current_task.get("vrp_batch_orders"):
            active_orders.extend(
                {
                    "id": order.get("id"),
                    "status": order.get("status"),
                    "pickup": order.get("pickup", {}).get("name"),
                    "dropoff": order.get("dropoff", {}).get("name"),
                }
                for order in self.current_task.get("vrp_batch_orders", [])
            )
        elif self.current_task:
            active_orders.append(
                {
                    "id": self.current_task.get("id"),
                    "status": self.current_task.get("status"),
                    "pickup": self.current_task.get("pickup", {}).get("name"),
                    "dropoff": self.current_task.get("dropoff", {}).get("name"),
                }
            )
        active_orders.extend(
            {
                "id": task.get("id"),
                "status": task.get("status"),
                "pickup": task.get("pickup", {}).get("name"),
                "dropoff": task.get("dropoff", {}).get("name"),
            }
            for task in self.task_queue
        )

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
            "charging_station": getattr(self, "charging_station_name", None),
            "remaining_charge_time": self.get_remaining_charge_time(),
            "capacity": self.capacity,
            "current_load": len(active_orders),
            "active_orders": active_orders[: self.capacity],
        }

        if self.geometry_path:
            state["geometry_path"] = self.geometry_path

        if self.segment_geometry:
            state["segment_geometry"] = self.segment_geometry

        return state
