def append_delivery_points(state, pickup_lat, pickup_lon, dropoff_lat, dropoff_lon):
    with state["history_lock"]:
        state["delivery_history"].append([pickup_lat, pickup_lon])
        state["delivery_history"].append([dropoff_lat, dropoff_lon])


def compute_optimized_hubs(state, cluster_count=5):
    import numpy as np
    from sklearn.cluster import KMeans

    with state["history_lock"]:
        if len(state["delivery_history"]) < 5:
            raise ValueError("Not enough delivery data to optimize hubs. Need at least 5 points.")
        data = np.array(state["delivery_history"])

    kmeans = KMeans(n_clusters=cluster_count, n_init="auto", random_state=42)
    kmeans.fit(data)
    hubs = []
    for idx, center in enumerate(kmeans.cluster_centers_):
        hubs.append(
            {
                "id": idx,
                "lat": float(center[0]),
                "lon": float(center[1]),
                "name": f"AI Hub {chr(65 + idx)}",
            }
        )
    return hubs
