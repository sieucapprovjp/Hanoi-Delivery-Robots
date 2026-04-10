from flask import Flask, jsonify
from flask_cors import CORS
import time
import threading

app = Flask(__name__)
CORS(app) # Cho phép JS gọi API

# Giả lập dữ liệu robot (Trong thực tế, cái này do hàm A* của bạn cập nhật)
robots_state = {
    "robot_1": {"lat": 21.0285, "lon": 105.8541, "status": "Moving"},
    "robot_2": {"lat": 21.0264, "lon": 105.8504, "status": "Charging"}
}

# Hàm chạy ngầm để giả lập xe đang di chuyển (Tick System)
def simulation_loop():
    while True:
        # Ở đây bạn gọi Master Controller và thuật toán tìm đường
        robots_state["robot_1"]["lat"] += 0.0001 # Giả lập xe đang nhích lên
        robots_state["robot_1"]["lon"] += 0.0001
        time.sleep(1) # 1 Tick = 1 giây

# Mở một đường API để JS gọi vào lấy dữ liệu
@app.route('/api/robots', methods=['GET'])
def get_robots():
    return jsonify(robots_state)

if __name__ == '__main__':
    # Chạy vòng lặp AI ở một luồng riêng
    threading.Thread(target=simulation_loop, daemon=True).start()
    # Chạy Server Flask
    app.run(port=5000)