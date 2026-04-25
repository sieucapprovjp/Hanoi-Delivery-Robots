import random
from flask import Blueprint, jsonify, request
from .. import env_manager
from ..utils.validation import validate_coordinate, validate_lat_lon, validate_non_negative_int, validate_positive_number

obstacles_bp = Blueprint('obstacles', __name__)

@obstacles_bp.route("", methods=["GET"])
def list_obstacles():
    """List all obstacles."""
    with env_manager._obstacles_lock:
        return jsonify({
            "obstacles": [
                {
                    "name": o["name"],
                    "center": {"lat": o["center"][0], "lon": o["center"][1]},
                    "radius": o["radius"],
                    "severity": o["severity"],
                    "type": o["type"],
                }
                for o in env_manager._obstacles
            ]
        })

@obstacles_bp.route("", methods=["POST"])
def add_obstacle():
    """Add a new obstacle."""
    d = request.get_json(silent=True) or {}
    try:
        lat = validate_coordinate(d.get("lat"), "lat")
        lon = validate_coordinate(d.get("lon"), "lon")
        radius = validate_positive_number(d.get("radius", 80), "radius")
        severity = validate_positive_number(d.get("severity", 10), "severity")
        validate_lat_lon(lat, lon)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    o = {
        "name": f"Obstacle {len(env_manager._obstacles) + 1}",
        "center": (lat, lon),
        "radius": radius,
        "severity": severity,
        "type": d.get("type", "roadblock"),
    }
    with env_manager._obstacles_lock:
        env_manager._obstacles.append(o)
    return jsonify({
        "message": "Added",
        "obstacle": {
            "name": o["name"],
            "center": {"lat": lat, "lon": lon},
            "radius": o["radius"],
            "severity": o["severity"],
            "type": o["type"],
        },
    })

@obstacles_bp.route("/randomize", methods=["POST"])
def randomize_obstacles():
    """Generate random obstacles."""
    d = request.get_json(silent=True) or {}
    try:
        count = validate_non_negative_int(d.get("count", 3), "count")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    types = ["roadblock", "construction", "accident"]
    with env_manager._obstacles_lock:
        env_manager._obstacles = [
            {
                "name": f"Obs {i + 1}",
                "center": (
                    random.uniform(21.0180, 21.0380),
                    random.uniform(105.8430, 105.8650),
                ),
                "radius": random.uniform(50, 120),
                "severity": random.uniform(5, 50),
                "type": random.choice(types),
            }
            for i in range(count)
        ]
    return jsonify({
        "message": f"Added {count}",
        "obstacles": [
            {
                "name": o["name"],
                "center": {"lat": o["center"][0], "lon": o["center"][1]},
                "radius": o["radius"],
                "severity": o["severity"],
                "type": o["type"],
            }
            for o in env_manager._obstacles
        ],
    })

@obstacles_bp.route("", methods=["DELETE"])
def clear_obstacles():
    """Clear all obstacles."""
    with env_manager._obstacles_lock:
        env_manager._obstacles = []
    return jsonify({"message": "Cleared"})
