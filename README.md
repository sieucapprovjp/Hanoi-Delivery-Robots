# AI Delivery Robots - Hoan Kiem District Simulation

Hệ thống mô phỏng hạm đội robot giao hàng tự hành tại khu vực quận Hoàn Kiếm, Hà Nội. Dự án phục vụ bài tập lớn môn **Nhập môn Trí tuệ Nhân tạo**, tập trung vào cách các thuật toán AI kinh điển phối hợp trong một bài toán giao vận động: tìm đường, điều phối robot, giải thích quyết định, gom cụm nhu cầu và tối ưu thứ tự giao hàng.

## Mục Tiêu

Hệ thống không chỉ tìm đường ngắn nhất, mà mô phỏng một pipeline AI hoàn chỉnh:

- **Routing:** A*, Dijkstra và Greedy Best-First Search chạy trên đồ thị đường thật từ OpenStreetMap.
- **Dynamic weights:** mưa, tắc đường, vật cản và road memory tác động trực tiếp lên trọng số cạnh.
- **CSP dispatch:** lọc robot theo trạng thái, pin, sức chứa và khoảng cách pickup trước khi chấm điểm.
- **XAI timeline:** giải thích vì sao robot bị loại, được chấm điểm, được chọn hoặc bị prune.
- **K-means hubs:** gom cụm tọa độ đơn hàng để tối ưu vị trí hub/trụ sạc.
- **VRP/PDP:** robot nhận tối đa 3 đơn, dùng Simulated Annealing để tối ưu thứ tự pickup/dropoff.
- **Lightweight logs:** lưu event và delivery history ra JSONL để phục vụ phân tích mà không cần database.

## Tech Stack

- **Backend:** Python 3.10+, Flask
- **AI/Graph:** NetworkX, OSMnx, scikit-learn, NumPy
- **Frontend:** Vanilla JavaScript, Alpine.js, Leaflet.js
- **Testing:** Python `unittest`, `node --check`

## Setup & Run

1. Cài dependency:

```bash
pip install -r requirements.txt
```

2. Chạy server:

```bash
python main.py
```

3. Mở app:

```text
http://127.0.0.1:5002
```

Port có thể đổi bằng biến môi trường `PORT`.

## Demo Flow

Một luồng demo ngắn, đủ bao phủ các phần AI chính:

1. Chạy simulation và so sánh A*, Dijkstra, GBFS trong **Academic Insights**.
2. Thêm mưa/tắc đường/vật cản để thấy route đổi vì dynamic edge weights.
3. Mở XAI timeline để giải thích dispatch CSP: robot nào bị reject, robot nào được chọn.
4. Quan sát Robot Fleet: mỗi robot có `Capacity 3`, hiển thị active orders và stop progress.
5. Khi queue đủ áp lực, VRP gộp nhiều đơn và hiển thị sequence `P... -> D...` cùng cost trước/sau Simulated Annealing.
6. Chạy **Optimize Hubs** để K-means dời hub/trụ sạc theo lịch sử pickup/dropoff.

## Key Features

### Routing & Dynamic Environment

- Production route search hỗ trợ `astar`, `dijkstra`, `gbfs`.
- Route response có cost breakdown: base distance, traffic penalty, rain penalty, obstacle penalty, total cost.
- Robot có road memory để tránh lặp lại các đoạn đường từng gây chậm/reroute.

### Dispatch CSP & XAI

- CSP pre-route kiểm tra:
  - robot idle
  - pin tối thiểu
  - capacity còn chỗ
  - pickup không quá xa
- Post-route kiểm tra pin dự phòng và ETA.
- XAI timeline giải thích từng bước: priority, pruning, scoring, rejection, selection.

### VRP/PDP With Simulated Annealing

- Robot capacity mặc định: `3` đơn đang active.
- Backend giải sequence pickup/dropoff bằng Simulated Annealing, giữ ràng buộc pickup trước dropoff.
- VRP dùng cùng weighted routing stack, nên mưa/tắc đường/vật cản/road memory đều ảnh hưởng đến cost.
- Frontend hiển thị:
  - active orders
  - capacity/load
  - next stop
  - stop progress
  - VRP initial cost, final cost, improvement, iterations, accepted moves

