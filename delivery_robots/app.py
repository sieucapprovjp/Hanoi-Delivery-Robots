import threading
import time
from collections import deque

from flask import Flask

from .core.environment import (
    edge_weight_with_traffic as core_edge_weight_with_traffic,
    get_rush_hour_multiplier as core_get_rush_hour_multiplier,
    get_simulation_time as core_get_simulation_time,
    obstacle_penalty_for_point as core_obstacle_penalty_for_point,
    rain_penalty_for_point as core_rain_penalty_for_point,
    traffic_penalty_for_point as core_traffic_penalty_for_point,
)
from .core.graph import get_road_graph as core_get_road_graph
from .routes import register_environment_routes, register_main_routes
from .utils.metrics import build_metrics_payload, create_metrics, record_route_metrics
from .utils.route_analysis import build_route_response, nearest_node_id
from .utils.validation import (
    validate_coordinate,
    validate_lat_lon,
    validate_non_negative_int,
    validate_positive_number,
)

app = Flask(__name__)

GRAPH_CENTER = (21.0285, 105.8542)
GRAPH_DIST_METERS = 2200
GRAPH_NETWORK_TYPE = "bike"
TRAFFIC_ANCHORS = []
TRAFFIC_PERIOD_SECONDS = 36
RAIN_ZONES = []

_simulation_start_time = time.time()
_simulation_speed = 60
RUSH_HOURS = [
    {"name": "Morning Rush", "start": 7, "end": 9, "multiplier": 2.5},
    {"name": "Lunch Traffic", "start": 11, "end": 13, "multiplier": 1.3},
    {"name": "Evening Rush", "start": 17, "end": 19, "multiplier": 3.0},
]

_graph_lock = threading.Lock()
_road_graph = None
_projected_road_graph = None
_traffic_routes = None
_ox = None

DELIVERY_HISTORY = []
_history_lock = threading.Lock()

_dynamic_traffic_lock = threading.Lock()
_dynamic_traffic_routes = []

_obstacles_lock = threading.Lock()
_obstacles = []

_metrics = create_metrics()
_api_logs_lock = threading.Lock()
_api_logs = deque(maxlen=500)


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
    "metrics": _metrics,
    "api_logs": _api_logs,
    "api_logs_lock": _api_logs_lock,
}


def _sync_state_from_globals():
    _app_state["road_graph"] = _road_graph
    _app_state["projected_road_graph"] = _projected_road_graph
    _app_state["traffic_routes"] = _traffic_routes
    _app_state["ox"] = _ox
    _app_state["rain_zones"] = RAIN_ZONES
    _app_state["dynamic_traffic_routes"] = _dynamic_traffic_routes
    _app_state["obstacles"] = _obstacles
    _app_state["delivery_history"] = DELIVERY_HISTORY


def _sync_globals_from_state():
    global _road_graph, _projected_road_graph, _traffic_routes, _ox
    _road_graph = _app_state["road_graph"]
    _projected_road_graph = _app_state["projected_road_graph"]
    _traffic_routes = _app_state["traffic_routes"]
    _ox = _app_state["ox"]


def get_road_graph():
    _sync_state_from_globals()
    result = core_get_road_graph(
        _app_state,
        nearest_node_id,
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
        "get_road_graph": get_road_graph,
        "road_graph_getter": lambda: _road_graph,
        "get_simulation_time": get_simulation_time,
        "get_rush_hour_multiplier": get_rush_hour_multiplier,
        "build_metrics_payload": build_metrics_payload,
        "record_route_metrics": record_route_metrics,
        "build_route_response": build_route_response,
        "nearest_node_id": nearest_node_id,
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
    }


_ctx = _build_routes_context()
register_main_routes(app, _ctx)
register_environment_routes(app, _ctx)
