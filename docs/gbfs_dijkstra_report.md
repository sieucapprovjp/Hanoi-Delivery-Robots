# Báo cáo thực hiện thuật toán GBFS và Dijkstra

## 1. Mục tiêu
- Nghiên cứu và triển khai hai thuật toán tìm đường: Dijkstra và GBFS (Greedy Best-First Search).
- Tạo giao diện so sánh hiệu suất theo thời gian thực giữa các thuật toán trên bản đồ mô phỏng robot giao hàng.
- Cung cấp cơ sở lý thuyết và kết quả thực nghiệm để phục vụ báo cáo học tập.

## 2. Cơ sở lý thuyết

### 2.1 Dijkstra
- Dijkstra là thuật toán tìm đường ngắn nhất trên đồ thị có trọng số không âm.
- Thuật toán ưu tiên mở rộng nút có khoảng cách tổng chi phí nhỏ nhất từ điểm bắt đầu.
- Công thức ưu tiên: $f(n) = g(n)$, trong đó $g(n)$ là chi phí thực tế từ start tới nút $n$.
- Ưu điểm: luôn tìm được đường tối ưu nếu trọng số không âm.
- Nhược điểm: xét nhiều nút hơn, thời gian chạy lớn hơn so với các thuật toán heuristic.

### 2.2 GBFS
- GBFS là thuật toán tìm kiếm heuristic, ưu tiên mở rộng nút có khoảng cách ước lượng gần đích nhất.
- Công thức ưu tiên: $f(n) = h(n)$.
- $h(n)$ được tính bằng khoảng cách Haversine từ nút hiện tại tới đích.
- Ưu điểm: nhanh hơn về mặt khám phá và thường mở ít nút hơn trên các bài toán thực tế.
- Nhược điểm: không đảm bảo tìm được đường tối ưu, vì có thể chọn đường “đẹp” về heuristic nhưng không tối ưu về chi phí thực tế.

### 2.3 So sánh giữa Dijkstra và GBFS
- Dijkstra ưu tiên tối ưu chi phí, GBFS ưu tiên tốc độ heuristic.
- Trong project, Dijkstra được dùng như baseline cho đường đi tối ưu, GBFS được dùng để minh họa cách heuristic có thể rút ngắn quy trình tìm đường.

## 3. Những phần đã triển khai trong project

### 3.1 Backend
- File chính triển khai thuật toán:
  - [delivery_robots/algorithms/classical.py](delivery_robots/algorithms/classical.py)
    - Chứa hàm `run_dijkstra(...)` cho Dijkstra.
    - Chứa hàm `run_greedy_best_first(...)` cho GBFS.
    - Chứa hàm `compare_classical_algorithms(...)` dùng để so sánh nhiều thuật toán cùng lúc.
- File cung cấp dữ liệu cho UI insider comparison:
  - [delivery_robots/algorithms/insider.py](delivery_robots/algorithms/insider.py)
    - Tạo kết quả so sánh giữa A*, Dijkstra, GBFS và BFS.
    - Trả về các thông số như `path_length`, `nodes_explored`, `time_ms`, `optimal`.
- File điều hướng API route:
  - [delivery_robots/routes/main_routes.py](delivery_robots/routes/main_routes.py)
    - Kết nối request từ frontend tới backend.
    - Cung cấp các endpoint như `/api/route`, `/api/insider`, `/api/classical/compare`.

### 3.2 Frontend
- File chính hiển thị bảng so sánh:
  - [delivery_robots/static/js/insider/insider_panel.js](delivery_robots/static/js/insider/insider_panel.js)
    - Hiển thị bảng so sánh thời gian thực.
    - Đưa ra các thông số: số nút mở rộng, thời gian chạy, độ dài đường đi, độ tối ưu.
- File cấu hình giao diện và endpoint:
  - [delivery_robots/static/js/core/config.js](delivery_robots/static/js/core/config.js)
    - Chứa các endpoint API và cấu hình hiển thị.
- File gọi API route:
  - [delivery_robots/static/js/core/api_client.js](delivery_robots/static/js/core/api_client.js)
    - Gửi request từ frontend tới backend.
- File template giao diện chính:
  - [delivery_robots/templates/index.html](delivery_robots/templates/index.html)
    - Chứa khu vực hiển thị insider panel và bảng so sánh.

### 3.3 Kiểm thử
- File kiểm thử cho thuật toán:
  - [tests/test_classical_ai.py](tests/test_classical_ai.py)
    - Kiểm tra việc trả về kết quả cho Dijkstra, A*, GBFS và BFS.
    - Đảm bảo GBFS được xuất hiện như một thuật toán độc lập.

### 3.4 Tài liệu và báo cáo
- [docs/gbfs_dijkstra_report.md](docs/gbfs_dijkstra_report.md)
  - Tài liệu tổng hợp mục tiêu, lý thuyết, triển khai và kết quả.

## 4. Cách hoạt động trong hệ thống
1. Người dùng chọn điểm bắt đầu và điểm đích.
2. Hệ thống chuyển tọa độ sang node gần nhất trên đồ thị.
3. Thuật toán Dijkstra hoặc GBFS chạy trên đồ thị.
4. Kết quả được trả về dưới dạng đường đi, số nút mở rộng, thời gian thực thi và trạng thái tối ưu.
5. Frontend vẽ bảng so sánh và hiển thị insight trực quan.

## 5. Kết quả kiểm chứng
- Chạy lệnh kiểm thử:
  - `python -m unittest tests.test_classical_ai -v`
- Kết quả: 2 test passed, 0 failed.

## 6. Kết luận
- Dijkstra phù hợp cho bài toán cần độ tối ưu tuyệt đối về chi phí đường đi.
- GBFS phù hợp khi cần phản hồi nhanh và chấp nhận rủi ro tối ưu không đảm bảo.
- Việc tích hợp hai thuật toán vào hệ thống giúp project có khả năng demo trực quan và dễ hiểu hơn cho người xem.
