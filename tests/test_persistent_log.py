import json
import tempfile
import unittest
from pathlib import Path

from delivery_robots.utils.persistent_log import (
    append_app_event,
    append_delivery_history,
    append_jsonl,
)


class PersistentLogTests(unittest.TestCase):
    def test_append_jsonl_writes_one_json_object_per_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            entry = append_jsonl("events.jsonl", {"message": "hello"}, tmp)
            path = Path(tmp) / "events.jsonl"

            lines = path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(lines), 1)
        parsed = json.loads(lines[0])
        self.assertEqual(parsed["message"], "hello")
        self.assertEqual(parsed["ts"], entry["ts"])

    def test_append_helpers_add_event_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            app_entry = append_app_event({"message": "ready"}, tmp)
            delivery_entry = append_delivery_history({"deliveryId": 12}, tmp)

        self.assertEqual(app_entry["type"], "app_event")
        self.assertEqual(delivery_entry["type"], "delivery_history")
        self.assertEqual(delivery_entry["deliveryId"], 12)


if __name__ == "__main__":
    unittest.main()
