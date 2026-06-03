# AI Delivery Robots - Hoan Kiem Simulation

Du an mo phong doi robot giao hang tu hanh trong khu vuc Hoan Kiem, Ha Noi. Backend dung Flask de tinh toan do thi duong di, tim duong, dieu phoi don hang va quan ly moi truong dong. Frontend dung Leaflet va JavaScript de hien thi ban do, robot, khu vuc mua, tac duong, vat can va cac bang so sanh thuat toan.

Muc tieu chinh cua du an la minh hoa cac ky thuat AI co dien trong bai toan giao hang:

- Tim duong tren do thi: A*, Dijkstra, Greedy Best-First Search va BFS.
- Trong so dong: chi phi canh thay doi theo traffic, rain, obstacle va rush hour.
- Dieu phoi nhieu robot: gan don theo priority, chi phi duong di va rui ro pin.
- Hoc khong giam sat: K-means toi uu vi tri hub dua tren lich su pickup/dropoff.
- Road memory: robot ghi nho doan duong cham va gui penalty nguoc ve backend khi tinh duong lai.

## Chay Du An

Yeu cau:

- Python 3.10+
- pip

Cai thu vien:

```bash
pip install -r requirements.txt
```

Chay server:

```bash
python main.py
```

Mac dinh ung dung chay tai:

```text
http://127.0.0.1:5002
```

Co the doi port bang bien moi truong `PORT`.

## Luong Hoat Dong Tong Quan

```text
Browser
  -> delivery_robots/templates/index.html
  -> delivery_robots/static/js/*.js
  -> Flask API trong delivery_robots/routes/
  -> Thuat toan trong delivery_robots/algorithms/
  -> Do thi va moi truong trong delivery_robots/core/
  -> Response JSON ve frontend de ve route va cap nhat metrics
```

Khi robot can tim duong, frontend goi `GET /api/route` hoac backend goi truc tiep trong `POST /api/dispatch/assign`. Backend snap toa do vao node gan nhat tren do thi OSMnx, chay thuat toan tim duong, tinh cost breakdown, roi tra ve danh sach toa do de robot di chuyen tren ban do.

## Can Doc Gi Khi Lam Task Thuat Toan Tim Duong

Neu task cua ban la code, sua hoac danh gia thuat toan tim duong, nen doc theo thu tu sau:

1. `delivery_robots/algorithms/weighted_search.py`
   - File quan trong nhat cho route robot dang dung that.
   - Ham chinh: `run_weighted_route_search(...)`.
   - Ho tro `astar`, `dijkstra`, `gbfs`.
   - Nhan `weight_fn` tu ben ngoai, vi vay thuat toan khong tu tinh traffic/rain/obstacle ma dung ham trong so duoc truyen vao.

2. `delivery_robots/core/environment.py`
   - Noi tinh penalty moi truong.
   - Ham quan trong: `edge_weight_with_traffic(...)`.
   - Cost canh = do dai canh * traffic penalty * rain penalty * obstacle penalty.
   - Neu task lien quan "tranh tac duong", "tranh mua", "tranh vat can", doc file nay truoc khi sua thuat toan.

3. `delivery_robots/routes/main_routes.py`
   - Noi endpoint `/api/route` parse query, validate toa do, chon algorithm, goi `run_weighted_route_search`, roi build response.
   - Cung co `/api/classical/compare`, `/api/astep`, `/api/insider`, `/api/dispatch/assign`.
   - Neu them algorithm moi, can them vao validation/config va route xu ly o day.

4. `delivery_robots/utils/route_analysis.py`
   - `nearest_node_id(...)`: snap lat/lon vao node gan nhat tren graph.
   - `build_route_response(...)`: doi route node thanh danh sach toa do va tinh `costBreakdown`.
   - Neu response frontend thieu field, sai distance, sai penalty, doc file nay.

5. `delivery_robots/utils/geo.py`
   - `haversine_distance(...)` la heuristic cho A* va GBFS.
   - `point_to_segment_distance_meters(...)` dung de tinh anh huong cua traffic route.

6. `delivery_robots/algorithms/classical.py`
   - Ban cai dat thuat toan co dien dung de so sanh.
   - Khac voi `weighted_search.py`: file nay chi dung edge length co ban, khong tinh penalty moi truong.
   - Nen doc neu task yeu cau so sanh A*, Dijkstra, GBFS, BFS.

7. `delivery_robots/algorithms/insider.py`
   - Dung cho visualization tung buoc A* va so sanh insider.
   - Neu sua logic A* ma UI "A* Expansion Step-by-Step" sai, can cap nhat file nay.

8. `delivery_robots/static/js/pathfinding.js`
   - Client wrapper goi `/api/route`, `/api/snap`, `/api/traffic`, `/api/weather`.
   - Neu thay doi API contract, can sua file nay.

9. `delivery_robots/static/js/robot.js`
   - Noi robot goi route, di theo path, reroute khi gap traffic/rain, ghi road memory.
   - Neu task lien quan robot tu dong reroute hoac hoc doan duong cham, doc file nay.

