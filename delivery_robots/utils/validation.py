from ..config import (
    LATITUDE_ERROR_MSG,
    LATITUDE_MAX,
    LATITUDE_MIN,
    LONGITUDE_ERROR_MSG,
    LONGITUDE_MAX,
    LONGITUDE_MIN,
)


def validate_coordinate(value, name):
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {name}") from exc


def validate_lat_lon(lat, lon):
    if not LATITUDE_MIN <= lat <= LATITUDE_MAX:
        raise ValueError(LATITUDE_ERROR_MSG)
    if not LONGITUDE_MIN <= lon <= LONGITUDE_MAX:
        raise ValueError(LONGITUDE_ERROR_MSG)


def validate_positive_number(value, name):
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {name}") from exc

    if parsed <= 0:
        raise ValueError(f"{name} must be greater than 0")
    return parsed


def validate_non_negative_int(value, name):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {name}") from exc

    if parsed < 0:
        raise ValueError(f"{name} must be 0 or greater")
    return parsed
