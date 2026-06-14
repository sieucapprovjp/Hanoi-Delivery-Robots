import importlib

from . import config
from .utils.route_analysis import build_route_response
from .utils.validation import (
    validate_coordinate,
    validate_lat_lon,
    validate_non_negative_int,
    validate_positive_number,
)


_APP_EXPORTS = {
    "DELIVERY_HISTORY",
    "RAIN_ZONES",
    "_dynamic_traffic_lock",
    "_dynamic_traffic_routes",
    "_obstacles",
    "_obstacles_lock",
    "_ox",
    "_projected_road_graph",
    "_road_graph",
    "app",
    "flask_app",
    "get_road_graph",
}


def __getattr__(name):
    if name not in _APP_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    app_module = importlib.import_module(".app", __name__)
    if name == "flask_app":
        return app_module.app
    return getattr(app_module, name)


__all__ = [
    "DELIVERY_HISTORY",
    "RAIN_ZONES",
    "_dynamic_traffic_lock",
    "_dynamic_traffic_routes",
    "_obstacles",
    "_obstacles_lock",
    "_ox",
    "_projected_road_graph",
    "_road_graph",
    "app",
    "build_route_response",
    "config",
    "flask_app",
    "get_road_graph",
    "validate_coordinate",
    "validate_lat_lon",
    "validate_non_negative_int",
    "validate_positive_number",
]
