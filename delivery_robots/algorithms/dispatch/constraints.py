from ...config import (
    DISPATCH_MAX_PICKUP_DISTANCE_METERS,
    DISPATCH_MIN_BATTERY_PERCENT,
    DISPATCH_REQUIRED_ROBOT_STATUS,
)


def build_constraints_summary():
    return {
        "requiredStatus": DISPATCH_REQUIRED_ROBOT_STATUS,
        "minBatteryPercent": DISPATCH_MIN_BATTERY_PERCENT,
        "maxPickupDistanceMeters": DISPATCH_MAX_PICKUP_DISTANCE_METERS,
        "capacityRule": "currentLoad < capacity",
    }


def evaluate_pre_route_constraints(robot, pickup_distance_meters):
    status = robot.get("status")
    capacity = robot.get("capacity")
    current_load = robot.get("currentLoad", 0)
    battery = robot.get("battery", 0)

    checks = {
        "idle": {
            "passed": status is None or status == DISPATCH_REQUIRED_ROBOT_STATUS,
            "code": "not_idle",
            "message": f"Robot status is {status}; expected idle.",
            "details": {
                "actualStatus": status,
                "requiredStatus": DISPATCH_REQUIRED_ROBOT_STATUS,
            },
        },
        "batteryOk": {
            "passed": battery >= DISPATCH_MIN_BATTERY_PERCENT,
            "code": "low_battery",
            "message": (
                f"Battery {battery:.1f}% is below "
                f"{DISPATCH_MIN_BATTERY_PERCENT}% minimum."
            ),
            "details": {
                "battery": battery,
                "minBatteryPercent": DISPATCH_MIN_BATTERY_PERCENT,
            },
        },
        "capacityOk": {
            "passed": capacity is None or current_load < capacity,
            "code": "capacity_full",
            "message": f"Load {current_load}/{capacity} leaves no free capacity.",
            "details": {
                "currentLoad": current_load,
                "capacity": capacity,
            },
        },
        "pickupDistanceOk": {
            "passed": pickup_distance_meters <= DISPATCH_MAX_PICKUP_DISTANCE_METERS,
            "code": "pickup_too_far",
            "message": (
                f"Pickup distance {pickup_distance_meters:.0f}m exceeds "
                f"{DISPATCH_MAX_PICKUP_DISTANCE_METERS}m limit."
            ),
            "details": {
                "pickupDistanceMeters": pickup_distance_meters,
                "maxPickupDistanceMeters": DISPATCH_MAX_PICKUP_DISTANCE_METERS,
            },
        },
    }

    return {
        "passed": all(check["passed"] for check in checks.values()),
        "checks": checks,
        "rejections": [
            {
                "code": check["code"],
                "message": check["message"],
                "details": check["details"],
            }
            for check in checks.values()
            if not check["passed"]
        ],
    }
