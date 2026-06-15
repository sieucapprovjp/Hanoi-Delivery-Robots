# AI Delivery Robots - Hoan Kiem District Simulation

Hệ thống mô phỏng hạm đội robot giao hàng tự hành tại khu vực quận Hoàn Kiếm, Hà Nội. Dự án được xây dựng phục vụ cho bài tập lớn môn học **Nhập môn Trí tuệ Nhân tạo (Introduction to AI)**, tập trung vào việc áp dụng các thuật toán kinh điển để giải quyết bài toán định tuyến, phân cụm và điều phối trong môi trường động.

## 🎯 Mục tiêu:

Hệ thống không chỉ tìm đường đơn thuần mà mô phỏng cách một hệ đa tác tử (Multi-Agent System) vận hành và tối ưu hóa dưới các ràng buộc thực tế:
- **Routing (Tìm đường):** So sánh hiệu năng của A*, Dijkstra, và Greedy Best-First Search (GBFS) trên đồ thị đường đi thực tế.
- **Dynamic Environment (Môi trường động):** Đường đi bị ảnh hưởng bởi Mưa (Rain), Tắc đường (Traffic), và Vật cản (Obstacles), biến thành các hàm phạt (Penalty Costs) đè lên trọng số đồ thị.
- **Unsupervised Learning (Học không giám sát):** Sử dụng K-means để tự động phân tích dữ liệu giao hàng lịch sử và định vị lại các trạm chờ (Hubs) tối ưu.
- **Multi-Agent Dispatching (Điều phối):** Giải quyết bài toán phân công đơn hàng bằng CSP/XAI và tối ưu hóa thứ tự lấy/giao hàng bằng VRP/PDP cho robot có capacity tối đa 3 đơn.

## 🛠️ Công nghệ (Tech Stack)

- **Backend:** Python 3.10+, Flask, Flask-SocketIO, SimPy
- **AI/Graph Processing:** NetworkX (Xử lý đồ thị), OSMnx (Dữ liệu OpenStreetMap), Scikit-learn (K-means Clustering), NumPy
- **Frontend:** Vanilla JavaScript, Leaflet.js (Bản đồ)

## ⚙️ Cài đặt & Chạy (Setup & Run)

**1. Yêu cầu hệ thống:**
- Python 3.10 trở lên.
- pip (Trình quản lý gói Python).

**2. Cài đặt thư viện:**
```bash
pip install -r requirements.txt
```

**3. Chạy Server:**
```bash
python main.py
```
Sau đó, mở trình duyệt và truy cập vào địa chỉ được in ra (mặc định: `http://127.0.0.1:5000`). Có thể đổi port bằng biến môi trường `PORT`.

## 🧠 AI Logistics hiện có

### Routing và môi trường động

- Routing chạy trên graph OSMnx/NetworkX.
- Các yếu tố mưa, giao thông và vật cản được đưa vào hàm trọng số cạnh.
- Robot có cơ chế replanning khi projected plan-execute gap vượt ngưỡng.
- Có anti-chatter reassignment để tránh robot đổi đơn liên tục.

### Persistent log và K-means

- Delivery history được ghi vào JSONL tại `logs/delivery-history.jsonl`.
- K-means tối ưu hub ưu tiên đọc dữ liệu từ file log; nếu chưa đủ dữ liệu thì fallback về RAM.
- Endpoint `/api/log_delivery` cho phép FE hoặc script ghi pickup/dropoff history.
- Endpoint `/api/optimize-hubs` cập nhật charging hubs và giữ field `spots` để simulation restart ổn định.

### CSP/XAI Dispatch

- Dispatcher chạy qua adapter CSP/XAI quanh các assignment policies hiện có: `nearest_idle`, `nearest_feasible`, `weighted_cost`, `hungarian`.
- CSP filter kiểm tra status idle, battery sanity, capacity, pickup distance, route reachability và route battery feasibility.
- Explanation được lưu trong app state, emit qua websocket `dispatch_explanations_update`, và đọc lại bằng `GET /api/dispatch/explanations`.

