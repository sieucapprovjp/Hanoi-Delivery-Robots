import threading
import time
import networkx as nx
import numpy as np
import osmnx as ox
from collections import deque

from flask import Flask

from .config import (
    API_LOGS_MAX_LENGTH,
    GRAPH_CENTER,
    GRAPH_DIST_METERS,
    GRAPH_NETWORK_TYPE,
    RAIN_ZONES_INITIAL,
    RUSH_HOURS,
    SIMULATION_SPEED,
    TRAFFIC_ANCHORS,
    TRAFFIC_PERIOD_SECONDS,
    DEFAULT_DISPATCH_MODEL,
    NEIGHBOR_ORDERING_POLICY,
)

from .core.data import CHARGING_STATIONS
from .core.environment import (
    edge_weight_with_traffic as core_edge_weight_with_traffic,
    get_rush_hour_multiplier as core_get_rush_hour_multiplier,
    get_simulation_time as core_get_simulation_time,
    obstacle_penalty_for_point as core_obstacle_penalty_for_point,
    rain_penalty_for_point as core_rain_penalty_for_point,
    traffic_penalty_for_point as core_traffic_penalty_for_point,
    register_environment_subscribers,
)
from .core.event_bus import EventBus
from .core.graph import get_road_graph as core_get_road_graph
from .routes import register_environment_routes, register_main_routes
from .utils.metrics import (
    build_metrics_payload,
    create_metrics,
    record_route_metrics,
    record_route_failure,
)
from .utils import MetricsInterceptor
from .utils.route_analysis import (
    build_geometry_path,
    build_route_response,
    build_segment_geometry,
    nearest_node_id,
)
from .utils.validation import (
    validate_coordinate,
    validate_lat_lon,
    validate_non_negative_int,
    validate_positive_number,
)
from flask_socketio import SocketIO
from .core.simulation.simulator import SimulatorManager
from .algorithms import run_weighted_route_search

app = Flask(__name__)
socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")

RAIN_ZONES = list(RAIN_ZONES_INITIAL)

_simulation_start_time = time.time()
_simulation_speed = SIMULATION_SPEED

_graph_lock = threading.Lock()
_road_graph = nx.DiGraph()
_projected_road_graph = nx.DiGraph()
_traffic_routes = []
_ox = ox

DELIVERY_HISTORY = []
_history_lock = threading.Lock()

_dynamic_traffic_lock = threading.Lock()
_dynamic_traffic_routes = []

_obstacles_lock = threading.Lock()
_obstacles = []

_metrics = create_metrics()
_metrics_lock = threading.Lock()


def _on_route_search_completed(
    calc_time_ms: float,
    nodes_explored: int,
    path_length: int,
    memory_bytes: int,
    algo_name: str,
    optimality_ratio: float = 1.0,
    heuristic_effectiveness: float = 1.0,
    graph=None,
    path=None,
) -> None:
    """Callback function triggered when a route search is completed.

    Args:
        calc_time_ms (float): Computation time in milliseconds.
        nodes_explored (int): Number of nodes explored during search.
        path_length (int): Number of nodes in the generated path.
        memory_bytes (int): Memory usage in bytes.
        algo_name (str): Name of the pathfinding algorithm.
        optimality_ratio (float): Path optimality ratio. Defaults to 1.0.
        heuristic_effectiveness (float): Heuristic effectiveness ratio. Defaults to 1.0.
        graph: The road network graph. Defaults to None.
        path: The path node list. Defaults to None.
    """
    with _metrics_lock:
        record_route_metrics(
            _metrics,
            calc_time_ms,
            nodes_explored,
            path_length,
            memory_bytes=memory_bytes,
            optimality_ratio=optimality_ratio,
            heuristic_effectiveness=heuristic_effectiveness,
            graph=graph,
            path=path,
            algo_name=algo_name,
        )


