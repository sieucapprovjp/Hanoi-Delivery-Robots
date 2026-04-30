# Mô tả cấu trúc hệ thống và định hướng thiết kế Backend DES

Tài liệu này mô tả chi tiết trạng thái hiện tại của dự án và các thành phần cốt lõi phục vụ việc thiết kế hệ thống mô phỏng thời gian thực (Discrete Event Simulation - DES) thay thế cho hệ thống cũ.

> [!IMPORTANT]
> **Tài liệu/File quan trọng cần đọc:**
> *   **`delivery_robots/config.py`**: Cấu hình tập trung phía Backend. Chứa hằng số hệ thống, tham số môi trường, logic penalty. **TUYỆT ĐỐI KHÔNG HARDCODE** giá trị mới vào code, hãy đưa vào đây.
> *   **`delivery_robots/core/data.py`**: Dữ liệu hệ thống tĩnh (vị trí trạm sạc, các điểm giao hàng, đội xe ban đầu).
> *   **`delivery_robots/static/js/config.js`**: Cấu hình hiển thị và API endpoints phía Frontend.
> *   **`docs/mo_ta.md`**: (Chính là file này) Tổng quan kiến trúc.

## 1. Cấu trúc dự án hiện tại

Dự án hiện được tổ chức theo kiến trúc Backend-driven với Frontend đóng vai trò là Viewer (hiển thị). Dữ liệu thực tế về hạ tầng và trạng thái được Backend quản lý và cung cấp qua API.

### 1.1 Backend (Python / Flask)
*   **`delivery_robots/app.py`**: Điểm khởi đầu ứng dụng. Quản lý trạng thái hệ thống (`_app_state`) sử dụng threading locks.
*   **`delivery_robots/core/`**:
    *   `data.py`: Chứa dữ liệu tĩnh về hạ tầng (Locations, Hubs, Robots). Thay thế cho việc hardcode ở Frontend.
    *   `environment.py`: Logic tính toán thời gian mô phỏng, tính toán penalty cho trọng số cạnh.
    *   `graph.py`: Xây dựng đồ thị đường bộ từ OSMnx.
    *   `hubs.py`: Quản lý trạm sạc/trạm điều phối.
*   **`delivery_robots/algorithms/`**: Thuật toán tìm đường và phân bổ đơn hàng.
*   **`delivery_robots/routes/`**: 
    *   `main_routes.py`: API lấy dữ liệu tĩnh (`/api/data/...`), tính toán lộ trình.
    *   `environment_routes.py`: API cập nhật/lấy trạng thái môi trường (traffic, rain, obstacles).

### 1.2 Frontend (JavaScript / Leaflet)
*   **`main.js`**: Điều phối hiển thị, polling dữ liệu động từ backend.
*   **`viewer/`**:
    *   `DisplayEngine.js`: Khởi tạo Viewer, fetch dữ liệu hạ tầng từ Backend API thay vì dùng mock data.
    *   `HanoiMap.js`: Hiển thị bản đồ, Render các Hubs và Locations lấy từ Backend.
    *   `DeliveryRobot.js`: Biểu diễn đồ họa của robot.

## 2. Chi tiết trạng thái mô phỏng hiện tại

*   **Thời gian (Clock)**: Hiện đang dựa trên `time.time()` kết hợp với `SIMULATION_SPEED`. Đây là cơ chế "time-stepped" phụ thuộc vào tốc độ thực thi của hệ thống.
*   **Đồ thị (Graph)**: Sử dụng NetworkX, tọa độ dạng Lat/Lon. Trọng số cạnh (`length`) được nhân với các hệ số penalty động.
*   **Môi trường**:
    *   `rain_zones`: Các vùng tròn có bán kính và độ nghiêm trọng.
    *   `traffic_routes`: Các tuyến đường bị ảnh hưởng bởi lưu lượng giao thông theo chu kỳ.
    *   `obstacles`: Các điểm chặn đường cố định hoặc ngẫu nhiên.

## 3. Định hướng thiết kế Backend DES (Discrete Event Simulation)

Thay thế cơ chế "Frontend time stepped" bằng một hệ thống mô phỏng sự kiện rời rạc phía Backend.

### 3.1 Thành phần công nghệ
*   **Celery**: Sử dụng để lập lịch và thực thi các sự kiện mô phỏng (tasks).
*   **Redis**: Làm message broker cho Celery và lưu trữ trạng thái mô phỏng (shared state) để đảm bảo hiệu năng và khả năng truy cập đồng thời.

### 3.2 Cơ chế mô phỏng (DES)
*   **Event-driven**: Mô phỏng tiến triển theo danh sách các sự kiện được xếp hàng (event queue) theo thời gian `t`.
*   **Độ chính xác (Precision)**: Các phép tính khoảng cách và thời gian di chuyển phải được thực hiện chính xác trên đồ thị (sử dụng haversine và logic nội suy đường bộ).

### 3.3 Khả năng Reroute và Sự kiện ngẫu nhiên
*   Hệ thống cần hỗ trợ chèn các sự kiện ngẫu nhiên (`RAIN_START`, `ROAD_BLOCK`) vào hàng đợi.
*   Khi có sự kiện ảnh hưởng đến trọng số đồ thị, các robot đang di chuyển phải có khả năng nhận tín hiệu và tính toán lại lộ trình (Reroute) ngay lập tức từ vị trí hiện tại.

### 3.4 Tương thích thuật toán
*   Kiến trúc cần tách biệt logic mô phỏng (movement) và logic tìm đường (pathfinding).
*   Hỗ trợ "Algorithm Interface" để dễ dàng thay đổi giữa A*, Dijkstra, hoặc các thuật toán tùy chỉnh khác mà không làm thay đổi lõi mô phỏng.

---
*Lưu ý: Tài liệu này chỉ phục vụ mục đích mô tả cấu trúc, không bao gồm các mã triển khai cho hệ thống mới.*
