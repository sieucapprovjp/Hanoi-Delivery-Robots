from ..config import (
    DEFAULT_HUB_CLUSTER_COUNT,
    HUB_NAME_ASCII_OFFSET,
    HUB_NAME_PREFIX,
    KMEANS_N_INIT,
    KMEANS_RANDOM_STATE,
    MIN_DELIVERY_HISTORY_ERROR_MSG,
    MIN_DELIVERY_HISTORY_POINTS,
)


def compute_optimized_hubs(state, cluster_count=DEFAULT_HUB_CLUSTER_COUNT):
    import numpy as np
    from sklearn.cluster import KMeans

    with state["history_lock"]:
        if len(state["delivery_history"]) < MIN_DELIVERY_HISTORY_POINTS:
            raise ValueError(MIN_DELIVERY_HISTORY_ERROR_MSG)
        data = np.array(state["delivery_history"])

    kmeans = KMeans(n_clusters=cluster_count, n_init=KMEANS_N_INIT, random_state=KMEANS_RANDOM_STATE)
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
