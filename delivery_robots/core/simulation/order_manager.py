"""Standalone OrderManager module.

Handles order lifecycle (PENDING, ASSIGNED, IN_TRANSIT, DELIVERED, EXPIRED),
FIFO queue policy, periodic expiration checking, and failure metrics.
"""

import typing
from typing import Generator

import simpy

from ...config import (
    ORDER_EXPIRY_TIMEOUT,
    ORDER_STATUS_ASSIGNED,
    ORDER_STATUS_DELIVERED,
    ORDER_STATUS_EXPIRED,
    ORDER_STATUS_IN_TRANSIT,
    ORDER_STATUS_PENDING,
)


class OrderManager:
    """Manages the lifecycle, queuing, and expiration of delivery orders.

    Maintains a list of pending orders using FIFO policy and performs
    periodic checks to expire orders that exceed the allowed timeout.
    """

    def __init__(
        self, env: simpy.Environment, app_state: dict, socketio: typing.Any = None
    ) -> None:
        """Initialize the OrderManager.

        Args:
            env (simpy.Environment): The SimPy simulation environment.
            app_state (dict): The global application state dictionary.
            socketio (typing.Any, optional): SocketIO server instance for broadcasting.
        """
        self.env: simpy.Environment = env
        self.app_state: dict = app_state
        self.socketio: typing.Any = socketio

        self.order_queue: list[dict] = []
        self.app_state["order_queue"] = self.order_queue
        self.app_state["order_manager"] = self

        # Ensure failedOrders is initialized in metrics
        if "metrics" in self.app_state:
            if "failedOrders" not in self.app_state["metrics"]:
                self.app_state["metrics"]["failedOrders"] = 0

        # Start periodic expiration check process
        self.process: simpy.Process = self.env.process(self.run())

    def add_order(self, task: dict) -> None:
        """Add a new order to the queue.

        Sets the created time and moves its status to PENDING.

        Args:
            task (dict): The order information dictionary.
        """
        task["created_time"] = self.env.now
        task["status"] = ORDER_STATUS_PENDING
        task["reassign_count"] = 0
        task["last_reassign_time"] = None
        self.order_queue.append(task)

    def pop_next_pending(self) -> dict | None:
        """Retrieve the next PENDING order from the queue (FIFO policy).

        Returns:
            dict | None: The next pending order task dictionary, or None if empty.
        """
        for i, task in enumerate(self.order_queue):
            if task.get("status") == ORDER_STATUS_PENDING:
                self.order_queue.pop(i)
                task["status"] = ORDER_STATUS_ASSIGNED
                return task
        return None

    def requeue_order(self, task: dict) -> None:
        """Re-queue an assigned order back to the pending queue.

        This typically happens when routing fails or robot aborts due to low battery.
        Task is placed at the front of the queue to prioritize it.

        Args:
            task (dict): The order information dictionary.
        """
        task["status"] = ORDER_STATUS_PENDING
        self.order_queue.insert(0, task)

    def mark_assigned(self, task: dict) -> None:
        """Transition order status to ASSIGNED.

        Args:
            task (dict): The order information dictionary.
        """
        task["status"] = ORDER_STATUS_ASSIGNED

    def mark_in_transit(self, task: dict) -> None:
        """Transition order status to IN_TRANSIT.

        Args:
            task (dict): The order information dictionary.
        """
        task["status"] = ORDER_STATUS_IN_TRANSIT

    def mark_delivered(self, task: dict) -> None:
        """Transition order status to DELIVERED.

        Args:
            task (dict): The order information dictionary.
        """
        task["status"] = ORDER_STATUS_DELIVERED

    def check_expired_orders(self) -> None:
        """Scan the queue and mark pending orders as EXPIRED if timeout is exceeded."""
        now: float = self.env.now
        for task in list(self.order_queue):
            if task.get("status") == ORDER_STATUS_PENDING:
                created_time: float | None = task.get("created_time")
                if (
                    created_time is not None
                    and (now - created_time) > ORDER_EXPIRY_TIMEOUT
                ):
                    task["status"] = ORDER_STATUS_EXPIRED
                    self.order_queue.remove(task)

                    # Update failure metrics
                    if "metrics" in self.app_state:
                        self.app_state["metrics"]["failedOrders"] = (
                            self.app_state["metrics"].get("failedOrders", 0) + 1
                        )

                    # Emit system event via socketio if available
                    if self.socketio:
                        msg = (
                            f"Order {task['id']} has expired after "
                            f"{ORDER_EXPIRY_TIMEOUT}s"
                        )
                        self.socketio.emit("system_event", {"message": msg})

    def run(self) -> Generator[simpy.Event, None, None]:
        """Periodic simulation process checking for expired orders.

        Yields:
            simpy.Event: A timeout event for SimPy scheduler.
        """
        while True:
            yield self.env.timeout(10)  # Check every 10 simulation seconds
            self.check_expired_orders()
