import unittest

from delivery_robots.core.environment import traffic_penalty_for_snapshot


class EnvironmentTests(unittest.TestCase):
    def test_traffic_penalty_snapshot_uses_snapshot_period(self):
        snapshot = {
            "traffic_routes": [
                {
                    "name": "Test Traffic",
                    "severity": 0.5,
                    "path": [
                        {"lat": 21.0, "lon": 105.0},
                        {"lat": 21.0, "lon": 105.001},
                    ],
                }
            ],
            "rush_multiplier": 1.0,
            "now": 0.0,
            "traffic_period_seconds": 36,
        }

        penalty = traffic_penalty_for_snapshot(snapshot, 21.0, 105.0005)

        self.assertGreater(penalty, 1.0)


if __name__ == "__main__":
    unittest.main()