10. Tests lien quan:
    - `tests/test_api.py`: test `/api/route`, `/api/classical/compare`, traffic API.
    - `tests/test_classical_ai.py`: test thuat toan co dien.
    - `tests/test_route_analysis.py`: test cost breakdown.

## API Quan Trong Cho Tim Duong

### `GET /api/route`

Query:

```text
fromLat=<float>
fromLon=<float>
toLat=<float>
toLon=<float>
algo=astar|dijkstra|gbfs
memory=<JSON object optional>
```

Response chinh:

```json
{
  "path": [{"lat": 21.0, "lon": 105.0}],
  "distance": 100.0,
  "costBreakdown": {
    "baseDistance": 100.0,
    "trafficPenalty": 0.0,
    "rainPenalty": 0.0,
    "obstaclePenalty": 0.0,
    "totalCost": 100.0,
    "estimatedMinutes": 0.6
  },
  "algo": "astar",
  "timeMs": 3.21,
  "nodesExplored": 42,
  "pathCost": 100.0
}
```

### `GET /api/classical/compare`

Dung de so sanh A*, Dijkstra, Greedy Best-First va BFS tren edge length co ban. Endpoint nay khong tinh traffic/rain/obstacle penalty.

### `GET /api/astep`

Tra ve tung buoc mo node cua A* de frontend hien thi `g`, `h`, `f`, open set va closed set.

### `POST /api/dispatch/assign`

Dung khi frontend can gan don cho robot. Backend tinh route tu tung robot den pickup, tinh total score va tra ve assignment kem route da tinh san.

## Cau Truc Thu Muc Va File

```text
.
|-- .gitignore
|-- README.md
|-- main.py
|-- requirements.txt
|-- delivery_robots/
|   |-- __init__.py
|   |-- app.py
|   |-- config.py
|   |-- algorithms/
|   |   |-- __init__.py
|   |   |-- classical.py
|   |   |-- insider.py
|   |   |-- weighted_search.py
|   |   `-- dispatch/
|   |       |-- __init__.py
|   |       `-- allocation.py
|   |-- core/
|   |   |-- __init__.py
|   |   |-- environment.py
|   |   |-- graph.py
|   |   `-- hubs.py
|   |-- routes/
|   |   |-- __init__.py
|   |   |-- environment_routes.py
|   |   `-- main_routes.py
|   |-- utils/
|   |   |-- __init__.py
|   |   |-- geo.py
|   |   |-- metrics.py
|   |   |-- route_analysis.py
|   |   `-- validation.py
|   |-- templates/
|   |   `-- index.html
|   `-- static/
|       |-- css/
|       |   `-- style.css
|       `-- js/
|           |-- app.js
|           |-- config.js
|           |-- map.js
|           |-- pathfinding.js
|           |-- robot.js
|           `-- simulation.js
|-- docs/
|   |-- backend_documentation.md
|   |-- kmeans_plan.md
|   |-- vrp_implementation_plan.md
|   `-- vrp_research.md
`-- tests/
    |-- __init__.py
    |-- test_api.py
    |-- test_classical_ai.py
    |-- test_route_analysis.py
    `-- test_validation.py
