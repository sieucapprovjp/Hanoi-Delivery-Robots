 # PHÂN TÍCH CHI TIẾT CODEBASE — BÁO CÁO BÀI TẬP LỚN AI

  **Dự án:** AI Delivery Robots – Simulation khu vực Hoàn Kiếm, Hà Nội
  **Tech Stack:** Python 3.10+ (Flask), NetworkX, OSMnx, Scikit-learn (K-means), Vanilla JS + Leaflet.js

  > **Đặc thù của bài toán:** Không phải tìm đường trên lưới ô số (grid 2D) truyền thống, mà là **tìm đường trên đồ thị
  đường phố thực** (OpenStreetMap). Mỗi "trạng thái" là một node (giao lộ) trong đồ thị có trọng số.

  ---

  ## PHẦN 1: BIỂU DIỄN BÀI TOÁN & TRẠNG THÁI (Bước 2)

  ### 1.1. Trạng thái (State) — Cấu trúc dữ liệu

  Hệ thống **không dùng** `class State` / mảng 2D như 8-puzzle. Thay vào đó, trạng thái được biểu diễn bằng **Node ID**
  trong đồ thị `networkx.MultiDiGraph` do OSMnx tải về từ OpenStreetMap.

  **Khai báo đồ thị** trong `delivery_robots/core/graph.py:73-118`:

  ```python
  def get_road_graph(
      state,
      nearest_node_id,
      build_route_response,
      traffic_penalty_for_point,
      rain_penalty_for_point,
      obstacle_penalty_for_point,
  ):
      if (
          state["road_graph"] is not None
          and state["projected_road_graph"] is not None
          and state["traffic_routes"] is not None
      ):
          return state["road_graph"], state["projected_road_graph"], state["traffic_routes"]

      with state["graph_lock"]:
          if state["ox"] is None:
              import osmnx as ox
              state["ox"] = ox

          if state["road_graph"] is None:
              state["road_graph"] = _load_or_fetch_graph(state)
              state["projected_road_graph"] = state["ox"].project_graph(state["road_graph"])
              ...
              # Initialize spatial index (BallTree) for fast nearest neighbor lookups
              nodes_data = list(state["road_graph"].nodes(data=True))
              state["spatial_node_ids"] = np.array([node[0] for node in nodes_data])
              coords = np.array(
                  [
                      (np.radians(data["y"]), np.radians(data["x"]))
                      for _, data in nodes_data
                  ]
              )
              state["spatial_tree"] = BallTree(coords, metric="haversine")

  Mỗi node chứa các thuộc tính y (lat), x (lon) — được truy cập trong toàn bộ thuật toán tìm kiếm. Cấu trúc dữ liệu hỗ
  trợ:

  - state["road_graph"] → Đồ thị đường (read-only)
  - state["projected_road_graph"] → Đồ thị chiếu sang hệ tọa độ mét
  - state["spatial_tree"] → BallTree từ sklearn (O(log N) nearest-neighbor lookup)
  - state["obstacles"], state["rain_zones"], state["traffic_routes"] → Danh sách vật cản

  Trạng thái đầy đủ của một robot (State của multi-agent) — static/js/robot/robot.js:2-47:

  class DeliveryRobot {
      constructor(id, lat, lon, name, color, routeAlgorithm = 'astar') {
          this.id = id;
          this.lat = this.lon = ...;          // vị trí hiện tại
          this.battery = CONFIG.ROBOT.INITIAL_BATTERY;  // năng lượng
          this.status = CONFIG.ROBOT.STATUSES.IDLE;     // IDLE / MOVING / CHARGING
          this.currentPath = [];                        // đường đi hiện tại (list node)
          this.pathIndex = 0;                           // tiến độ trên path
          this.currentDelivery = null;                  // đơn hàng đang giao
          this.deliveryQueue = [];                      // hàng chờ cá nhân
          this.routeAlgorithm = 'astar';                // thuật toán đang dùng
          this.roadMemory = {};                         // memory RL-lite
          ...
      }
  }

  1.2. Start State & Goal State

  Start State: Node (giao lộ) gần nhất với tọa độ (fromLat, fromLon) người dùng nhập.
  Goal State: Node gần nhất với tọa độ (toLat, toLon).

  Trích xuất từ delivery_robots/routes/main_routes.py:99-150 (endpoint /api/route):

  @app.route("/api/route")
  def route():
      start_t = time.time()
      try:
          from_lat, from_lon, to_lat, to_lon = parse_route_coordinates()
      except ValueError as exc:
          return jsonify({"error": str(exc)}), 400

      if from_lat == to_lat and from_lon == to_lon:
          return jsonify(
              {"path": [{"lat": from_lat, "lon": from_lon}], "distance": 0}
          )
      ...
      try:
          graph, start_node, end_node = route_graph_context(
              from_lat, from_lon, to_lat, to_lon
          )
          ...
          route_nodes, nodes_explored = run_weighted_route_search(
              graph, start_node, end_node, to_lat, to_lon, weight_fn, algo,
          )

  Hàm route_graph_context (main_routes.py:89-93):

  def route_graph_context(from_lat, from_lon, to_lat, to_lon):
      graph, _, _ = get_road_graph()
      start_node = nearest_node_id(graph, from_lat, from_lon, app_state["ox"])
      end_node = nearest_node_id(graph, to_lat, to_lon, app_state["ox"])
      return graph, start_node, end_node

  Hàm nearest_node_id (utils/route_analysis.py:11-35) — ánh xạ tọa độ thực → node đồ thị:

  def nearest_node_id(graph, lat, lon, state):
      """
      Find the nearest node in the graph to the given coordinates.
      Uses the BallTree from state if available for O(log N) lookup.
      """
      spatial_tree = state.get("spatial_tree")
      spatial_node_ids = state.get("spatial_node_ids")
      ox = state.get("ox")
      if spatial_tree is not None and spatial_node_ids is not None:
          query_coord = np.array([[np.radians(lat), np.radians(lon)]])
          _, indices = spatial_tree.query(query_coord, k=1)
          return spatial_node_ids[indices[0][0]]

      if ox:
          return ox.nearest_nodes(graph, lon, lat)

      nodes = graph.nodes(data=True)
      best_node_id = None
      best_distance = float("inf")
      for node_id, node_data in nodes:
          distance = haversine_distance(lat, lon, node_data["y"], node_data["x"])
          if distance < best_distance:
              best_distance = distance
              best_node_id = node_id
      return best_node_id

  1.3. State Transition — Sinh trạng thái con

  Trên đồ thị đường, không có Up/Down/Left/Right — thay vào đó, các node kề (neighbors) chính là các node được nối trực
  tiếp bởi một cạnh (con đường thực). API graph.neighbors(node) của NetworkX trả về các node kề. "Vật cản" không cấm
  node mà phạt trọng số cạnh.

  Cơ chế sinh trạng thái con trong algorithms/classical.py:80-130 (A*):

  def run_astar(graph, start_node, end_node, goal_lat, goal_lon):
      started = time.time()
      open_set = [(0.0, start_node)]
      came_from = {}
      g_score = {start_node: 0.0}
      closed = set()
      nodes_explored = 0

      while open_set:
          _, current = heapq.heappop(open_set)
          if current in closed:
              continue
          closed.add(current)
          nodes_explored += 1

          if current == end_node:
              path = _reconstruct_path(came_from, current)
              return { ... "found": True ... }

          for neighbor in graph.neighbors(current):   # ← STATE TRANSITION
              if neighbor in closed:
                  continue
              tentative_g = g_score[current] + _edge_length(graph, current, neighbor)
              if tentative_g < g_score.get(neighbor, float("inf")):
                  came_from[neighbor] = current
                  g_score[neighbor] = tentative_g
                  heuristic = haversine_distance(
                      graph.nodes[neighbor]["y"],
                      graph.nodes[neighbor]["x"],
                      goal_lat, goal_lon,
                  )
                  heapq.heappush(open_set, (tentative_g + heuristic, neighbor))

  Hàm _edge_length (classical.py:8-12) — lấy độ dài cạnh (có thể nhân thêm penalty):

  def _edge_length(graph, from_node, to_node):
      edge_data = graph[from_node][to_node]
      if "length" in edge_data:
          return float(edge_data.get("length", 1.0))
      return min(float(d.get("length", 1.0)) for d in edge_data.values())

  Trọng số cạnh động (kết hợp Mưa, Tắc đường, Vật cản) — core/environment.py:173-187:

  def edge_weight_with_traffic(state, from_node, to_node, edge_data):
      from_data = state["road_graph"].nodes[from_node]
      to_data = state["road_graph"].nodes[to_node]
      midpoint_lat = (from_data["y"] + to_data["y"]) / 2
      midpoint_lon = (from_data["x"] + to_data["x"]) / 2

      penalty = traffic_penalty_for_point(state, midpoint_lat, midpoint_lon)
      penalty *= rain_penalty_for_point(state, midpoint_lat, midpoint_lon)
      penalty *= obstacle_penalty_for_point(state, midpoint_lat, midpoint_lon)

      if "length" in edge_data:
          return edge_data.get("length", DEFAULT_EDGE_LENGTH) * penalty

      best_length = min(data.get("length", float("inf")) for data in edge_data.values())
      return best_length * penalty

  → Công thức tổng quát: w(u,v) = length(u,v) × P_traffic × P_rain × P_obstacle

  ▎ Lưu ý quan trọng cho báo cáo: Khác với mê cung grid (4 hướng, tránh tường), đồ thị OSM có hàng nghìn node, mỗi node
  ▎ có thể có 2–5+ hàng xóm, "vật cản" được xử lý bằng hàm phạt chứ không cấm trạng thái.

  ---
  PHẦN 2: CÁC THUẬT TOÁN TÌM KIẾM MÙ (Bước 3)

  2.1. Liệt kê hàm/phương thức

  Có 2 thuật toán mù (Uninformed Search) được cài đặt trong delivery_robots/algorithms/classical.py:

  ┌──────────────┬─────────┬────────────────────────────────────────┐
  │     Hàm      │  Dòng   │               Thuật toán               │
  ├──────────────┼─────────┼────────────────────────────────────────┤
  │ run_dijkstra │ 33-77   │ Dijkstra (UCS trên đồ thị có trọng số) │
  ├──────────────┼─────────┼────────────────────────────────────────┤
  │ run_bfs      │ 190-229 │ BFS (Breadth-First Search)             │
  └──────────────┴─────────┴────────────────────────────────────────┘

  Lưu ý: DFS không được implement vì với đồ thị đường phố thực và metric là khoảng cách, DFS cho ra kết quả tệ & không
  tối ưu.

  Có phiên bản song song trong algorithms/insider.py (run_insider_comparison — dòng 155-405) cho mục đích trình diễn/so
  sánh.

  2.2. Code chính — Main Loop

  Dijkstra (classical.py:33-77) — Dùng Priority Queue (heapq), không có heuristic:

  def run_dijkstra(graph, start_node, end_node):
      started = time.time()
      open_set = [(0.0, start_node)]      # ← Priority Queue (min-heap theo g)
      dist = {start_node: 0.0}            # ← best-known cost
      came_from = {}                      # ← parent pointer để dựng path
      visited = set()                     # ← Closed Set
      nodes_explored = 0

      while open_set:
          current_dist, current = heapq.heappop(open_set)
          if current in visited:
              continue
          visited.add(current)
          nodes_explored += 1

          if current == end_node:
              path = _reconstruct_path(came_from, current)
              return {
                  "found": True, "path": path,
                  "pathLength": len(path), "pathCost": round(current_dist, 2),
                  "nodesExplored": nodes_explored,
                  "timeMs": round((time.time() - started) * 1000, 2),
                  "expectedOptimal": True,   # ← đảm bảo tối ưu
              }

          for neighbor in graph.neighbors(current):
              if neighbor in visited:
                  continue
              next_dist = dist[current] + _edge_length(graph, current, neighbor)
              if next_dist < dist.get(neighbor, float("inf")):
                  dist[neighbor] = next_dist
                  came_from[neighbor] = current
                  heapq.heappush(open_set, (next_dist, neighbor))

  BFS (classical.py:190-229) — Dùng FIFO Queue (deque), mọi cạnh trọng số 1:

  def run_bfs(graph, start_node, end_node):
      started = time.time()
      queue = deque([start_node])         # ← FIFO Queue
      came_from = {start_node: None}
      nodes_explored = 0

      while queue:
          current = queue.popleft()       # ← FIFO pop
          nodes_explored += 1

          if current == end_node:
              path = [current]
              while came_from[current] is not None:
                  current = came_from[current]
                  path.append(current)
              path.reverse()
              return {
                  "found": True, "path": path,
                  "pathLength": len(path), "pathCost": round(_path_cost(graph, path), 2),
                  "nodesExplored": nodes_explored,
                  "timeMs": round((time.time() - started) * 1000, 2),
                  "expectedOptimal": False,   # ← BFS optimal nếu uniform-cost, KHÔNG ở đây
              }

          for neighbor in graph.neighbors(current):
              if neighbor not in came_from:    # ← "Visited" gộp vào came_from
                  came_from[neighbor] = current
                  queue.append(neighbor)

  Phiên bản rút gọn cho A*/Dijkstra/GBFS/BFS unified — algorithms/weighted_search.py:16-83 (dùng cho production route
  API):

  def run_weighted_route_search(
      graph, start_node, end_node, goal_lat, goal_lon,
      weight_fn, algorithm,
  ):
      g_score = {start_node: 0.0}
      came_from = {}
      visited = set()
      nodes_explored = 0

      start_h = haversine_distance(
          graph.nodes[start_node]["y"],
          graph.nodes[start_node]["x"],
          goal_lat, goal_lon,
      )

      # Chọn priority function tùy theo thuật toán
      if algorithm == "dijkstra":
          open_set = [(0.0, start_node)]            # f = g
      elif algorithm == "gbfs":
          open_set = [(start_h, start_node)]         # f = h
      else:  # astar
          open_set = [(start_h, start_node)]         # f = g + h

      while open_set:
          _, current = heapq.heappop(open_set)
          if current in visited: continue

          visited.add(current)
          nodes_explored += 1

          if current == end_node:
              return _reconstruct_node_path(came_from, current), nodes_explored

          for neighbor in graph.neighbors(current):
              if neighbor in visited: continue

              edge_data = graph[current][neighbor]
              tentative_g = g_score[current] + weight_fn(current, neighbor, edge_data)
              if tentative_g >= g_score.get(neighbor, float("inf")): continue

              came_from[neighbor] = current
              g_score[neighbor] = tentative_g

              h_neighbor = haversine_distance(
                  graph.nodes[neighbor]["y"],
                  graph.nodes[neighbor]["x"],
                  goal_lat, goal_lon,
              )

              if algorithm == "dijkstra":
                  priority = tentative_g
              elif algorithm == "gbfs":
                  priority = h_neighbor
              else:
                  priority = tentative_g + h_neighbor

              heapq.heappush(open_set, (priority, neighbor))

      raise nx.NetworkXNoPath

  2.3. Cơ chế hoạt động — Giải thích ngắn gọn

  - Dijkstra duy trì dist[v] = chi phí nhỏ nhất từ start đến v. Mỗi lần pop node có dist nhỏ nhất từ min-heap. Nếu tìm
  được đường đi tốt hơn qua current thì cập nhật dist[neighbor]. Vì trọng số cạnh ≥ 0, khi pop node lần đầu, dist của nó
  đã tối ưu → đảm bảo tối ưu.
  - BFS không quan tâm trọng số, chỉ đếm số cạnh. Tối ưu về số bước chứ không tối ưu về khoảng cách trên đồ thị có trọng
  số, do đó expectedOptimal: False.
  - Cả hai dùng visited/came_from set để tránh lặp node — đây chính là kỹ thuật Closed Set mà giáo trình yêu cầu.

  ---
  PHẦN 3: THUẬT TOÁN A* & CÁC HÀM HEURISTIC (Bước 4)

  3.1. Hàm A* chính

  A* trong classical.py:80-130 (phiên bản cho demo/so sánh "classical"):

  def run_astar(graph, start_node, end_node, goal_lat, goal_lon):
      started = time.time()
      open_set = [(0.0, start_node)]         # ← priority queue theo f
      came_from = {}                          # ← parent
      g_score = {start_node: 0.0}            # ← cost từ start → node
      closed = set()                          # ← Closed Set
      nodes_explored = 0

      while open_set:
          _, current = heapq.heappop(open_set)    # pop f nhỏ nhất
          if current in closed:
              continue
          closed.add(current)
          nodes_explored += 1

          if current == end_node:                 # goal test
              path = _reconstruct_path(came_from, current)
              return { "found": True, "path": path, ... }

          for neighbor in graph.neighbors(current):
              if neighbor in closed:
                  continue
              tentative_g = g_score[current] + _edge_length(graph, current, neighbor)
              if tentative_g < g_score.get(neighbor, float("inf")):
                  came_from[neighbor] = current
                  g_score[neighbor] = tentative_g
                  heuristic = haversine_distance(    # ← h(n)
                      graph.nodes[neighbor]["y"],
                      graph.nodes[neighbor]["x"],
                      goal_lat, goal_lon,
                  )
                  heapq.heappush(open_set, (tentative_g + heuristic, neighbor))   # ← f = g + h

  A* trong insider.py:24-152 (run_astep_demo — phiên bản XAI có ghi lại từng step):

  def run_astep_demo(graph, start_node, end_node, to_lat, to_lon,
                     traffic_penalty_for_point, rain_penalty_for_point,
                     obstacle_penalty_for_point, max_steps=ASTEP_MAX_STEPS):
      start_t = time.time()
      open_set = [(0, start_node)]
      came_from = {}
      g_score = {start_node: 0}
      h_score = {
          start_node: haversine_distance(
              graph.nodes[start_node]["y"], graph.nodes[start_node]["x"], to_lat, to_lon
          )
      }
      f_score = {start_node: h_score[start_node]}
      closed_set = set()
      steps = []
      explored_nodes = []

      step_count = 0
      while open_set and step_count < max_steps:
          step_count += 1
          _, current = heapq.heappop(open_set)

          if current == end_node:
              path = [current]
              while current in came_from:
                  current = came_from[current]
                  path.append(current)
              path.reverse()
              path_coords = [{"lat": graph.nodes[n]["y"], "lon": graph.nodes[n]["x"]} for n in path]
              return {
                  "success": True, "path": path_coords, "pathLength": len(path),
                  "steps": steps, "exploredPath": [...],
                  "totalSteps": step_count, "calcTime": ...,
                  "openSetSize": len(open_set), "closedSetSize": len(closed_set),
              }

          if current in closed_set: continue
          closed_set.add(current)
          explored_nodes.append(current)

          current_lat = graph.nodes[current]["y"]
          current_lon = graph.nodes[current]["x"]
          h_current = haversine_distance(current_lat, current_lon, to_lat, to_lon)
          steps.append({
              "step": step_count,
              "currentNode": json_safe_node_id(current),
              "g": round(g_score.get(current, 0), ...),
              "h": round(h_current, ...),
              "f": round(f_score.get(current, 0), ...),
              "openSetSize": len(open_set), "closedSetSize": len(closed_set),
              "formula": f"f(n) = {g_score.get(current, 0):.0f} + {h_current:.0f} = {f_score.get(current, 0):.0f}",
          })

          for neighbor in graph.neighbors(current):
              if neighbor in closed_set: continue
              edge_data = graph[current][neighbor]
              edge_length = min(d.get("length", ...) for d in edge_data.values())
              mid_lat = (graph.nodes[current]["y"] + graph.nodes[neighbor]["y"]) / 2
              mid_lon = (graph.nodes[current]["x"] + graph.nodes[neighbor]["x"]) / 2
              traffic_pen = traffic_penalty_for_point(mid_lat, mid_lon)
              rain_pen = rain_penalty_for_point(mid_lat, mid_lon)
              obs_pen = obstacle_penalty_for_point(mid_lat, mid_lon)
              total_weight = edge_length * traffic_pen * rain_pen * obs_pen
              tentative_g = g_score[current] + total_weight

              if tentative_g < g_score.get(neighbor, float("inf")):
                  came_from[neighbor] = current
                  g_score[neighbor] = tentative_g
                  h_neighbor = haversine_distance(
                      graph.nodes[neighbor]["y"], graph.nodes[neighbor]["x"],
                      to_lat, to_lon,
                  )
                  h_score[neighbor] = h_neighbor
                  f_score[neighbor] = tentative_g + h_neighbor
                  heapq.heappush(open_set, (f_score[neighbor], neighbor))

  Quy ước công thức đầy đủ A* (xem frontend templates/index.html:336-341):

  f(n) = g(n) + h(n)
  A*     : priority = g(n) + h(n)
  Dijkstra: priority = g(n)
  GBFS   : priority = h(n)
  Heuristic h(n) uses Haversine distance to goal.

  3.2. Danh sách hàm Heuristic

  Dự án chỉ dùng 1 hàm heuristic cho toàn bộ tìm đường:

  ┌────────────────────────────────────────────┬──────────────┬──────┬────────────────────────────────────────┐
  │                    Hàm                     │     File     │ Dòng │             Tên heuristic              │
  ├────────────────────────────────────────────┼──────────────┼──────┼────────────────────────────────────────┤
  │ haversine_distance(lat1, lon1, lat2, lon2) │ utils/geo.py │ 6-17 │ Haversine (khoảng cách đường tròn lớn) │
  └────────────────────────────────────────────┴──────────────┴──────┴────────────────────────────────────────┘

  Ngoài ra còn 2 hàm phụ trợ:
  - point_to_segment_distance_meters(...) (utils/geo.py:26-41) — khoảng cách từ điểm đến đoạn thẳng, dùng cho traffic
  penalty
  - to_local_xy(...) (utils/geo.py:20-23) — chuyển lat/lon sang tọa độ phẳng cục bộ

  3.3. Toàn bộ code Heuristic & Giải thích

  haversine_distance — delivery_robots/utils/geo.py:1-17:

  import math

  from ..config import EARTH_RADIUS_METERS, METERS_PER_DEGREE_LATITUDE


  def haversine_distance(lat1, lon1, lat2, lon2):
      radius = EARTH_RADIUS_METERS
      phi1 = math.radians(lat1)
      phi2 = math.radians(lat2)
      delta_phi = math.radians(lat2 - lat1)
      delta_lambda = math.radians(lon2 - lon1)

      a = (
          math.sin(delta_phi / 2) ** 2
          + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
      )
      return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

  Công thức toán học (Haversine formula):

  a = sin²((φ₂ - φ₁)/2) + cos(φ₁)·cos(φ₂)·sin²((λ₂ - λ₁)/2)
  h(n) = 2 · R · atan2(√a, √(1-a))

  Trong đó:
  - φ = vĩ độ (latitude) tính bằng radian
  - λ = kinh độ (longitude) tính bằng radian
  - R = EARTH_RADIUS_METERS = 6371000 (bán kính Trái Đất, mét) — từ config.py:152

  Ý nghĩa: Đây là khoảng cách cung tròn lớn (great-circle distance) giữa 2 điểm trên mặt cầu. Vì A* yêu cầu heuristic
  admissible (không bao giờ đánh giá cao hơn chi phí thực), Haversine là lựa chọn lý tưởng cho bài toán định tuyến:
  đường thẳng qua không gian luôn ≤ đường đi thực trên mặt đất, đảm bảo tính chất admissible.

  ▎ Tại sao không dùng Manhattan/Euclid? Vì đây là đồ thị đường phố thực trên bề mặt cong Trái Đất. Manhattan/Euclid là
  ▎ heuristic cho lưới 2D phẳng (8-puzzle, maze grid). Trên đồ thị OSM, khoảng cách Haversine chính là cận dưới lý
  ▎ tưởng.

  point_to_segment_distance_meters — utils/geo.py:26-41 (heuristic phụ cho traffic penalty):

  def point_to_segment_distance_meters(lat, lon, start_lat, start_lon, end_lat, end_lon):
      origin_lat = (lat + start_lat + end_lat) / 3
      px, py = to_local_xy(lat, lon, origin_lat)
      ax, ay = to_local_xy(start_lat, start_lon, origin_lat)
      bx, by = to_local_xy(end_lat, end_lon, origin_lat)
      abx = bx - ax
      aby = by - aby
      ab_len_sq = abx * abx + aby * aby

      if ab_len_sq == 0:
          return math.hypot(px - ax, py - ay)

      t = max(0, min(1, ((px - ax) * abx + (py - ay) * aby) / ab_len_sq))
      closest_x = ax + t * abx
      closest_y = ay + t * aby
      return math.hypot(px - closest_x, py - closest_y)

  Công thức: Khoảng cách từ điểm P đến đoạn thẳng AB (chiếu xuống hệ tọa độ phẳng cục bộ gốc origin_lat):

  P' = (px, py),  A' = (ax, ay),  B' = (bx, by)
  AB' = B' - A',  t = clamp(((P'-A')·AB') / |AB'|², 0, 1)
  P*  = A' + t·AB'    (điểm chiếu vuông góc)
  d(P, AB) = |P' - P*|

  Ứng dụng: Tính khoảng cách từ một vị trí lat/lon đến một đoạn đường cụ thể → dùng trong _traffic_penalty_for_routes
  (core/environment.py:67-86) để xác định đoạn đường có bị ảnh hưởng bởi kẹt xe hay không.

  ---
  PHẦN 4: THIẾT KẾ GIAO DIỆN & TƯƠNG TÁC (Bước 5)

  4.1. Công nghệ / Thư viện GUI

  Không dùng Tkinter / Pygame / Swing (vốn là GUI desktop truyền thống). Dự án dùng kiến trúc Web:

  ┌──────────┬─────────────────────────────────────────────────────────────┬──────────────────────────────────┐
  │   Tầng   │                          Công nghệ                          │             Vai trò              │
  ├──────────┼─────────────────────────────────────────────────────────────┼──────────────────────────────────┤
  │ Backend  │ Python 3.10+, Flask 3.0 (app.py, routes/*.py)               │ REST API server, render template │
  ├──────────┼─────────────────────────────────────────────────────────────┼──────────────────────────────────┤
  │ Frontend │ Vanilla JavaScript (ES6 class), Alpine.js, Leaflet.js 1.9.4 │ SPA tương tác bản đồ             │
  ├──────────┼─────────────────────────────────────────────────────────────┼──────────────────────────────────┤
  │ Bản đồ   │ Leaflet + tile OpenStreetMap                                │ Hiển thị map Hoàn Kiếm Hà Nội    │
  ├──────────┼─────────────────────────────────────────────────────────────┼──────────────────────────────────┤
  │ Styling  │ CSS3 (file static/css/style.css, 34KB)                      │ Giao diện dark/light mode        │
  └──────────┴─────────────────────────────────────────────────────────────┴──────────────────────────────────┘

  Dependencies (requirements.txt):

  flask==3.0.0
  osmnx==2.1.0
  networkx==3.6.1
  scikit-learn
  numpy

  4.2. Các thành phần chính trên giao diện

  Trích từ delivery_robots/templates/index.html:

  Layout tổng thể:
  - <div id="map"> — Bản đồ Leaflet toàn màn hình (nền)
  - .search-bar — Thanh trạng thái trên cùng (đồng hồ mô phỏng, badge RUSH HOUR)
  - .fab-container — 7 nút Floating Action Button (góc phải)
  - Các panel trượt từ phải vào

  7 panel chức năng:

  ┌─────────────────────────┬─────────────────┬─────────────────────────────────────────────────────┐
  │          Panel          │       ID        │                      Mục đích                       │
  ├─────────────────────────┼─────────────────┼─────────────────────────────────────────────────────┤
  │ 🎮 Simulation Hub       │ control-panel   │ Start/Pause/Reset, chọn thuật toán, tốc độ mô phỏng │
  ├─────────────────────────┼─────────────────┼─────────────────────────────────────────────────────┤
  │ 🤖 Active Fleet         │ robot-panel     │ Trạng thái đội robot (pin, đơn hàng, vị trí)        │
  ├─────────────────────────┼─────────────────┼─────────────────────────────────────────────────────┤
  │ 🏢 Dispatch Center      │ dispatch-panel  │ Hàng chờ đơn hàng                                   │
  ├─────────────────────────┼─────────────────┼─────────────────────────────────────────────────────┤
  │ 💻 Computing Process    │ computing-panel │ Chi tiết tính toán của 1 robot                      │
  ├─────────────────────────┼─────────────────┼─────────────────────────────────────────────────────┤
  │ 🌦️ Environment Controls │ weather-panel   │ Đặt Mưa / Tắc đường / Vật cản                       │
  ├─────────────────────────┼─────────────────┼─────────────────────────────────────────────────────┤
  │ 📘 Academic Insights    │ decision-panel  │ Metrics realtime (avg time, nodes explored)         │
  ├─────────────────────────┼─────────────────┼─────────────────────────────────────────────────────┤
  │ 🔍 Insider View         │ insider-panel   │ So sánh 4 thuật toán + Step-by-step A*              │
  └─────────────────────────┴─────────────────┴─────────────────────────────────────────────────────┘

  Các "nút bấm" / "bảng lưới" quan trọng (không phải grid puzzle mà là dropdown + slider + map):

  <!-- Chọn thuật toán -->
  <select id="fleet-algo-select" class="algo-select">
      <option value="astar">Advanced A* (Optimized)</option>
      <option value="dijkstra">Dijkstra's Algorithm</option>
      <option value="gbfs">Greedy Best-First Search</option>
  </select>
  <button id="apply-fleet-algo-btn" class="btn-apply">Apply</button>

  <!-- K-means -->
  <button id="optimize-hubs-btn" class="btn-optimize">✨ Re-optimize Hub Locations</button>

  <!-- Insider View: 2 nút chạy demo -->
  <button id="run-comparison-btn" class="btn-comparison">Run Comparison</button>
  <button id="run-astar-viz-btn" class="btn-astar-viz">Run A* Visualization</button>

  <!-- Slider cấu hình -->
  <input type="range" id="speed-slider" min="0.1" max="5" step="0.1" value="1">
  <input type="range" id="rain-radius" min="30" max="300">
  <input type="range" id="obstacle-severity" min="1" max="50">

  Hiển thị "bảng lưới" — không phải grid ô số mà là bảng HTML so sánh thuật toán (render từ insider_panel.js:184-203):

  let html = `
      <table class="comparison-table">
          <thead>
              <tr>
                  <th>${table.ALGORITHM}</th>
                  <th>NODES</th> <th>PATH</th> <th>TIME</th>
                  <th>OPTIMAL</th> <th>EFFICIENCY</th>
              </tr>
          </thead>
          ...
  `;
  rows.forEach(r => {
      html += `<tr class="${isAStar ? 'best-row' : ''}">
          <td>${r.icon} ${r.name}</td>
          <td>${r.nodes_explored}</td>
          <td>${r.path_length} nodes</td>
          <td>${r.time_ms}ms</td>
          <td>${r.optimal ? '✅ Yes' : '❌ No'}</td>
          <td>${eff}</td>
      </tr>`;
  });

  4.3. Event Handling — Xử lý sự kiện

  Không dùng click chuột/bàn phím để đặt vật cản trên grid 2D — thay vào đó, click trực tiếp trên bản đồ Leaflet thật
  (lat/lon) để đặt vật cản, mưa, kẹt xe.

  Thiết lập listener tổng quát — static/js/environment/environment_controls.js:13-53:

  function setupWeather() {
      document.getElementById('randomize-rain-btn')?.addEventListener('click', randomizeRain);
      document.getElementById('clear-rain-btn')?.addEventListener('click', clearRain);
      document.getElementById('reset-traffic-points-btn')?.addEventListener('click', resetTrafficPoints);
      document.getElementById('randomize-traffic-btn')?.addEventListener('click', randomizeTraffic);
      document.getElementById('clear-traffic-btn')?.addEventListener('click', clearTraffic);
      document.getElementById('randomize-obstacle-btn')?.addEventListener('click', randomizeObstacles);
      document.getElementById('clear-obstacle-btn')?.addEventListener('click', clearObstacles);

      const setupMapClick = () => {
          const map = window.map;
          if (map && typeof map.on === 'function') {
              map.on('click', function (e) {
                  const store = Alpine.store('sim');
                  if (!store.panels.weather) return;

                  if (store.weather.mode === CONFIG.UI.WEATHER_MODES.RAIN) {
                      addRainZone(e.latlng.lat, e.latlng.lng, +store.weather.rainRadius);
                  } else if (store.weather.mode === CONFIG.UI.WEATHER_MODES.TRAFFIC) {
                      handleTrafficClick(e.latlng.lat, e.latlng.lng);
                  } else if (store.weather.mode === CONFIG.UI.WEATHER_MODES.OBSTACLE) {
                      addObstacle(
                          e.latlng.lat, e.latlng.lng,
                          +store.weather.obstacleRadius, +store.weather.obstacleSeverity
                      );
                  }
              });
              console.log('Map click listener ready');
          } else {
              console.warn('Map not ready, retrying in 500ms...');
              setTimeout(setupMapClick, 500);
          }
      };
      setTimeout(setupMapClick, 500);

      updateRainList().catch(() => { });
      updateTrafficList().catch(() => { });
      updateObstacleList().catch(() => { });
  }

  Đặt vùng mưa — static/js/environment/rain_controls.js:3-12:

  async function addRainZone(lat, lon, radius) {
      try {
          const d = await postJson(CONFIG.API.RAIN_ADD, { lat, lon, radius },
                                    CONFIG.UI.TEXT.ENVIRONMENT.ERROR_RAIN_ADD);
          updateRainList();
          refreshMapWeather().catch(() => { });
          logEvent('🌧️ ' + d.rainZone.name);
      } catch (error) {
          logEvent('❌ Rain: ' + error.message);
      }
  }

  Đặt vật cản — static/js/environment/obstacle_controls.js:3-18:

  async function addObstacle(lat, lon, radius, severity) {
      try {
          const d = await postJson(CONFIG.API.OBSTACLE_ADD, {
              lat, lon, radius, severity,
              type: CONFIG.SIMULATION.DEFAULT_OBSTACLE_TYPE
          }, CONFIG.UI.TEXT.ENVIRONMENT.ERROR_OBSTACLE_ADD);
          displayObstacle(d.obstacle);
          updateObstacleList();
          logEvent('🚧 ' + d.obstacle.name);
      } catch (error) {
          logEvent('❌ Obstacle: ' + error.message);
      }
  }

  Đặt tuyến kẹt xe (cần 2 click) — static/js/environment/traffic_controls.js:12-33:

  function handleTrafficClick(lat, lon) {
      if (!window.map) return;

      const severity = +document.getElementById('traffic-severity')?.value
                       || CONFIG.SIMULATION.DEFAULT_TRAFFIC_SEVERITY;

      if (!trafficPointA) {                                    // click lần 1
          trafficPointA = { lat, lon };
          if (trafficPointMarkerA) window.map.removeLayer(trafficPointMarkerA);
          trafficPointMarkerA = L.circleMarker([lat, lon], {
              radius: CONFIG.UI.RADII.markerLarge,
              color: CONFIG.ROBOT.COLORS.error,
              fillColor: CONFIG.ROBOT.COLORS.error,
              fillOpacity: 1
          }).addTo(window.map);
          trafficPointMarkerA.bindPopup(CONFIG.UI.TEXT.ENVIRONMENT.TRAFFIC_START_POPUP);
          logEvent(CONFIG.UI.TEXT.ENVIRONMENT.LOG_TRAFFIC_START);
          return;
      }

      const trafficPointB = { lat, lon };                     // click lần 2
      addTrafficRoute(trafficPointA, trafficPointB, severity).finally(() => resetTrafficPoints());
  }

  Chọn thuật toán — static/js/core/app.js:23-27:

  document.getElementById('apply-fleet-algo-btn')?.addEventListener('click', () => {
      const selected = document.getElementById('fleet-algo-select')?.value
                       || CONFIG.SIMULATION.DEFAULT_ALGORITHM;
      simulation?.setFleetAlgorithm(selected);
      Alpine.store('sim').metrics.fleetAlgo = selected.toUpperCase();
  });

  Slide cấu hình (tốc độ mô phỏng) — static/js/core/app.js:29-33:

  const slider = document.getElementById('speed-slider');
  slider?.addEventListener('input', (e) => {
      if (simulation) simulation.speed = +e.target.value;
      Alpine.store('sim').metrics.speed = e.target.value + 'x';
  });

  Khởi tạo tổng thể — static/js/core/app.js:1-16:

  async function init() {
      try {
          simulation = new Simulation();
          window.simulation = simulation;
          await simulation.initialize();
          setupControls();          // gắn listener cho nút
          setupWeather();           // gắn listener cho rain/traffic/obstacle
          setupInsiderControls();   // gắn listener cho Run Comparison / Run A* Viz
          startPolling();           // poll /api/metrics mỗi N ms
          updateClock();
          logEvent(CONFIG.UI.TEXT.LOGS.READY);
      } catch (error) {
          console.error('Init error:', error);
          logEvent('❌ ' + error.message);
      }
  }

  window.addEventListener('load', () => {
      init().catch(e => {
          console.error(e);
          logEvent(CONFIG.UI.TEXT.LOGS.INIT_FAILED);
      });
  });

  Polling metrics realtime — static/js/core/app.js:36-50:

  function startPolling() {
      fetchMetrics();
      setInterval(fetchMetrics, CONFIG.UI.METRICS_REFRESH_INTERVAL_MS);
      setInterval(refreshComputingPanel, CONFIG.UI.COMPUTING_PANEL_REFRESH_INTERVAL_MS);
      setInterval(updateClock, 1000);
  }

  async function fetchMetrics() {
      try {
          const d = await getJson(CONFIG.API.METRICS, null,
                                  CONFIG.UI.TEXT.API_ERRORS.METRICS);
          Alpine.store('sim').updateMetrics(d);
      } catch (e) {
          console.error('Metrics:', e);
      }
  }

  Đặt vị trí bắt đầu/kết thúc cho robot — không phải click chuột mà là hard-coded trong config
  (config.js:CONFIG.DATA.LOCATIONS) rồi "snap to road" qua API /api/snap:

  // Trong simulation.js:initialize()
  this.snappedLocations = await Promise.all(
      CONFIG.DATA.LOCATIONS.map(async location => {
          try {
              const snapped = await pathfindingManager.snapToRoad(location.lat, location.lon);
              return { ...location, lat: snapped.lat, lon: snapped.lon };
          } catch (e) {
              console.warn(`Failed to snap ${location.name}, using original coords`);
              return location;
          }
      })
  );

  API /api/snap (routes/main_routes.py:179-193):

  @app.route("/api/snap")
  def snap():
      try:
          lat = validate_coordinate(request.args.get("lat"), "lat")
          lon = validate_coordinate(request.args.get("lon"), "lon")
          validate_lat_lon(lat, lon)
          graph = get_road_graph()[0]
          node_id = nearest_node_id(graph, lat, lon)
          return jsonify(
              {"lat": graph.nodes[node_id]["y"], "lon": graph.nodes[node_id]["x"]}
          )
      except ValueError as exc:
          return jsonify({"error": str(exc)}), 400
      except Exception as exc:
          return jsonify({"error": str(exc)}), 500

  ---
  TÓM TẮT NHANH CHO BÁO CÁO

  ┌───────────────┬─────────────────────────────────────────────────────────────────────────────────────────────────┐
  │      Mục      │                                     Đặc điểm của dự án này                                      │
  ├───────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ State         │ Node ID trong networkx.MultiDiGraph (đồ thị OSMnx) + các list toàn cục (obstacles, rain_zones,  │
  │               │ traffic_routes)                                                                                 │
  ├───────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Start / Goal  │ Tọa độ lat/lon → nearest_node_id (BallTree) ánh xạ về node gần nhất                             │
  ├───────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Transition    │ graph.neighbors(current) trả các node kề; cạnh có trọng số = length × P_traffic × P_rain ×      │
  │               │ P_obstacle                                                                                      │
  ├───────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Blind search  │ Dijkstra (heapq, dist), BFS (deque, came_from)                                                  │
  ├───────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ A*            │ f = g + h với g = chi phí tích lũy, h = Haversine                                               │
  ├───────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Heuristic     │ haversine_distance (great-circle, admissible). Không dùng Manhattan/Euclid vì là đồ thị cong    │
  ├───────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ GUI           │ Flask + Leaflet + Alpine.js (web, không phải Tkinter/Pygame)                                    │
  ├───────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Event         │ Click trên bản đồ Leaflet (lat/lon) → POST /api/rain/add, /api/obstacle/add, /api/traffic/add   │
  │ handling      │                                                                                                 │
  └───────────────┴─────────────────────────────────────────────────────────────────────────────────────────────────┘

  Chúc bạn hoàn thành báo cáo thật tốt! Nếu cần phân tích thêm phần nào (ví dụ: K-means cho hub optimization, hoặc
  multi-agent dispatching CSP/VRP), cứ hỏi tiếp nhé.