### VRP/PDP batching

- Mỗi robot có capacity tối đa 3 đơn.
- VRP sequence giữ ràng buộc pickup trước dropoff.
- Backend dùng greedy seed + simulated annealing để tối ưu thứ tự stop.
- Robot state trả `capacity`, `current_load`, `active_orders` để FE hiển thị khi click robot.

## 📊 Công thức Đánh giá Hiệu quả (Efficiency Metric)

Để so sánh công bằng giữa các thuật toán, hệ thống sử dụng một điểm số tổng hợp (Efficiency Score):
```text
Score = Deliveries / (Distance_Km + 0.02*Time_ms + 0.005*Nodes_Explored + 0.5*Reroutes + 1)
```
*Điểm số càng cao chứng tỏ thuật toán vận hành hạm đội càng hiệu quả dưới điều kiện môi trường hiện tại.*

## 📋 Tiến độ Dự án (Project Roadmap)

- [x] **Core Routing Engine:** Tích hợp đồ thị OSMnx khu vực Hoàn Kiếm.
- [x] **Classical Search Algorithms:** Cài đặt A*, Dijkstra, GBFS với Heuristic Haversine.
- [x] **Dynamic Environment:** Mô phỏng Mưa, Tắc đường, Vật cản làm thay đổi trọng số cạnh đồ thị.
- [x] **Academic Insights:** Giao diện so sánh metrics theo thời gian thực (Nodes explored, Calc time, Path cost).
- [x] **Unsupervised Learning (K-means):** Nút `Optimize Hubs` tự động gom cụm đơn hàng và dời robot về các trọng tâm (Centroids) mới.
- [x] **RL-lite Road Memory:** Robot ghi nhớ các đoạn đường chậm/phạt để né trong các lần tìm đường sau.
- [x] **Explainable AI (XAI) Timeline:** Ghi và hiển thị lý do chọn/reject robot trong Dispatch panel.
- [x] **Multi-Agent Dispatching (CSP):** Bộ lọc ràng buộc cho status, pin, capacity, khoảng cách pickup và route reachability.
- [x] **Vehicle Routing Problem (VRP/PDP):** Simulated Annealing cho batch tối đa 3 đơn/robot với pickup-before-dropoff.
- [ ] **Advanced K-means:** Cho phép chọn `K` thủ công và cung cấp Auto-K (Elbow method) kèm metrics Before/After.

## 🔌 API chính

Chi tiết hơn nằm trong [docs/api_reference.md](docs/api_reference.md).

| Endpoint | Mục đích |
| --- | --- |
| `GET /api/route` | Tính route và cost breakdown theo môi trường hiện tại. |
| `GET /api/snap` | Snap tọa độ về node gần nhất, tương thích API cũ. |
| `GET /api/orders` | Đọc lifecycle của order trong simulation. |
| `POST /api/log_delivery` | Ghi pickup/dropoff history vào RAM và JSONL. |
| `POST /api/optimize-hubs` | Chạy K-means để tối ưu charging hubs. |
| `GET /api/dispatch/model` | Đọc model dispatch hiện tại. |
| `POST /api/dispatch/select` | Chọn assignment policy. |
| `GET /api/dispatch/explanations` | Đọc XAI decisions gần nhất. |
| `POST /api/dispatch/assign` | Compatibility wrapper cho payload dispatch cũ. |

## 📂 Cấu trúc Thư mục

```text
delivery_robots/
  main.py               # Entrypoint chạy server
  requirements.txt      # Các thư viện phụ thuộc
  app.py                # Khởi tạo Flask app & đăng ký route
  algorithms/           # Các thuật toán AI (Search, K-means, Dispatch)
  core/                 # Xử lý đồ thị, môi trường, simulation loop
  routes/               # Định nghĩa các API endpoints
  utils/                # Tiện ích (Tính toán khoảng cách, validation, metrics)
  static/               # Frontend (CSS, JS, Leaflet maps)
  templates/            # Frontend (HTML)
  tests/                # Unit/Integration tests
```