def _on_route_search_failed(
    calc_time_ms: float,
    memory_bytes: int,
    algo_name: str,
    error: Exception,
    graph=None,
    start_node=None,
    end_node=None,
    nodes_explored: int = 0,
) -> None:
    """Callback function triggered when a route search fails.

    Args:
        calc_time_ms (float): Computation time spent before failure in ms.
        memory_bytes (int): Memory usage in bytes.
        algo_name (str): Name of the pathfinding algorithm.
        error (Exception): The error/exception that caused the failure.
        graph: The road network graph snapshot. Defaults to None.
        start_node: The start node ID. Defaults to None.
        end_node: The target node ID. Defaults to None.
        nodes_explored: Number of nodes explored before failure.
    """
    with _metrics_lock:
        record_route_failure(
            _metrics,
            calc_time_ms,
            memory_bytes,
            algo_name,
            error,
            graph=graph,
            start_node=start_node,
            end_node=end_node,
            nodes_explored=nodes_explored,
        )


MetricsInterceptor.register_callback(_on_route_search_completed)
MetricsInterceptor.register_failure_callback(_on_route_search_failed)


_api_logs_lock = threading.Lock()
_api_logs = deque(maxlen=API_LOGS_MAX_LENGTH)

_spatial_node_ids = np.array([])
_spatial_tree = None

_sim_now = 0

_event_bus = EventBus(recording=True)

_app_state = {
    "graph_center": GRAPH_CENTER,
    "graph_dist_meters": GRAPH_DIST_METERS,
    "graph_network_type": GRAPH_NETWORK_TYPE,
    "traffic_anchors": TRAFFIC_ANCHORS,
    "traffic_period_seconds": TRAFFIC_PERIOD_SECONDS,
    "rain_zones": RAIN_ZONES,
    "simulation_start_time": _simulation_start_time,
    "simulation_speed": _simulation_speed,
    "rush_hours": RUSH_HOURS,
    "graph_lock": _graph_lock,
    "road_graph": _road_graph,
    "projected_road_graph": _projected_road_graph,
    "traffic_routes": _traffic_routes,
    "ox": _ox,
    "delivery_history": DELIVERY_HISTORY,
    "history_lock": _history_lock,
    "dynamic_traffic_lock": _dynamic_traffic_lock,
    "dynamic_traffic_routes": _dynamic_traffic_routes,
    "obstacles_lock": _obstacles_lock,
    "obstacles": _obstacles,
    "api_logs": _api_logs,
    "api_logs_lock": _api_logs_lock,
    "spatial_node_ids": _spatial_node_ids,
    "spatial_tree": _spatial_tree,
    "sim_now": _sim_now,
    "event_bus": _event_bus,
    "charging_stations": list(CHARGING_STATIONS),
    "dispatch_model": DEFAULT_DISPATCH_MODEL,
    "neighbor_ordering_policy": NEIGHBOR_ORDERING_POLICY,
    "metrics": _metrics,
    "metrics_lock": _metrics_lock,
}

register_environment_subscribers(_event_bus, _app_state)


def _sync_state_from_globals():
    _app_state["road_graph"] = _road_graph
    _app_state["projected_road_graph"] = _projected_road_graph
    _app_state["traffic_routes"] = _traffic_routes
    _app_state["ox"] = _ox
    _app_state["rain_zones"] = RAIN_ZONES
    _app_state["dynamic_traffic_routes"] = _dynamic_traffic_routes
    _app_state["obstacles"] = _obstacles
    _app_state["delivery_history"] = DELIVERY_HISTORY
    _app_state["spatial_node_ids"] = _spatial_node_ids
    _app_state["spatial_tree"] = _spatial_tree


def _sync_globals_from_state():
    global \
        _road_graph, \
        _projected_road_graph, \
        _traffic_routes, \
        _ox, \
        _spatial_node_ids, \
        _spatial_tree
    _road_graph = _app_state["road_graph"]
    _projected_road_graph = _app_state["projected_road_graph"]
    _traffic_routes = _app_state["traffic_routes"]
    _ox = _app_state["ox"]
    _spatial_node_ids = _app_state["spatial_node_ids"]
    _spatial_tree = _app_state["spatial_tree"]


