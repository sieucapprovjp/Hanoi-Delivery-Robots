# Tài liệu Kỹ thuật Backend - AI Delivery Robots

Tài liệu này cung cấp cái nhìn chi tiết về kiến trúc, các module, thuật toán và API của phần Backend trong dự án AI Delivery Robots. Backend được xây dựng bằng **Python (Flask)** và đóng vai trò xử lý tính toán tìm đường, quản lý trạng thái môi trường (thời tiết, giao thông, chướng ngại vật) và điều phối API cho Frontend.

---

## 1. Tổng quan Dự án & Cấu trúc Hệ thống (Project Overview)

### 1.1. Kiến trúc chung
Hệ thống sử dụng **Flask** làm web framework chính. Thay vì thiết kế dạng monolithic truyền thống, mã nguồn được chia thành các module rời rạc nhằm tăng tính bảo trì, khả năng mở rộng và dễ dàng kiểm thử. 

Trạng thái của toàn bộ ứng dụng (Application State) được quản lý tập trung trong file `app.py` thông qua biến từ điển `_app_state`. Biến này lưu trữ cấu trúc đồ thị (bản đồ đường đi), các dữ liệu về môi trường (kẹt xe, khu vực mưa, chướng ngại vật) và cấu hình mô phỏng. Để đảm bảo an toàn đa luồng (thread-safe), các thao tác đọc/ghi dữ liệu chung đều sử dụng `threading.Lock()`.

### 1.2. Cấu trúc thư mục

Toàn bộ logic backend nằm trong thư mục `delivery_robots/`, được phân chia thành các sub-package như sau:

- **`core/`**: Chứa các cấu trúc dữ liệu cốt lõi, quản lý môi trường và bản đồ (Environment, Graph, Hubs).
- **`algorithms/`**: Nơi triển khai các thuật toán tìm đường (A*, Dijkstra, GBFS, Insider) và logic tính toán trọng số tùy chỉnh.
- **`routes/`**: Nơi định nghĩa các API endpoints chia theo nhóm (main_routes, environment_routes).
- **`utils/`**: Các hàm tiện ích hỗ trợ về địa lý (Geo), đánh giá hiệu suất thuật toán (Metrics), phân tích tuyến đường và kiểm tra dữ liệu đầu vào (Validation).

---

## 2. Cốt lõi Hệ thống (Core Components)

Thư mục `core/` bao gồm các module quản lý cấu trúc cốt lõi nhất của bản đồ, thời gian thực, và các yếu tố ngoại cảnh.

### 2.1. Environment (`core/environment.py`)
Mô-đun quản lý các yếu tố môi trường tác động đến chi phí di chuyển:
- **Thời gian mô phỏng (`get_simulation_time`)**: Ánh xạ thời gian thực thành thời gian trong mô phỏng thông qua biến `simulation_speed`.
- **Kẹt xe & Giờ cao điểm (`get_rush_hour_multiplier`, `traffic_penalty_for_point`)**: Tính toán hệ số phạt (penalty) nếu một tọa độ nằm trong tuyến đường kẹt xe. Độ nghiêm trọng của kẹt xe thay đổi theo chu kỳ (`traffic_period_seconds`) và phụ thuộc vào giờ cao điểm (sáng, trưa, tối).
- **Thời tiết (`rain_penalty_for_point`)**: Trả về hệ số phạt nếu tọa độ nằm trong vùng mưa (dựa trên khoảng cách Haversine từ tâm vùng mưa).
- **Chướng ngại vật (`obstacle_penalty_for_point`)**: Tính toán điểm cản trở nếu tọa độ tiệm cận với tâm của một chướng ngại vật đang có trên đường.
- **Trọng số cạnh (`edge_weight_with_traffic`)**: Hàm tổng hợp toàn bộ các hệ số trên để điều chỉnh chiều dài của một cạnh đồ thị. Đây là nền tảng để thuật toán tìm đường trả về con đường tối ưu thực tế (không chỉ là ngắn nhất).

### 2.2. Graph (`core/graph.py`)
Quản lý đồ thị mạng lưới đường giao thông:
- Sử dụng thư viện **OSMnx** để tự động tải cấu trúc đường đi xung quanh một tọa độ trung tâm (mặc định là khu vực Hồ Hoàn Kiếm, Hà Nội).
- Quá trình tải (fetching) và chiếu (projecting) đồ thị chỉ thực hiện 1 lần lúc startup hệ thống (`get_road_graph`) và lưu vào bộ nhớ. Nếu đã tải, sẽ lập tức trả về từ cache để tối ưu tốc độ.
- Tự động sinh ra các tuyến đường có kẹt xe cố định (Traffic Anchors) ngay khi nạp đồ thị lần đầu.

