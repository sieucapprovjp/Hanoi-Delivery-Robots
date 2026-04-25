from flask import Blueprint, jsonify
from .. import _metrics, map_manager, env_manager
from ..utils.metrics_utils import build_metrics_payload

metrics_bp = Blueprint('metrics', __name__)

@metrics_bp.route("", methods=["GET"])
def get_metrics():
    """Get system and routing metrics."""
    return jsonify(
        build_metrics_payload(
            _metrics,
            map_manager._road_graph,
            len(env_manager.rain_zones),
            len(env_manager._dynamic_traffic_routes),
            len(env_manager._obstacles),
        )
    )