def get_road_graph():
    _sync_state_from_globals()
    result = core_get_road_graph(
        _app_state,
        lambda g, lat, lon, ox=_app_state["ox"]: nearest_node_id(
            g, lat, lon, {**_app_state, "ox": ox}
        ),
        build_route_response,
        traffic_penalty_for_point,
        rain_penalty_for_point,
        obstacle_penalty_for_point,
    )
    _sync_globals_from_state()
    return result


def get_simulation_time():
    _sync_state_from_globals()
    return core_get_simulation_time(_app_state)


def get_rush_hour_multiplier():
    _sync_state_from_globals()
    return core_get_rush_hour_multiplier(_app_state)


def traffic_penalty_for_point(lat, lon):
    _sync_state_from_globals()
    return core_traffic_penalty_for_point(_app_state, lat, lon)


def rain_penalty_for_point(lat, lon):
    _sync_state_from_globals()
    return core_rain_penalty_for_point(_app_state, lat, lon)


def obstacle_penalty_for_point(lat, lon):
    _sync_state_from_globals()
    return core_obstacle_penalty_for_point(_app_state, lat, lon)


def edge_weight_with_traffic(from_node, to_node, edge_data):
    _sync_state_from_globals()
    return core_edge_weight_with_traffic(_app_state, from_node, to_node, edge_data)


def _build_routes_context():
    return {
        "app_state": _app_state,
        "get_road_graph": lambda: get_road_graph(),
        "road_graph_getter": lambda: _road_graph,
        "get_simulation_time": get_simulation_time,
        "get_rush_hour_multiplier": get_rush_hour_multiplier,
        "build_metrics_payload": build_metrics_payload,
        "record_route_metrics": record_route_metrics,
        "build_route_response": build_route_response,
        "nearest_node_id": lambda g, lat, lon, ox=_app_state["ox"]: nearest_node_id(
            g, lat, lon, {**_app_state, "ox": ox}
        ),
        "validate_coordinate": validate_coordinate,
        "validate_lat_lon": validate_lat_lon,
        "validate_non_negative_int": validate_non_negative_int,
        "validate_positive_number": validate_positive_number,
        "traffic_penalty_for_point": traffic_penalty_for_point,
        "rain_penalty_for_point": rain_penalty_for_point,
        "obstacle_penalty_for_point": obstacle_penalty_for_point,
        "edge_weight_with_traffic": edge_weight_with_traffic,
        "traffic_period_seconds": TRAFFIC_PERIOD_SECONDS,
        "rush_hours": RUSH_HOURS,
        "simulation_speed": _simulation_speed,
        "rain_zones": RAIN_ZONES,
        "dynamic_traffic_lock": _dynamic_traffic_lock,
        "dynamic_traffic_routes": _dynamic_traffic_routes,
        "obstacles_lock": _obstacles_lock,
        "obstacles": _obstacles,
        "metrics": _metrics,
        "api_logs": _api_logs,
        "api_logs_lock": _api_logs_lock,
        "get_ox": lambda: _ox,
        "spatial_node_ids": _spatial_node_ids,
        "spatial_tree": _spatial_tree,
        "event_bus": _event_bus,
    }


_ctx = _build_routes_context()
register_main_routes(app, _ctx)
register_environment_routes(app, _ctx)


def _build_route_geometry(graph, route_nodes):
    """Helper that returns (geometry_path, segment_geometry) for a route."""
    geometry_path = build_geometry_path(graph, route_nodes)
    segment_geometry = build_segment_geometry(graph, route_nodes)
    return geometry_path, segment_geometry


simulator = SimulatorManager(
    socketio=socketio,
    app_state=_app_state,
    nearest_node_id=lambda g, lat, lon: nearest_node_id(g, lat, lon, _app_state),
    run_weighted_route_search=run_weighted_route_search,
    edge_weight_with_traffic=core_edge_weight_with_traffic,
    build_route_geometry=_build_route_geometry,
)
_app_state["simulator"] = simulator


@socketio.on("start_simulation")
def handle_start():
    simulator.start()


@socketio.on("pause_simulation")
def handle_pause():
    simulator.pause()


@socketio.on("reset_simulation")
def handle_reset():
    simulator.reset()
