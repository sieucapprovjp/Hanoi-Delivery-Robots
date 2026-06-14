import json
import tempfile
import unittest
from pathlib import Path

from delivery_robots.utils.persistent_log import (
    append_app_event,
    append_delivery_history,
    append_jsonl,
    read_delivery_history,
    read_jsonl,
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

    def test_read_jsonl_skips_invalid_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_text(
                '{"message": "ok"}\nnot-json\n{"message": "still-ok"}\n',
                encoding="utf-8",
            )

            entries = read_jsonl("events.jsonl", tmp)

        self.assertEqual([entry["message"] for entry in entries], ["ok", "still-ok"])

    def test_read_delivery_history_filters_event_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            append_jsonl("delivery-history.jsonl", {"type": "app_event"}, tmp)
            append_delivery_history({"deliveryId": 42}, tmp)

            entries = read_delivery_history(tmp)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["deliveryId"], 42)


if __name__ == "__main__":
    unittest.main()
