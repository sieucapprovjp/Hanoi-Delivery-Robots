import unittest

from delivery_robots.algorithms.dispatch.constraints import (
    build_constraints_summary,
    evaluate_pre_route_constraints,
)
from delivery_robots.config import (
    DISPATCH_MAX_PICKUP_DISTANCE_METERS,
    DISPATCH_MIN_BATTERY_PERCENT,
    DISPATCH_REQUIRED_ROBOT_STATUS,
)


class DispatchConstraintTests(unittest.TestCase):
    def test_build_constraints_summary_uses_config_values(self):
        summary = build_constraints_summary()

        self.assertEqual(summary["requiredStatus"], DISPATCH_REQUIRED_ROBOT_STATUS)
        self.assertEqual(summary["minBatteryPercent"], DISPATCH_MIN_BATTERY_PERCENT)
        self.assertEqual(
            summary["maxPickupDistanceMeters"],
            DISPATCH_MAX_PICKUP_DISTANCE_METERS,
        )

    def test_evaluate_pre_route_constraints_accepts_feasible_robot(self):
        result = evaluate_pre_route_constraints(
            {
                "status": "idle",
                "battery": DISPATCH_MIN_BATTERY_PERCENT,
                "currentLoad": 0,
                "capacity": 1,
            },
            DISPATCH_MAX_PICKUP_DISTANCE_METERS,
        )

        self.assertTrue(result["passed"])
        self.assertEqual(result["rejections"], [])
        self.assertTrue(result["checks"]["idle"]["passed"])
        self.assertTrue(result["checks"]["batteryOk"]["passed"])
        self.assertTrue(result["checks"]["capacityOk"]["passed"])
        self.assertTrue(result["checks"]["pickupDistanceOk"]["passed"])

    def test_evaluate_pre_route_constraints_returns_all_rejections(self):
        result = evaluate_pre_route_constraints(
            {
                "status": "moving",
                "battery": DISPATCH_MIN_BATTERY_PERCENT - 1,
                "currentLoad": 2,
                "capacity": 2,
            },
            DISPATCH_MAX_PICKUP_DISTANCE_METERS + 1,
        )

        self.assertFalse(result["passed"])
        self.assertEqual(
            [item["code"] for item in result["rejections"]],
            ["not_idle", "low_battery", "capacity_full", "pickup_too_far"],
        )
        self.assertFalse(result["checks"]["idle"]["passed"])
        self.assertFalse(result["checks"]["batteryOk"]["passed"])
        self.assertFalse(result["checks"]["capacityOk"]["passed"])
        self.assertFalse(result["checks"]["pickupDistanceOk"]["passed"])
        self.assertIn("details", result["rejections"][0])


if __name__ == "__main__":
    unittest.main()
