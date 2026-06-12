import simpy
import random
import threading
from typing import Generator
from .robot_agent import RobotAgent
from ...algorithms import run_assignment
from ...algorithms.assignment import compute_battery_cost
from ...algorithms.base import AssignmentInput
from ..event_bus import Event, EventType
from ..data import LOCATIONS, INITIAL_ROBOTS
from ..environment import get_simulation_time, get_rush_hour_multiplier, SnapFactory
from ...config import (
    ORDER_STATUS_PENDING,
    RUSH_HOUR_INACTIVE_LABEL,
    DISPATCH_ALPHA,
    DISPATCH_BETA,
    DISPATCH_GAMMA,
    DISPATCH_LAMBDA,
    ROBOT_STATUS_MOVING_TO_PICKUP,
    REASSIGN_PENALTY,
    MAX_REASSIGN_LIMIT,
    REASSIGN_COOLDOWN,
)

from ...utils import Profiler, profile_time, profile_block


class SimulatorManager:
    def __init__(
        self,
        socketio,
        app_state,
        nearest_node_id,
        run_weighted_route_search,
        edge_weight_with_traffic,
        build_route_geometry,
    ):
        self.socketio = socketio
        self.app_state = app_state
        self.nearest_node_id = nearest_node_id
        self.run_weighted_route_search = run_weighted_route_search
        self.edge_weight_with_traffic = edge_weight_with_traffic
        self.build_route_geometry = build_route_geometry

        self.env = simpy.Environment()
        self.robots = []
        self.running = False
        self._thread = None
        self._stop_event = threading.Event()

        # Order dispatcher queue
        from .order_manager import OrderManager

        self.order_manager = OrderManager(self.env, self.app_state, self.socketio)
        self.order_queue = self.order_manager.order_queue
        self.app_state["order_queue"] = self.order_queue
        self.scenario_config = None

    def initialize_robots(self):
        self.robots = []
        initial_starts = LOCATIONS[: len(INITIAL_ROBOTS)]

        graph = self.app_state.get("road_graph")

        for i, r_data in enumerate(INITIAL_ROBOTS):
            start = initial_starts[i] if i < len(initial_starts) else LOCATIONS[0]

            lat, lon = start["lat"], start["lon"]
            if graph:
                node_id = self.nearest_node_id(graph, lat, lon)
                if node_id and node_id in graph.nodes:
                    lat = graph.nodes[node_id]["y"]
                    lon = graph.nodes[node_id]["x"]

            agent = RobotAgent(
                env=self.env,
                robot_id=i,
                name=r_data["name"],
                color=r_data["color"],
                start_lat=lat,
                start_lon=lon,
                app_state=self.app_state,
                on_state_change=self.emit_robot_state,
            )
            self.robots.append(agent)

        self.app_state["robots"] = self.robots

        # Create SimPy resources for charging stations
        self.hub_resources = {}
        hubs = self.app_state.get("charging_stations", [])
        for hub in hubs:
            capacity = hub["spots"]
            if capacity % 2 == 1:
                self.hub_resources[hub["name"]] = simpy.PriorityResource(
                    self.env, capacity=capacity
                )
            else:
                self.hub_resources[hub["name"]] = simpy.Resource(
                    self.env, capacity=capacity
                )
        self.app_state["hub_resources"] = self.hub_resources

    def emit_robot_state(self, state):
        # We send to a specific websocket event
        self.socketio.emit("robot_state_update", state)

    def emit_system_event(self, message):
        self.socketio.emit("system_event", {"message": message})

    def emit_clock_update(self):
        hours, minutes, seconds = get_simulation_time(self.app_state)
        rush_multiplier, rush_name = get_rush_hour_multiplier(self.app_state)
        is_rush_hour = rush_name != RUSH_HOUR_INACTIVE_LABEL

        self.socketio.emit(
            "clock_update",
            {
                "time": {
                    "display": f"{hours:02d}:{minutes:02d}:{seconds:02d}",
                },
                "rushHour": {
                    "isActive": is_rush_hour,
                    "multiplier": round(rush_multiplier, 2),
                },
                "simulationSpeed": self.app_state.get("simulation_speed", 60),
            },
        )

    def start(self) -> None:
        """Start the simulation loop and processes.

        If a scenario config is loaded, apply its seed and parameters.
        """
        if self.running:
            return

        # Apply seed and params if scenario config is present
        if self.scenario_config:
            if self.scenario_config.seed is not None:
                random.seed(self.scenario_config.seed)
                try:
                    import numpy as np

                    np.random.seed(self.scenario_config.seed)
                except ImportError:
                    pass
            if self.scenario_config.params:
                for key, val in self.scenario_config.params.items():
                    self.app_state[key] = val

        if not self.robots:
            self.initialize_robots()

        self.running = True
        self._stop_event.clear()

        # Start background processes in SimPy
        self.env.process(self._order_generator_process())
        self.env.process(self._dispatcher_process())

        if self.scenario_config and self.scenario_config.events:
            self.env.process(self._scenario_injector_process())

        self.app_state["event_bus"].publish(
            Event(EventType.SIM_STARTED, sim_time=self.env.now)
        )

        self._thread = self.socketio.start_background_task(self._run_loop)
        self.emit_system_event("Simulation started")

    def pause(self):
        self.running = False
        self._stop_event.set()
        self.app_state["event_bus"].publish(
            Event(EventType.SIM_PAUSED, sim_time=self.env.now)
        )
        self.emit_system_event("Simulation paused")

    def reset(self):
        self.pause()
        self.env = simpy.Environment()
        from .order_manager import OrderManager

        self.order_manager = OrderManager(self.env, self.app_state, self.socketio)
        self.order_queue = self.order_manager.order_queue
        self.app_state["order_queue"] = self.order_queue
        self.initialize_robots()

        # Broadcast initial states
        for robot in self.robots:
            self.emit_robot_state(robot.get_state())
        self.app_state["event_bus"].publish(Event(EventType.SIM_RESET, sim_time=0.0))
        self.emit_system_event("Simulation reset")

    def _generate_random_location(self):
        # Simple random choice from LOCATIONS
        return random.choice(LOCATIONS)

    def _order_generator_process(self):
        while True:
            # Generate a new order every 1 to 3 minutes of simulation time
            delay = random.uniform(60, 180)
            yield self.env.timeout(delay)

            pickup = self._generate_random_location()
            dropoff = self._generate_random_location()

            while pickup == dropoff:
                dropoff = self._generate_random_location()

            task = {
                "id": f"ORDER-{int(self.env.now)}",
                "pickup": pickup,
                "dropoff": dropoff,
            }
            self.order_manager.add_order(task)
            self.emit_system_event(
                f"New order {task['id']} generated from {pickup['name']} to {dropoff['name']}"
            )

    def _dispatcher_process(self):
        while True:
            # Dispatch checks every 10 seconds of sim time
            yield self.env.timeout(10)

            idle_robots = [r for r in self.robots if r.status == "idle"]
            if not idle_robots:
                continue

            graph = self.app_state.get("road_graph")
            if not graph:
                continue

            try:
                snap_graph = SnapFactory.create_snapshot(self.app_state, self.env.now)
            except Exception as e:
                self.emit_system_event(f"Snapshot creation failed: {e}")
                continue

            # Check for re-assignments of active orders (Ref: algo S2.3)
            active_robots_going_to_pickup = [
                r
                for r in self.robots
                if r.status == ROBOT_STATUS_MOVING_TO_PICKUP
                and r.current_task is not None
            ]
            if active_robots_going_to_pickup:
                import networkx as nx

                def weight_fn(u, v, d):
                    return snap_graph.get_edge_weight(u, v, d)

                for r_old in list(active_robots_going_to_pickup):
                    task = r_old.current_task
                    if not task:
                        continue

                    # Check anti-chatter constraints
                    reassign_count = task.get("reassign_count", 0)
                    last_reassign_time = task.get("last_reassign_time")

                    if reassign_count >= MAX_REASSIGN_LIMIT:
                        continue
                    if (
                        last_reassign_time is not None
                        and (self.env.now - last_reassign_time) < REASSIGN_COOLDOWN
                    ):
                        continue

                    # Calculate remaining travel cost for r_old to reach pickup
                    remaining_path = r_old.current_path[r_old.path_index :]
                    d_old_pickup = 0.0
                    if remaining_path and len(remaining_path) >= 2:
                        for u, v in zip(remaining_path[:-1], remaining_path[1:]):
                            edge_data = snap_graph.get_edge_data(u, v)
                            if edge_data:
                                d_old_pickup += snap_graph.get_edge_weight(
                                    u, v, edge_data
                                )
                    else:
                        continue

                    best_candidate = None
                    min_d_new_pickup = float("inf")
                    best_pickup_path = None
                    best_dropoff_path = None
                    best_charge_path = None
                    best_hub = None
                    is_3_leg_for_best = False

                    # Evaluate each idle robot as a candidate r_new
                    for r_new in idle_robots:
                        r_new_node = self.nearest_node_id(
                            snap_graph, r_new.lat, r_new.lon
                        )
                        pickup_node = self.nearest_node_id(
                            snap_graph, task["pickup"]["lat"], task["pickup"]["lon"]
                        )
                        delivery_node = self.nearest_node_id(
                            snap_graph, task["dropoff"]["lat"], task["dropoff"]["lon"]
                        )

                        try:
                            # Standard routing from r_new to pickup
                            pickup_result = self.run_weighted_route_search(
                                snap_graph,
                                r_new_node,
                                pickup_node,
                                task["pickup"]["lat"],
                                task["pickup"]["lon"],
                                weight_fn,
                                "astar",
                            )
                            pickup_path = pickup_result.path
                            pickup_cost = pickup_result.planned_cost

                            # Standard routing from pickup to dropoff
                            dropoff_result = self.run_weighted_route_search(
                                snap_graph,
                                pickup_node,
                                delivery_node,
                                task["dropoff"]["lat"],
                                task["dropoff"]["lon"],
                                weight_fn,
                                "astar",
                            )
                            dropoff_path = dropoff_result.path
                            dropoff_cost = dropoff_result.planned_cost
                        except nx.NetworkXNoPath:
                            continue

                        # Battery check: does r_new have enough battery for direct delivery?
                        battery_cost = compute_battery_cost(
                            snap_graph, pickup_path
                        ) + compute_battery_cost(snap_graph, dropoff_path)

                        is_3_leg = False
                        charge_path = None
                        hub = None

                        if r_new.battery < battery_cost:
                            # 3-leg route required for r_new
                            hub = r_new.select_optimal_hub()
                            if not hub:
                                continue

                            hub_node = self.nearest_node_id(
                                snap_graph, hub["lat"], hub["lon"]
                            )
                            try:
                                # Leg 1: r_new -> Hub
                                charge_result = self.run_weighted_route_search(
                                    snap_graph,
                                    r_new_node,
                                    hub_node,
                                    hub["lat"],
                                    hub["lon"],
                                    weight_fn,
                                    "astar",
                                )
                                # Leg 2: Hub -> Pickup
                                pickup_result = self.run_weighted_route_search(
                                    snap_graph,
                                    hub_node,
                                    pickup_node,
                                    task["pickup"]["lat"],
                                    task["pickup"]["lon"],
                                    weight_fn,
                                    "astar",
                                )
                                charge_path = charge_result.path
                                pickup_path = pickup_result.path
                                d_new_pickup = (
                                    charge_result.planned_cost
                                    + pickup_result.planned_cost
                                )
                                is_3_leg = True
                            except nx.NetworkXNoPath:
                                continue
                        else:
                            d_new_pickup = pickup_cost

                        # Trigger check: d(r_new, pickup) + penalty_reassign < d(r_old, pickup)
                        if d_new_pickup + REASSIGN_PENALTY < d_old_pickup:
                            if d_new_pickup < min_d_new_pickup:
                                min_d_new_pickup = d_new_pickup
                                best_candidate = r_new
                                best_pickup_path = pickup_path
                                best_dropoff_path = dropoff_path
                                best_charge_path = charge_path
                                best_hub = hub
                                is_3_leg_for_best = is_3_leg
                                best_pickup_cost = pickup_cost
                                best_dropoff_cost = dropoff_cost
                                best_charge_cost = (
                                    charge_result.planned_cost if is_3_leg else 0.0
                                )

                    if best_candidate:
                        # Reassign!
                        # Cancel task for old robot
                        r_old.action.interrupt(cause="reassignment")

                        # Update task info
                        task["reassign_count"] = reassign_count + 1
                        task["last_reassign_time"] = self.env.now
                        task["is_3_leg"] = is_3_leg_for_best
                        task["pickup_path"] = best_pickup_path
                        task["dropoff_path"] = best_dropoff_path

                        task["pickup_planned_cost"] = best_pickup_cost
                        task["dropoff_planned_cost"] = best_dropoff_cost
                        task["pickup_edge_planned_costs"] = [
                            snap_graph.get_edge_weight(
                                u, v, snap_graph.get_edge_data(u, v)
                            )
                            for u, v in zip(best_pickup_path[:-1], best_pickup_path[1:])
                        ]
                        task["dropoff_edge_planned_costs"] = [
                            snap_graph.get_edge_weight(
                                u, v, snap_graph.get_edge_data(u, v)
                            )
                            for u, v in zip(
                                best_dropoff_path[:-1], best_dropoff_path[1:]
                            )
                        ]

                        pickup_geom_path, pickup_seg_geom = self.build_route_geometry(
                            snap_graph, best_pickup_path
                        )
                        task["pickup_geometry_path"] = pickup_geom_path
                        task["pickup_segment_geometry"] = pickup_seg_geom

                        dropoff_geom_path, dropoff_seg_geom = self.build_route_geometry(
                            snap_graph, best_dropoff_path
                        )
                        task["dropoff_geometry_path"] = dropoff_geom_path
                        task["dropoff_segment_geometry"] = dropoff_seg_geom

                        if is_3_leg_for_best:
                            task["charging_station"] = best_hub
                            task["charge_path"] = best_charge_path
                            task["charge_planned_cost"] = best_charge_cost
                            task["charge_edge_planned_costs"] = [
                                snap_graph.get_edge_weight(
                                    u, v, snap_graph.get_edge_data(u, v)
                                )
                                for u, v in zip(
                                    best_charge_path[:-1], best_charge_path[1:]
                                )
                            ]
                            charge_geom_path, charge_seg_geom = (
                                self.build_route_geometry(snap_graph, best_charge_path)
                            )
                            task["charge_geometry_path"] = charge_geom_path
                            task["charge_segment_geometry"] = charge_seg_geom
                        else:
                            task.pop("charging_station", None)
                            task.pop("charge_path", None)
                            task.pop("charge_geometry_path", None)
                            task.pop("charge_segment_geometry", None)
                            task.pop("charge_planned_cost", None)
                            task.pop("charge_edge_planned_costs", None)

                        task["robot_name"] = best_candidate.name
                        self.order_manager.mark_assigned(task)

                        # Assign task to new robot
                        best_candidate.assign_task(task)

                        self.emit_system_event(
                            f"Order {task['id']} reassigned from {r_old.name} to {best_candidate.name}"
                        )

                        # Remove newly busy robot from idle_robots list
                        idle_robots.remove(best_candidate)

            # Retrieve pending orders and idle robots
            pending_orders = [
                t for t in self.order_queue if t.get("status") == ORDER_STATUS_PENDING
            ]
            if not pending_orders:
                continue

            if not idle_robots:
                continue

            # Build AssignmentInput
            dispatch_model_name = self.app_state.get("dispatch_model", "nearest_idle")

            context = AssignmentInput(
                graph=snap_graph,
                robots=idle_robots,
                orders=pending_orders,
                nearest_node_fn=self.nearest_node_id,
                weight_fn=lambda u, v, d: snap_graph.get_edge_weight(u, v, d),
                run_route_search_fn=self.run_weighted_route_search,
                alpha=DISPATCH_ALPHA,
                beta=DISPATCH_BETA,
                gamma=DISPATCH_GAMMA,
                val_lambda=DISPATCH_LAMBDA,
            )

            try:
                result = run_assignment(dispatch_model_name, context)
            except Exception as e:
                self.emit_system_event(f"Assignment execution failed: {e}")
                continue

            # Process assignments
            for assignment in result.assignments:
                task = assignment.order
                robot = assignment.robot

                try:
                    # Remove from pending queue and mark assigned
                    if task in self.order_queue:
                        self.order_queue.remove(task)
                    task["robot_name"] = robot.name
                    self.order_manager.mark_assigned(task)

                    # Compute battery cost to see if robot is low on battery
                    pickup_cost = compute_battery_cost(
                        snap_graph, assignment.pickup_path
                    )
                    dropoff_cost = compute_battery_cost(
                        snap_graph, assignment.dropoff_path
                    )
                    total_battery_cost = pickup_cost + dropoff_cost

                    if robot.battery < total_battery_cost:
                        # 3-leg route required!
                        hub = robot.select_optimal_hub()
                        if hub:
                            robot_node = self.nearest_node_id(
                                snap_graph, robot.lat, robot.lon
                            )
                            hub_node = self.nearest_node_id(
                                snap_graph, hub["lat"], hub["lon"]
                            )
                            pickup_node = self.nearest_node_id(
                                snap_graph, task["pickup"]["lat"], task["pickup"]["lon"]
                            )
                            delivery_node = self.nearest_node_id(
                                snap_graph,
                                task["dropoff"]["lat"],
                                task["dropoff"]["lon"],
                            )

                            def weight_fn(u, v, d):
                                return snap_graph.get_edge_weight(u, v, d)

                            # Leg 1: Robot -> Hub
                            charge_result = self.run_weighted_route_search(
                                snap_graph,
                                robot_node,
                                hub_node,
                                hub["lat"],
                                hub["lon"],
                                weight_fn,
                                "astar",
                            )

                            # Leg 2: Hub -> Pickup
                            pickup_result = self.run_weighted_route_search(
                                snap_graph,
                                hub_node,
                                pickup_node,
                                task["pickup"]["lat"],
                                task["pickup"]["lon"],
                                weight_fn,
                                "astar",
                            )

                            # Leg 3: Pickup -> Delivery
                            dropoff_result = self.run_weighted_route_search(
                                snap_graph,
                                pickup_node,
                                delivery_node,
                                task["dropoff"]["lat"],
                                task["dropoff"]["lon"],
                                weight_fn,
                                "astar",
                            )

                            task["is_3_leg"] = True
                            task["charging_station"] = hub
                            task["charge_path"] = charge_result.path
                            task["pickup_path"] = pickup_result.path
                            task["dropoff_path"] = dropoff_result.path

                            task["charge_planned_cost"] = charge_result.planned_cost
                            task["pickup_planned_cost"] = pickup_result.planned_cost
                            task["dropoff_planned_cost"] = dropoff_result.planned_cost
                            task["charge_edge_planned_costs"] = [
                                snap_graph.get_edge_weight(
                                    u, v, snap_graph.get_edge_data(u, v)
                                )
                                for u, v in zip(
                                    charge_result.path[:-1], charge_result.path[1:]
                                )
                            ]
                            task["pickup_edge_planned_costs"] = [
                                snap_graph.get_edge_weight(
                                    u, v, snap_graph.get_edge_data(u, v)
                                )
                                for u, v in zip(
                                    pickup_result.path[:-1], pickup_result.path[1:]
                                )
                            ]
                            task["dropoff_edge_planned_costs"] = [
                                snap_graph.get_edge_weight(
                                    u, v, snap_graph.get_edge_data(u, v)
                                )
                                for u, v in zip(
                                    dropoff_result.path[:-1], dropoff_result.path[1:]
                                )
                            ]

                            # Build geometry for all three legs
                            charge_geometry_path, charge_segment_geometry = (
                                self.build_route_geometry(
                                    snap_graph, charge_result.path
                                )
                            )
                            task["charge_geometry_path"] = charge_geometry_path
                            task["charge_segment_geometry"] = charge_segment_geometry

                            pickup_geometry_path, pickup_segment_geometry = (
                                self.build_route_geometry(
                                    snap_graph, pickup_result.path
                                )
                            )
                            task["pickup_geometry_path"] = pickup_geometry_path
                            task["pickup_segment_geometry"] = pickup_segment_geometry

                            dropoff_geometry_path, dropoff_segment_geometry = (
                                self.build_route_geometry(
                                    snap_graph, dropoff_result.path
                                )
                            )
                            task["dropoff_geometry_path"] = dropoff_geometry_path
                            task["dropoff_segment_geometry"] = dropoff_segment_geometry
                        else:
                            task["is_3_leg"] = False
                    else:
                        task["is_3_leg"] = False

                    if not task.get("is_3_leg"):
                        task["pickup_path"] = assignment.pickup_path
                        task["dropoff_path"] = assignment.dropoff_path

                        task["pickup_planned_cost"] = assignment.pickup_cost
                        task["dropoff_planned_cost"] = assignment.dropoff_cost
                        task["pickup_edge_planned_costs"] = [
                            snap_graph.get_edge_weight(
                                u, v, snap_graph.get_edge_data(u, v)
                            )
                            for u, v in zip(
                                assignment.pickup_path[:-1], assignment.pickup_path[1:]
                            )
                        ]
                        task["dropoff_edge_planned_costs"] = [
                            snap_graph.get_edge_weight(
                                u, v, snap_graph.get_edge_data(u, v)
                            )
                            for u, v in zip(
                                assignment.dropoff_path[:-1],
                                assignment.dropoff_path[1:],
                            )
                        ]

                        # Build geometry for accurate drawing and proportional interpolation
                        pickup_geometry_path, pickup_segment_geometry = (
                            self.build_route_geometry(
                                snap_graph, assignment.pickup_path
                            )
                        )
                        task["pickup_geometry_path"] = pickup_geometry_path
                        task["pickup_segment_geometry"] = pickup_segment_geometry

                        dropoff_geometry_path, dropoff_segment_geometry = (
                            self.build_route_geometry(
                                snap_graph, assignment.dropoff_path
                            )
                        )
                        task["dropoff_geometry_path"] = dropoff_geometry_path
                        task["dropoff_segment_geometry"] = dropoff_segment_geometry

                    self.emit_system_event(
                        f"Order {task['id']} assigned to {robot.name} ({dispatch_model_name})"
                    )
                    robot.assign_task(task)
                except Exception as e:
                    self.emit_system_event(
                        f"Assignment setup failed for {task['id']}: {e}"
                    )
                    self.order_manager.requeue_order(task)

    def _scenario_injector_process(self) -> Generator[simpy.Event, None, None]:
        """Yield simulation time and publish scenario events when reached.

        Yields:
            simpy.Event: A timeout event for SimPy scheduler.
        """
        if not self.scenario_config or not self.scenario_config.events:
            return

        sorted_events = sorted(self.scenario_config.events, key=lambda e: e.sim_time)
        for event in sorted_events:
            if event.sim_time > self.env.now:
                yield self.env.timeout(event.sim_time - self.env.now)
            self.app_state["event_bus"].publish(event)

    @profile_time(label="simulator_run_loop")
    def _run_loop(self):
        p = Profiler()
        ticks_per_real_second = 10.0
        real_time_step = 1.0 / ticks_per_real_second
        tick_counter = 0

        while not self._stop_event.is_set():
            with profile_block("simulator_tick"):
                speed = self.app_state.get("simulation_speed", 60)
                sim_time_step = speed / ticks_per_real_second

                self.env.run(until=self.env.now + sim_time_step)
                self.app_state["sim_now"] = self.env.now
                self.app_state["event_bus"].publish(
                    Event(EventType.SIM_TICK, sim_time=self.env.now)
                )

                tick_counter += 1
                if tick_counter >= ticks_per_real_second:
                    tick_counter = 0
                    self.emit_clock_update()
                    p.save_to_log()

            # Standard threading sleep using socketio
            self.socketio.sleep(real_time_step)
