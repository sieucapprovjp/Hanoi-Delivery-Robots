import os

from delivery_robots.app import app, get_road_graph


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    print("Starting Hanoi Delivery Robots...")
    print("Loading OpenStreetMap road graph for Hoan Kiem...")
    get_road_graph()
    print(f"Open http://127.0.0.1:{port} in your browser")
    app.run(host="127.0.0.1", port=port)