### 2.3. Hubs (`core/hubs.py`)
Quản lý tối ưu hóa điểm tập kết (Hubs) cho Robot:
- Lưu vết lịch sử các điểm lấy và giao hàng của robot (`append_delivery_points`).
- Cung cấp hàm `compute_optimized_hubs` sử dụng thuật toán **K-Means Clustering** (`sklearn.cluster.KMeans`) để gom cụm các tọa độ lịch sử. Từ đó tìm ra số điểm trung tâm (mặc định là 5) làm Hub mới để tối ưu việc phân bổ Robot đón đầu nhu cầu giao hàng trong tương lai.

---

## 3. Thuật toán & Phân chia Nhiệm vụ (Algorithms)

Thư mục `algorithms/` chứa logic tìm đường đi ngắn nhất hoặc tối ưu nhất (Pathfinding). Do đặc thù dự án AI, hệ thống triển khai nhiều thuật toán và cung cấp công cụ để so sánh chúng với nhau.

### 3.1. Tìm đường Sản xuất (Production Search - `weighted_search.py`)
Được sử dụng làm thuật toán "thực chiến" cho robot hoạt động:
- Triển khai hàm `run_weighted_route_search` với cấu trúc chung hỗ trợ 3 thuật toán: **A***, **Dijkstra**, và **Greedy Best-First Search (GBFS)**.
- **Đặc tính cốt lõi**: Thuật toán không chỉ lấy độ dài cạnh vật lý (`edge_length`) mà nhận vào hàm trọng số động (`weight_fn`). Nhờ vậy thuật toán có thể né kẹt xe, tránh vùng mưa lớn hoặc chướng ngại vật theo thời gian thực.
- Cấu trúc sử dụng hàng đợi ưu tiên `heapq` giúp tối ưu tài nguyên tính toán (O(E log V)).

### 3.2. Thuật toán Cổ điển để So sánh (`classical.py`)
Mô-đun này cung cấp các cài đặt "nguyên bản" của 4 thuật toán: A*, Dijkstra, GBFS, và BFS.
- **Điểm khác biệt**: Module này tính đường đi **chỉ dựa trên chiều dài vật lý thuần túy (Base Edge Length)**, KHÔNG cộng thêm bất kỳ hình phạt môi trường (traffic, rain, obstacle) nào.
- Mục đích chính là cung cấp API `/api/classical/compare` cho Frontend để vẽ biểu đồ và phân tích sự khác nhau giữa đường đi "ngắn nhất về lý thuyết" và đường đi "tối ưu nhất trên thực tế" (Production Search).

### 3.3. Thuật toán Mổ xẻ & Trực quan hóa (`insider.py`)
Cung cấp các API chuyên sâu phục vụ mục đích Debug và Vẽ trực quan hóa trên giao diện (Insider / X-Ray Mode):
- `run_astep_demo`: Chạy A* step-by-step. Thuật toán giới hạn vòng lặp (`max_steps=30`) và ghi nhận lại lịch sử mở từng node (ghi lại `g`, `h`, `f`), kích thước danh sách `open_set`, `closed_set` tại mỗi bước.
- `run_insider_comparison`: Tính toán đồng thời A*, Dijkstra, GBFS, và BFS với MỌI ràng buộc môi trường (có penalty) để so sánh về chi phí (Nodes Explored, Time) trong điều kiện thực tế khắc nghiệt.

### 3.4. Logic Phân chia Nhiệm vụ (Task Allocation / Dispatching)
*Lưu ý kiến trúc:* 
- Bản thân logic gán đơn hàng cho robot **được thực hiện ở phía Frontend** (nằm trong class `Simulation` của file `simulation.js`).
- Tuy nhiên, để Frontend ra quyết định, Backend đóng vai trò như hệ thống **Oracle**. Frontend liên tục gọi API Route của Backend để lấy chi phí thực tế (`totalCost`) từ vị trí mỗi robot đến điểm đón khách hàng. 
- Backend cung cấp các metric gồm quãng đường, thời gian ETA dự kiến, và rủi ro hết pin (battery risk) dựa trên thuật toán Pathfinding để Frontend tính điểm (Priority Score) và chọn Robot ưu việt nhất.

---

## 4. Giao diện API (Routes)

