"""Lightweight Event Bus for environment-driven simulation events.

Implements publish/subscribe pattern to decouple environment mutations
(rain, traffic, obstacles) from Simulation Core. Supports event
recording for deterministic scenario replay in benchmarks.

Architecture reference: coding_requirement.md — Nguyên lý 4.
"""

import threading
import time
from collections import defaultdict
from enum import Enum, auto


class EventType(Enum):
    """Typed event categories for the simulation environment."""

    # Rain zone mutations
    RAIN_ADDED = auto()
    RAIN_CLEARED = auto()
    RAIN_RANDOMIZED = auto()

    # Traffic route mutations
    TRAFFIC_ADDED = auto()
    TRAFFIC_CLEARED = auto()
    TRAFFIC_RANDOMIZED = auto()

    # Obstacle mutations
    OBSTACLE_ADDED = auto()
    OBSTACLE_CLEARED = auto()
    OBSTACLE_RANDOMIZED = auto()

    # Simulation lifecycle
    SIM_STARTED = auto()
    SIM_PAUSED = auto()
    SIM_RESET = auto()
    SIM_TICK = auto()


class Event:
    """Immutable event payload.

    Attributes:
        event_type: Category of event.
        data: Arbitrary payload dict (event-specific).
        timestamp: Wall-clock time when event was created.
        sim_time: Simulation time (env.now) when event was created.
    """

    __slots__ = ("event_type", "data", "timestamp", "sim_time")

    def __init__(self, event_type, data=None, sim_time=0.0):
        self.event_type = event_type
        self.data = data or {}
        self.timestamp = time.time()
        self.sim_time = sim_time

    def to_dict(self):
        """Serialize for scenario replay file."""
        return {
            "type": self.event_type.name,
            "data": self.data,
            "timestamp": self.timestamp,
            "sim_time": self.sim_time,
        }

    @classmethod
    def from_dict(cls, d):
        """Deserialize from scenario replay file."""
        event = cls(
            event_type=EventType[d["type"]],
            data=d.get("data", {}),
            sim_time=d.get("sim_time", 0.0),
        )
        event.timestamp = d.get("timestamp", time.time())
        return event


class EventBus:
    """Thread-safe publish/subscribe event bus.

    Usage:
        bus = EventBus()

        # Subscribe
        bus.subscribe(EventType.RAIN_ADDED, handler_fn)
        bus.subscribe_all(global_logger_fn)

        # Publish
        bus.publish(Event(EventType.RAIN_ADDED, {"center": (21.03, 105.85)}))

        # Replay recorded events
        for event_dict in scenario_file:
            bus.replay(Event.from_dict(event_dict))
    """

    def __init__(self, recording=False):
        self._subscribers = defaultdict(list)
        self._global_subscribers = []
        self._lock = threading.Lock()
        self._recording = recording
        self._recorded_events = []

    def subscribe(self, event_type, handler):
        """Register handler for a specific event type.

        Args:
            event_type: EventType enum value.
            handler: Callable(event: Event) -> None.
        """
        with self._lock:
            self._subscribers[event_type].append(handler)

    def subscribe_all(self, handler):
        """Register handler that receives ALL events (for logging/replay)."""
        with self._lock:
            self._global_subscribers.append(handler)

    def unsubscribe(self, event_type, handler):
        """Remove a handler from a specific event type."""
        with self._lock:
            handlers = self._subscribers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)

    def publish(self, event):
        """Dispatch event to all matching subscribers.

        Thread-safe: subscribers list is copied before dispatch
        to avoid holding the lock during handler execution.
        """
        with self._lock:
            typed_handlers = list(self._subscribers.get(event.event_type, []))
            global_handlers = list(self._global_subscribers)
            if self._recording:
                self._recorded_events.append(event.to_dict())

        for handler in typed_handlers:
            handler(event)
        for handler in global_handlers:
            handler(event)

    def replay(self, event):
        """Re-dispatch a previously recorded event.

        Same as publish but skips recording to avoid infinite loops.
        """
        with self._lock:
            typed_handlers = list(self._subscribers.get(event.event_type, []))
            global_handlers = list(self._global_subscribers)

        for handler in typed_handlers:
            handler(event)
        for handler in global_handlers:
            handler(event)

    # --- Recording API for scenario replay ---

    @property
    def is_recording(self):
        return self._recording

    def start_recording(self):
        """Begin recording events for scenario replay."""
        with self._lock:
            self._recording = True
            self._recorded_events.clear()

    def stop_recording(self):
        """Stop recording and return recorded events."""
        with self._lock:
            self._recording = False
            events = list(self._recorded_events)
            self._recorded_events.clear()
            return events

    def get_recorded_events(self):
        """Get a copy of recorded events without stopping."""
        with self._lock:
            return list(self._recorded_events)

    def clear(self):
        """Remove all subscribers and recorded events."""
        with self._lock:
            self._subscribers.clear()
            self._global_subscribers.clear()
            self._recorded_events.clear()
            self._recording = False
