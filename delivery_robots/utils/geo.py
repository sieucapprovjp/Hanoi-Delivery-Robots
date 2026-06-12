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


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates the geographic bearing from point 1 to point 2 in degrees.

    North is 0 degrees, measured clockwise.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)

    y = math.sin(delta_lon) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(
        delta_lon
    )

    bearing_rad = math.atan2(y, x)
    return (math.degrees(bearing_rad) + 360.0) % 360.0
