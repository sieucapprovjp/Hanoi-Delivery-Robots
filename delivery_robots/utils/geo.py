import math
import osmnx as ox


from ..config import EARTH_RADIUS_METERS, METERS_PER_DEGREE_LATITUDE


def haversine_distance(lat1, lon1, lat2, lon2):
    return ox.distance.great_circle(
        lat1, lon1, lat2, lon2, earth_radius=EARTH_RADIUS_METERS
    )


def to_local_xy(lat, lon, origin_lat):
    meters_per_deg_lat = METERS_PER_DEGREE_LATITUDE
    meters_per_deg_lon = METERS_PER_DEGREE_LATITUDE * math.cos(math.radians(origin_lat))
    return lon * meters_per_deg_lon, lat * meters_per_deg_lat


def point_to_segment_distance_meters(lat, lon, start_lat, start_lon, end_lat, end_lon):
    origin_lat = (lat + start_lat + end_lat) / 3
    px, py = to_local_xy(lat, lon, origin_lat)
    ax, ay = to_local_xy(start_lat, start_lon, origin_lat)
    bx, by = to_local_xy(end_lat, end_lon, origin_lat)
    abx = bx - ax
    aby = by - ay
    ab_len_sq = abx * abx + aby * aby

    if ab_len_sq == 0:
        return math.hypot(px - ax, py - ay)

    t = max(0, min(1, ((px - ax) * abx + (py - ay) * aby) / ab_len_sq))
    closest_x = ax + t * abx
    closest_y = ay + t * aby
    return math.hypot(px - closest_x, py - closest_y)