```

## Mo Ta Chi Tiet Tung File

### Root

- `.gitignore`: Danh sach file/folder Git bo qua, thuong gom cache Python, virtualenv, IDE files.
- `README.md`: Tai lieu tong quan du an, cau truc repo va huong dan cho task tim duong.
- `main.py`: Entrypoint chay server. Nap Flask app, goi `get_road_graph()` de tai graph OSMnx, sau do chay app tren `127.0.0.1`.
- `requirements.txt`: Phu thuoc Python: Flask, OSMnx, NetworkX, scikit-learn, NumPy.

### `delivery_robots/`

- `__init__.py`: Export cac object/hook chinh de tests va module khac import: Flask app, graph getter, validation helpers, `compare_classical_algorithms`, `build_route_response`.
- `app.py`: Khoi tao Flask app, quan ly state toan cuc, lock, graph cache, delivery history, traffic/rain/obstacle state, metrics va dang ky route.
- `config.py`: Noi tap trung hang so cau hinh: graph center, simulation speed, rush hours, traffic/rain/obstacle defaults, valid algorithms, K-means settings, metrics/log settings.

### `delivery_robots/algorithms/`

- `__init__.py`: Export cac ham thuat toan chinh: classical compare, insider demo, weighted route search.
- `weighted_search.py`: Engine tim duong production. Dung priority queue `heapq`, ho tro A*, Dijkstra, GBFS, nhan `weight_fn` de tinh chi phi canh dong.
- `classical.py`: Cai dat A*, Dijkstra, GBFS va BFS phien ban co dien de so sanh. Chi tinh `length`, khong dung penalty moi truong.
- `insider.py`: Chay A* tung buoc va so sanh nhieu thuat toan phuc vu giao dien "Insider View".

### `delivery_robots/algorithms/dispatch/`

- `__init__.py`: Marker package cho module dispatch.
- `allocation.py`: Logic gan don hang cho robot. Tinh priority score, duyet robot kha dung, tinh route den pickup, cong battery risk va chon assignment co total score thap nhat.

### `delivery_robots/core/`

- `__init__.py`: Marker package cho core.
- `graph.py`: Tai graph duong di bang OSMnx tu toa do trung tam Hoan Kiem, project graph va tao BallTree de tim node gan nhat nhanh.
- `environment.py`: Tinh simulation time, rush hour multiplier, traffic penalty, rain penalty, obstacle penalty va edge weight tong hop.
- `hubs.py`: Luu lich su diem pickup/dropoff va chay K-means de tinh hub moi.

### `delivery_robots/routes/`

- `__init__.py`: Export ham dang ky route.
- `main_routes.py`: Cac endpoint nghiep vu chinh: trang index, route, snap, log delivery, dispatch assign, optimize hubs, A* step demo, insider comparison, classical compare.
- `environment_routes.py`: Cac endpoint moi truong va telemetry: health, logs, metrics, clock, charging stations, traffic, weather, rain, obstacle.

### `delivery_robots/utils/`

- `__init__.py`: Marker package cho utilities.
- `geo.py`: Ham dia ly: Haversine distance, doi lat/lon sang local XY, tinh khoang cach tu diem den doan thang.
- `metrics.py`: Tao, cap nhat va build payload metrics cho route calculation.
- `route_analysis.py`: Snap toa do vao graph node, trich geometry cua edge, build route response va cost breakdown.
- `validation.py`: Validate input API: coordinate, lat/lon range, positive number, non-negative int.

### `delivery_robots/templates/`

- `index.html`: Trang chinh cua ung dung. Nap Leaflet, Alpine store, cac panel UI va script frontend.

### `delivery_robots/static/css/`

- `style.css`: Style cho ban do, panel, nut dieu khien, robot card, popup, bang metrics va visualization.

### `delivery_robots/static/js/`

- `config.js`: Cau hinh frontend: map settings, robot settings, simulation constants, API paths, UI constants va data dia diem mau.
- `map.js`: Quan ly Leaflet map, tram sac, traffic overlay, rain overlay, delivery markers va hub markers.
- `pathfinding.js`: Lop client goi API pathfinding/environment va normalize cost estimate.
- `robot.js`: Lop `DeliveryRobot`: trang thai robot, route assignment, di chuyen theo path, reroute, sac pin, road memory va metrics tung robot.
- `simulation.js`: Quan ly vong lap mo phong, tao robot, tao don, goi dispatch API, cap nhat status, tinh efficiency score va toi uu hub.
- `app.js`: Khoi tao ung dung, bind event UI, quan ly panel, rain/traffic/obstacle controls, metrics polling va insider visualization.

### `docs/`

- `backend_documentation.md`: Tai lieu backend chi tiet. Hien file nay dang bi loi encoding tieng Viet trong repo.
- `kmeans_plan.md`: Ke hoach va API contract cho tinh nang K-means optimize hubs.
- `vrp_implementation_plan.md`: Ke hoach mo rong VRP/TSP voi Simulated Annealing, gom backend, frontend va tests can them/sua.
- `vrp_research.md`: Ghi chu nghien cuu VRP/TSP/PDP va cach gan vao he thong hien tai. File hien dang bi loi encoding tieng Viet.

### `tests/`

- `__init__.py`: Marker package cho tests.
- `test_api.py`: Test Flask API bang graph gia lap: health, traffic add/list, route cost breakdown, classical compare, validate rain radius.
- `test_classical_ai.py`: Test `compare_classical_algorithms` tren graph nho va xac nhan best path cost.
- `test_route_analysis.py`: Test `build_route_response` co tinh traffic/rain/obstacle penalty dung.
- `test_validation.py`: Test cac ham validate input.

## Cong Thuc Efficiency Score

Frontend tinh score de so sanh hieu qua fleet:

```text
Score = Deliveries / (Distance_Km + 0.02*Time_ms + 0.005*Nodes_Explored + 0.5*Reroutes + 1)
```

Score cao hon nghia la hoan thanh nhieu don hon voi chi phi duong di, thoi gian tinh, so node mo rong va so lan reroute thap hon.

## Ghi Chu Khi Them Algorithm Moi

Neu them thuat toan moi, can kiem tra nhung diem sau:

- Them ten algorithm vao `VALID_ROUTING_ALGORITHMS` trong `delivery_robots/config.py`.
- Cap nhat `run_weighted_route_search(...)` trong `delivery_robots/algorithms/weighted_search.py`.
- Neu frontend cho chon algorithm, cap nhat `CONFIG.SIMULATION.ALGORITHMS` va dropdown trong `index.html`.
- Cap nhat `delivery_robots/static/js/simulation.js` neu can hien thi metrics rieng.
- Them test trong `tests/test_api.py` hoac tao test rieng cho algorithm moi.
- Neu algorithm co visualization, cap nhat `delivery_robots/algorithms/insider.py` va `delivery_robots/static/js/app.js`.
