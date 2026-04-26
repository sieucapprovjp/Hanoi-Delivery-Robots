def validate_coordinate(value, name):
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {name}") from exc


def validate_lat_lon(lat, lon):
    if not -90 <= lat <= 90:
        raise ValueError("Latitude must be between -90 and 90")
    if not -180 <= lon <= 180:
        raise ValueError("Longitude must be between -180 and 180")


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
