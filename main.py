import os

from delivery_robots.app import app, get_road_graph, socketio


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    print("Starting Hanoi Delivery Robots...")
    print("Loading OpenStreetMap road graph for Hoan Kiem...")
    get_road_graph()
    print(f"Open http://127.0.0.1:{port} in your browser")
    socketio.run(app, host="127.0.0.1", port=port, debug=True, allow_unsafe_werkzeug=True, use_reloader=False)
