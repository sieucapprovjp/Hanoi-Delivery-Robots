from flask import jsonify, render_template

from ..core.data import CHARGING_STATIONS, INITIAL_ROBOTS, LOCATIONS
from ..core.hubs import compute_optimized_hubs
from ..config import (
    DEFAULT_HUB_CLUSTER_COUNT,
)


def register_main_routes(app, ctx):
    app_state = ctx["app_state"]

    @app.route("/api/data/locations")
    def get_locations():
        return jsonify({"locations": LOCATIONS})

    @app.route("/api/data/hubs")
    def get_hubs():
        return jsonify({"hubs": app_state.get("charging_stations", CHARGING_STATIONS)})

    @app.route("/api/data/robots")
    def get_robots():
        return jsonify({"robots": INITIAL_ROBOTS})

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/optimize-hubs", methods=["POST"])
    def optimize_hubs():
        try:
            hubs = compute_optimized_hubs(
                app_state, cluster_count=DEFAULT_HUB_CLUSTER_COUNT
            )
            app_state["charging_stations"] = hubs
            return jsonify({"hubs": hubs}), 200
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500
