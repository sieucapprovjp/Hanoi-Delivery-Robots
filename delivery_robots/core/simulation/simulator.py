import simpy
import random
import threading
from .robot_agent import RobotAgent
from ..data import LOCATIONS, INITIAL_ROBOTS

class SimulatorManager:
    def __init__(self, socketio, app_state, nearest_node_id, run_weighted_route_search, edge_weight_with_traffic):
        self.socketio = socketio
        self.app_state = app_state
        self.nearest_node_id = nearest_node_id
        self.run_weighted_route_search = run_weighted_route_search
        self.edge_weight_with_traffic = edge_weight_with_traffic
        
        self.env = simpy.Environment()
        self.robots = []
        self.running = False
        self._thread = None
        self._stop_event = threading.Event()
        
        # Order dispatcher queue
        self.order_queue = []

    def initialize_robots(self):
        self.robots = []
        initial_starts = LOCATIONS[:len(INITIAL_ROBOTS)]
        
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
                on_state_change=self.emit_robot_state
            )
            self.robots.append(agent)
            
    def emit_robot_state(self, state):
        # We send to a specific websocket event
        self.socketio.emit('robot_state_update', state)

    def emit_system_event(self, message):
        self.socketio.emit('system_event', {'message': message})

    def start(self):
        if self.running:
            return
        
        if not self.robots:
            self.initialize_robots()
            
        self.running = True
        self._stop_event.clear()
        
        # Start background processes in SimPy
        self.env.process(self._order_generator_process())
        self.env.process(self._dispatcher_process())
        
        self._thread = self.socketio.start_background_task(self._run_loop)
        self.emit_system_event('Simulation started')
        
    def pause(self):
        self.running = False
        self._stop_event.set()
        self.emit_system_event('Simulation paused')

    def reset(self):
        self.pause()
        self.env = simpy.Environment()
        self.order_queue = []
        self.initialize_robots()
        
        # Broadcast initial states
        for robot in self.robots:
            self.emit_robot_state(robot.get_state())
        self.emit_system_event('Simulation reset')

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
            
            # ensure pickup != dropoff
            while pickup == dropoff:
                dropoff = self._generate_random_location()
                
            task = {
                'id': f"ORDER-{int(self.env.now)}",
                'pickup': pickup,
                'dropoff': dropoff
            }
            self.order_queue.append(task)
            self.emit_system_event(f"New order {task['id']} generated from {pickup['name']} to {dropoff['name']}")

    def _dispatcher_process(self):
        while True:
            # Dispatch checks every 10 seconds of sim time
            yield self.env.timeout(10)
            
            if not self.order_queue:
                continue
                
            idle_robots = [r for r in self.robots if r.status == "idle"]
            if not idle_robots:
                continue
                
            # Naive assignment: assign first task to first idle robot
            task = self.order_queue.pop(0)
            robot = idle_robots[0]
            
            # Generate routes
            graph = self.app_state.get("road_graph")
            if not graph:
                self.order_queue.insert(0, task)
                continue
                
            try:
                # 1. Route: Robot -> Pickup
                robot_node = self.nearest_node_id(graph, robot.lat, robot.lon)
                pickup_node = self.nearest_node_id(graph, task['pickup']['lat'], task['pickup']['lon'])
                
                pickup_path, _ = self.run_weighted_route_search(
                    graph, robot_node, pickup_node,
                    task['pickup']['lat'], task['pickup']['lon'],
                    lambda u, v, d: self.edge_weight_with_traffic(self.app_state, u, v, d),
                    'astar'
                )
                
                # 2. Route: Pickup -> Dropoff
                dropoff_node = self.nearest_node_id(graph, task['dropoff']['lat'], task['dropoff']['lon'])
                dropoff_path, _ = self.run_weighted_route_search(
                    graph, pickup_node, dropoff_node,
                    task['dropoff']['lat'], task['dropoff']['lon'],
                    lambda u, v, d: self.edge_weight_with_traffic(self.app_state, u, v, d),
                    'astar'
                )
                
                task['pickup_path'] = pickup_path
                task['dropoff_path'] = dropoff_path
                
                self.emit_system_event(f"Order {task['id']} assigned to {robot.name}")
                robot.assign_task(task)
            except Exception:
                # If routing fails, put order back
                self.emit_system_event(f"Routing failed for {task['id']}, retrying later")
                self.order_queue.insert(0, task)
                
                # Prevent tight loop spam if there is a persistent error
                yield self.env.timeout(10)

    def _run_loop(self):
        ticks_per_real_second = 10.0
        real_time_step = 1.0 / ticks_per_real_second
        
        while not self._stop_event.is_set():
            speed = self.app_state.get("simulation_speed", 60)
            sim_time_step = speed / ticks_per_real_second
            
            self.env.run(until=self.env.now + sim_time_step)
            
            # Standard threading sleep using socketio
            self.socketio.sleep(real_time_step)