Các API của hệ thống chia làm 2 nhóm chính: điều khiển ứng dụng/robot (`main_routes.py`) và môi trường (`environment_routes.py`). Toàn bộ API trả về định dạng JSON.

### 4.1. Main Routes (`/api/...`)
- `GET /api/route`: Trả về mảng tọa độ đường đi tối ưu giữa `fromLat`, `fromLon` và `toLat`, `toLon` dựa trên thuật toán `algo` (astar, dijkstra, gbfs). Bao gồm `costBreakdown` chi tiết các loại penalty.
- `GET /api/snap`: Tìm node giao thông gần nhất của tọa độ cho trước (chức năng Snap to road).
- `POST /api/log_delivery`: Ghi nhận tọa độ giao/nhận hàng thành công phục vụ cho thuật toán tối ưu sau này.
- `POST /api/optimize-hubs`: Gọi hàm K-Means lấy danh sách 5 tọa độ Hub mới.
- `GET /api/astep`: API chuyên biệt chạy thuật toán A* nhưng trả về cả lịch sử `steps` (để render giao diện phân tích từng node).
- `GET /api/insider`: Trả về kết quả so sánh đồng thời của 4 thuật toán (thời gian, số node duyệt) CÓ tính đến penalty giao thông.
- `GET /api/classical/compare`: Trả về so sánh 4 thuật toán KHÔNG tính penalty giao thông (đường đi nguyên bản).

### 4.2. Environment Routes (`/api/...`)
- **Nhóm Logs & Metrics**:
  - `GET / POST /api/logs`: Đọc/Ghi nhật ký hệ thống (phục vụ log Frontend).
  - `GET /api/metrics`: Thông số cấu hình (tổng Node đồ thị, thời gian tính toán trung bình).
  - `GET /api/clock`: Thời gian mô phỏng hiện tại, có đang là Rush Hour (giờ cao điểm) hay không.
- **Nhóm Traffic (Kẹt xe)**:
  - `GET /api/traffic`: Danh sách các tuyến kẹt xe và độ nghiêm trọng theo thời gian thực (severity).
  - `POST /api/traffic/add | randomize | clear | list`: Quản lý danh sách các tuyến đường bị kẹt xe.
- **Nhóm Weather (Thời tiết)**:
  - `GET /api/weather`: Lấy danh sách các vùng mưa lớn (gây tăng penalty di chuyển).
  - `POST /api/rain/add | randomize | clear | list`: Quản lý vùng mưa.
- **Nhóm Obstacles (Chướng ngại vật)**:
  - `POST /api/obstacle/add | randomize | clear | list`: Quản lý các chướng ngại vật ngẫu nhiên trên bản đồ (lô cốt, tai nạn).

---

## 5. Các Tiện ích (Utilities)

Thư mục `utils/` tập hợp các logic tính toán phụ trợ, giúp làm sạch và module hóa mã nguồn chính.

- **`utils/geo.py`**:
  - `haversine_distance`: Tính khoảng cách chim bay (mét) giữa 2 tọa độ lat/lon. (Là hàm Heuristic h(n) chủ chốt cho thuật toán A* và GBFS).
  - `point_to_segment_distance_meters`: Tính khoảng cách từ 1 điểm đến 1 đoạn thẳng (Dùng để xác định 1 tọa độ có nằm trên một tuyến đường đang bị kẹt xe hay không).
- **`utils/metrics.py`**: Ghi nhận và tính trung bình thời gian thực thi (ms), số lượng node mở rộng (`nodes_explored`) của hàng trăm lệnh gọi tìm đường, phục vụ dashboard tổng quan.
- **`utils/route_analysis.py`**:
  - `nearest_node_id`: Tìm Node gần nhất trong đồ thị tính từ tọa độ bất kỳ. Dùng để "Snap" tọa độ người dùng chọn vào lưới giao thông.
  - `build_route_response`: Biến đổi danh sách các Node trả về từ thuật toán thành một Payload JSON chuẩn. Hàm này cũng lặp qua từng cạnh của đường đi để tính ra giá trị phạt kẹt xe, thời tiết... trả về trong object `costBreakdown`.
- **`utils/validation.py`**: Bộ kiểm tra đầu vào (validate lat/lon, kiểu dữ liệu) để đảm bảo API không bị crash khi Frontend gửi request sai định dạng.

---
**Tài liệu được trích xuất tự động và hoàn chỉnh.** Dùng để tra cứu logic xử lý phía Backend của dự án.
