import random
from flask import Blueprint, jsonify, request
from .. import env_manager
from ..utils.validation import validate_coordinate, validate_lat_lon, validate_non_negative_int, validate_positive_number

weather_bp = Blueprint('weather', __name__)

@weather_bp.route("", methods=["GET"])
def get_weather():
    """Get active weather status (rain zones) with multipliers."""
    return jsonify({
        "rainZones": [
            {
                "name": zone["name"],
                "center": {"lat": zone["center"][0], "lon": zone["center"][1]},
                "radius": zone["radius"],
                "multiplier": round(1 + zone.get("severity", 1.0), 2),
            }
            for zone in env_manager.rain_zones
        ]
    })

@weather_bp.route("/rain", methods=["GET"])
def list_rain():
    """List all rain zones."""
    return jsonify({
        "rainZones": [
            {
                "name": z["name"],
                "center": {"lat": z["center"][0], "lon": z["center"][1]},
                "radius": z["radius"],
            }
            for z in env_manager.rain_zones
        ]
    })

@weather_bp.route("/rain", methods=["POST"])
def add_rain():
    """Add a new rain zone."""
    d = request.get_json(silent=True) or {}
    try:
        lat = validate_coordinate(d.get("lat"), "lat")
        lon = validate_coordinate(d.get("lon"), "lon")
        radius = validate_positive_number(d.get("radius", 150), "radius")
        validate_lat_lon(lat, lon)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    env_manager.rain_zones.append({
        "name": f"Rain {len(env_manager.rain_zones) + 1}",
        "center": (lat, lon),
        "radius": radius,
        "severity": 1.0,
    })
    return jsonify({
        "message": "Added",
        "rainZone": {
            "name": f"Rain {len(env_manager.rain_zones)}",
            "center": {"lat": lat, "lon": lon},
            "radius": radius,
        },
    })

@weather_bp.route("/rain/randomize", methods=["POST"])
def randomize_rain():
    """Generate random rain zones."""
    d = request.get_json(silent=True) or {}
    try:
        count = validate_non_negative_int(d.get("count", 3), "count")
        min_radius = validate_positive_number(d.get("minRadius", 100), "minRadius")
        max_radius = validate_positive_number(d.get("maxRadius", 200), "maxRadius")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if min_radius > max_radius:
        return jsonify({"error": "minRadius must be less than or equal to maxRadius"}), 400

    env_manager.rain_zones = [
        {
            "name": f"Rain {i + 1}",
            "center": (
                random.uniform(21.0180, 21.0380),
                random.uniform(105.8430, 105.8650),
            ),
            "radius": random.uniform(min_radius, max_radius),
            "severity": 1.0,
        }
        for i in range(count)
    ]
    return jsonify({
        "message": f"Added {count}",
        "rainZones": [
            {
                "name": z["name"],
                "center": {"lat": z["center"][0], "lon": z["center"][1]},
                "radius": z["radius"],
            }
            for z in env_manager.rain_zones
        ],
    })

@weather_bp.route("/rain", methods=["DELETE"])
def clear_rain():
    """Clear all rain zones."""
    env_manager.rain_zones = []
    return jsonify({"message": "Cleared"})
