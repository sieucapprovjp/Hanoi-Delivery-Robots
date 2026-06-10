from ...config import (
    DISPATCH_BATTERY_DRAIN_PER_KM,
    DISPATCH_MAX_PICKUP_DISTANCE_METERS,
    DISPATCH_MAX_ROUTE_ETA_MINUTES,
    DISPATCH_MIN_BATTERY_PERCENT,
    DISPATCH_MIN_PROJECTED_BATTERY_PERCENT,
    DISPATCH_REQUIRED_ROBOT_STATUS,
)


def build_constraint_result(checks):
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


def build_constraints_summary():
    return {
        "requiredStatus": DISPATCH_REQUIRED_ROBOT_STATUS,
        "minBatteryPercent": DISPATCH_MIN_BATTERY_PERCENT,
        "minProjectedBatteryPercent": DISPATCH_MIN_PROJECTED_BATTERY_PERCENT,
        "maxRouteEtaMinutes": DISPATCH_MAX_ROUTE_ETA_MINUTES,
        "maxPickupDistanceMeters": DISPATCH_MAX_PICKUP_DISTANCE_METERS,
        "capacityRule": "currentLoad < capacity",
        "batteryReserveRule": "battery - projectedRouteDrain >= minProjectedBatteryPercent",
        "etaRule": "estimatedRouteMinutes <= maxRouteEtaMinutes",
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

    return build_constraint_result(checks)


def calculate_projected_battery(robot, route_cost_meters):
    projected_drain = (route_cost_meters / 1000.0) * DISPATCH_BATTERY_DRAIN_PER_KM
    projected_battery = robot.get("battery", 0) - projected_drain
    return projected_battery, projected_drain


def evaluate_post_route_constraints(robot, route_cost_meters, route_eta_minutes=None):
    projected_battery, projected_drain = calculate_projected_battery(
        robot, route_cost_meters
    )
    checks = {
        "batteryReserveOk": {
            "passed": projected_battery >= DISPATCH_MIN_PROJECTED_BATTERY_PERCENT,
            "code": "battery_reserve_too_low",
            "message": (
                f"Projected battery {projected_battery:.1f}% after route is below "
                f"{DISPATCH_MIN_PROJECTED_BATTERY_PERCENT}% reserve."
            ),
            "details": {
                "battery": robot.get("battery", 0),
                "projectedBattery": projected_battery,
                "projectedDrain": projected_drain,
                "routeCostMeters": route_cost_meters,
                "minProjectedBatteryPercent": DISPATCH_MIN_PROJECTED_BATTERY_PERCENT,
            },
        },
        "routeEtaOk": {
            "passed": (
                route_eta_minutes is None
                or route_eta_minutes <= DISPATCH_MAX_ROUTE_ETA_MINUTES
            ),
            "code": "route_eta_too_high",
            "message": (
                f"Route ETA {route_eta_minutes:.1f}m exceeds "
                f"{DISPATCH_MAX_ROUTE_ETA_MINUTES}m limit."
                if route_eta_minutes is not None
                else "Route ETA is unavailable."
            ),
            "details": {
                "routeEtaMinutes": route_eta_minutes,
                "maxRouteEtaMinutes": DISPATCH_MAX_ROUTE_ETA_MINUTES,
            },
        },
    }

    return build_constraint_result(checks)
