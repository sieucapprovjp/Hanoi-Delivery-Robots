import unittest

from delivery_robots.utils.validation import (
    validate_coordinate,
    validate_lat_lon,
    validate_non_negative_int,
    validate_positive_number,
)


class ValidationTests(unittest.TestCase):
    def test_validate_coordinate_accepts_numeric_string(self):
        self.assertEqual(validate_coordinate("21.5", "lat"), 21.5)

    def test_validate_lat_lon_rejects_invalid_latitude(self):
        with self.assertRaises(ValueError):
            validate_lat_lon(120, 105)

    def test_validate_positive_number_rejects_zero(self):
        with self.assertRaises(ValueError):
            validate_positive_number(0, "radius")

    def test_validate_non_negative_int_accepts_zero(self):
        self.assertEqual(validate_non_negative_int(0, "count"), 0)


if __name__ == "__main__":
    unittest.main()
