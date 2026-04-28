# AI Delivery Robots - Hoan Kiem District Simulation

Hệ thống mô phỏng hạm đội robot giao hàng tự hành tại khu vực quận Hoàn Kiếm, Hà Nội. Dự án được xây dựng phục vụ cho bài tập lớn môn học **Nhập môn Trí tuệ Nhân tạo (Introduction to AI)**, tập trung vào việc áp dụng các thuật toán kinh điển để giải quyết bài toán định tuyến, phân cụm và điều phối trong môi trường động.

## 🎯 Mục tiêu:

Hệ thống không chỉ tìm đường đơn thuần mà mô phỏng cách một hệ đa tác tử (Multi-Agent System) vận hành và tối ưu hóa dưới các ràng buộc thực tế:
- **Routing (Tìm đường):** So sánh hiệu năng của A*, Dijkstra, và Greedy Best-First Search (GBFS) trên đồ thị đường đi thực tế.
- **Dynamic Environment (Môi trường động):** Đường đi bị ảnh hưởng bởi Mưa (Rain), Tắc đường (Traffic), và Vật cản (Obstacles), biến thành các hàm phạt (Penalty Costs) đè lên trọng số đồ thị.
- **Unsupervised Learning (Học không giám sát):** Sử dụng K-means để tự động phân tích dữ liệu giao hàng lịch sử và định vị lại các trạm chờ (Hubs) tối ưu.
- **Multi-Agent Dispatching (Điều phối):** Giải quyết bài toán phân công đơn hàng (CSP) và tối ưu hóa thứ tự lấy/giao hàng (TSP/VRP) cho nhiều robot cùng lúc.

## 🛠️ Công nghệ (Tech Stack)

- **Backend:** Python 3.10+, Flask
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
Sau đó, mở trình duyệt và truy cập vào địa chỉ được in ra (mặc định: `http://127.0.0.1:5001`).

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
- [ ] **Advanced K-means:** Cho phép chọn `K` thủ công và cung cấp Auto-K (Elbow method) kèm metrics Before/After.
- [ ] **Explainable AI (XAI) Timeline:** Ghi log và giải thích chi tiết lý do hệ thống gán đơn hàng A cho robot B.
- [ ] **Multi-Agent Dispatching (CSP):** Xây dựng bộ lọc ràng buộc (Pin, Khoảng cách) để quyết định gán đơn.
- [ ] **Vehicle Routing Problem (VRP/TSP):** Áp dụng Simulated Annealing để robot có thể nhận nhiều đơn cùng lúc và tự sắp xếp thứ tự lấy/giao hàng tối ưu.

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