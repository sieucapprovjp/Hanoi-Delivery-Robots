from ..config import (
    DEFAULT_HUB_CLUSTER_COUNT,
    HUB_NAME_ASCII_OFFSET,
    HUB_NAME_PREFIX,
    KMEANS_N_INIT,
    KMEANS_RANDOM_STATE,
    MIN_DELIVERY_HISTORY_ERROR_MSG,
    MIN_DELIVERY_HISTORY_POINTS,
)
from ..utils.persistent_log import read_delivery_history


def append_delivery_points(state, pickup_lat, pickup_lon, dropoff_lat, dropoff_lon):
    with state["history_lock"]:
        state["delivery_history"].append([pickup_lat, pickup_lon])
        state["delivery_history"].append([dropoff_lat, dropoff_lon])


def _coordinate_pair(payload):
    try:
        return [float(payload["lat"]), float(payload["lon"])]
    except (TypeError, KeyError, ValueError):
        return None


def delivery_history_points_from_log(log_dir=None):
    points = []
    entries = read_delivery_history(log_dir=log_dir) if log_dir else read_delivery_history()
    for entry in entries:
        pickup = _coordinate_pair(entry.get("pickup"))
        dropoff = _coordinate_pair(entry.get("dropoff"))
        if pickup:
            points.append(pickup)
        if dropoff:
            points.append(dropoff)
    return points


def _in_memory_delivery_points(state):
    with state["history_lock"]:
        return [list(point) for point in state["delivery_history"]]


def load_delivery_points_for_kmeans(state, log_dir=None):
    log_points = delivery_history_points_from_log(log_dir=log_dir)
    if len(log_points) >= MIN_DELIVERY_HISTORY_POINTS:
        return log_points, "log"

    memory_points = _in_memory_delivery_points(state)
    if len(memory_points) >= MIN_DELIVERY_HISTORY_POINTS:
        return memory_points, "memory"

    return log_points or memory_points, "insufficient"


def compute_optimized_hubs(state, cluster_count=DEFAULT_HUB_CLUSTER_COUNT, log_dir=None):
    import numpy as np
    from sklearn.cluster import KMeans

    points, _source = load_delivery_points_for_kmeans(state, log_dir=log_dir)
    if len(points) < MIN_DELIVERY_HISTORY_POINTS:
        raise ValueError(MIN_DELIVERY_HISTORY_ERROR_MSG)

    data = np.array(points)

    kmeans = KMeans(
        n_clusters=cluster_count,
        n_init=KMEANS_N_INIT,
        random_state=KMEANS_RANDOM_STATE,
    )
    kmeans.fit(data)
    hubs = []
    for idx, center in enumerate(kmeans.cluster_centers_):
        hubs.append(
            {
                "id": idx,
                "lat": float(center[0]),
                "lon": float(center[1]),
                "name": f"{HUB_NAME_PREFIX}{chr(HUB_NAME_ASCII_OFFSET + idx)}",
            }
        )
    return hubs


def snap_hubs_to_graph(hubs, graph, nearest_node_id_fn, ox=None):
    snapped_hubs = []
    for hub in hubs:
        node_id = nearest_node_id_fn(graph, hub["lat"], hub["lon"], ox)
        node = graph.nodes[node_id]
        snapped = dict(hub)
        snapped["centroidLat"] = hub["lat"]
        snapped["centroidLon"] = hub["lon"]
        snapped["lat"] = float(node["y"])
        snapped["lon"] = float(node["x"])
        snapped["snappedToRoad"] = True
        snapped["roadNodeId"] = str(node_id)
        snapped_hubs.append(snapped)
    return snapped_hubs
