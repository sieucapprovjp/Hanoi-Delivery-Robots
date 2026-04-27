# AI Delivery Robots

Mô phỏng robot giao hàng AI tại Hoan Kiem, Hanoi, dùng cho bài tập AI nhập môn.

## Đã hoàn thành

- Fleet routing với `A*`, `Dijkstra`, `GBFS` cho toàn đội robot.
- So sánh thuật toán bằng runtime, nodes explored, path cost, reroutes và Efficiency Score.
- Tối ưu hub bằng `K-means` từ dữ liệu giao hàng lịch sử.
- Gộp log vào API chung để theo dõi và debug dễ hơn.
- Tinh gọn giao diện, giữ lại các phần quan trọng cho demo.

## Công nghệ

- Backend: Flask, NetworkX, OSMnx
- Frontend: Vanilla JS, Leaflet
- ML: scikit-learn, NumPy

## Cách chạy

```bash
pip install -r requirements.txt
python main.py
```

Mở URL được in ra sau khi chạy, mặc định là `http://127.0.0.1:5001`.

## API chính

- `GET /api/route?fromLat=&fromLon=&toLat=&toLon=&algo=astar|dijkstra|gbfs`
- `GET /api/snap?lat=&lon=`
- `GET /api/metrics`
- `GET /api/classical/compare`
- `POST /api/log_delivery`
- `POST /api/optimize-hubs`
- `POST /api/logs`
- `GET /api/logs?limit=200`

## Cấu trúc chính

```text
delivery_robots/
  app.py
  algorithms/
  core/
  routes/
  utils/
  static/js/
  templates/
main.py
requirements.txt
```