### K-means Hub Optimization

- App lưu tọa độ pickup/dropoff từ các đơn phát sinh.
- `/api/optimize-hubs` chạy K-means để tìm centroids, ưu tiên dữ liệu từ `logs/delivery-history.jsonl` và fallback RAM nếu file chưa đủ điểm.
- Frontend vẽ hub mới và có thể reposition robot/trụ sạc theo cụm nhu cầu.

### Logs

- `/api/logs` lưu event UI/dispatch trong bộ nhớ và append ra JSONL.
- `/api/log_delivery` lưu pickup/dropoff history cho K-means vào RAM và `logs/delivery-history.jsonl`.
- File runtime:
  - `logs/app-events.jsonl`
  - `logs/delivery-history.jsonl`

Các file JSONL nằm trong `logs/` được ignore khỏi Git.

## Efficiency Metric

Hệ thống dùng điểm tổng hợp để so sánh hiệu quả vận hành:

```text
Score = Deliveries / (Distance_Km + 0.02*Time_ms + 0.005*Nodes_Explored + 0.5*Reroutes + 1)
```

Điểm càng cao nghĩa là đội robot hoàn thành nhiều đơn hơn với ít chi phí đường đi, thời gian tính toán, node explored và reroute hơn.

## API Highlights

- `GET /api/route`: tìm route có dynamic cost breakdown.
- `GET /api/snap`: snap tọa độ về road graph.
- `POST /api/dispatch/assign`: CSP + scoring + VRP batch assignment.
- `POST /api/log_delivery`: ghi pickup/dropoff history.
- `POST /api/optimize-hubs`: chạy K-means hub optimization.
- `GET /api/astep`: A* step-by-step visualization.
- `GET /api/insider`: so sánh thuật toán insider view.
- `GET /api/classical/compare`: so sánh classical algorithms.
- `GET/POST /api/logs`: đọc/ghi app logs.
- Environment APIs: rain, traffic, obstacle, charging stations, metrics, clock.

## Test Commands

```bash
python -m unittest discover -s tests
```

```bash
python -m compileall -q delivery_robots tests
```

PowerShell:

```powershell
Get-ChildItem delivery_robots/static/js -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
```

## Project Status

Đủ scope để demo/nộp project Intro AI:

- [x] Core routing engine với Hoàn Kiếm OSM graph
- [x] A*, Dijkstra, GBFS
- [x] Dynamic environment: rain, traffic, obstacles
- [x] Road memory/reroute avoidance
- [x] Academic metrics and insider comparison
- [x] CSP dispatch constraints
- [x] XAI dispatch timeline
- [x] K-means hub optimization
- [x] VRP/PDP multi-order routing with Simulated Annealing
- [x] JSONL logging for app events and delivery history

Có thể mở rộng sau nếu còn thời gian:

- [ ] Advanced K-means: chọn `K`, Auto-K/Elbow, before/after metrics
- [ ] JSONL log analyzer/dashboard
- [ ] README screenshots/demo GIF
- [ ] UI polish cuối cho presentation

## Folder Structure

```text
.
├── main.py                         # Entrypoint chạy Flask server
├── requirements.txt                # Python dependencies
├── delivery_robots/
│   ├── app.py                      # Flask app, shared state, route registration
│   ├── algorithms/                 # Search, insider, dispatch, VRP solver
│   ├── core/                       # Graph, environment, hub optimization
│   ├── routes/                     # API endpoints
│   ├── static/                     # Frontend JS/CSS assets
│   ├── templates/                  # HTML template
│   └── utils/                      # Geo, metrics, validation, logs, route analysis
├── docs/                           # Architecture, API, convention, plans
├── tests/                          # Unit/integration tests
└── logs/                           # Runtime JSONL logs, ignored by Git
```
