#!/usr/bin/env python3

from dataclasses import dataclass
import json
from threading import Lock

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String


@dataclass
class JetcobotStatusCommView:
    arm_id: str
    station_role: str
    arm_state: str
    active_task_id: str
    active_transfer_direction: str
    active_item_id: str
    active_robot_slot_id: str
    fault_code: str
    measured_at_sec: int
    measured_at_nanosec: int
    received_at_sec: int
    received_at_nanosec: int
    stale: bool


class JetcobotStatusCommSubscriber(Node):
    """Simple communication-test subscriber for Jetcobot JSON status."""

    def __init__(self):
        super().__init__("jetcobot_status_comm_subscriber")

        self.declare_parameter("arm_id", "arm1")
        self.declare_parameter("stale_timeout_sec", 3.0)

        arm_id = str(self.get_parameter("arm_id").value)
        self._stale_timeout_sec = float(self.get_parameter("stale_timeout_sec").value)
        self._latest_view = None
        self._lock = Lock()

        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=20,
        )
        topic_name = f"/ropi/arms/{arm_id}/status_json"
        self.create_subscription(String, topic_name, self._on_status, qos)
        self.create_timer(1.0, self._check_stale)
        self.get_logger().info(f"Subscribed to Jetcobot JSON topic {topic_name}")

    def _on_status(self, msg: String):
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError as exc:
            self.get_logger().warning(f"Invalid Jetcobot status JSON: {exc}")
            return

        timestamp = payload.get("timestamp", {})
        received_at = self.get_clock().now().to_msg()

        view = JetcobotStatusCommView(
            arm_id=str(payload.get("arm_id", "")),
            station_role=str(payload.get("station_role", "")),
            arm_state=str(payload.get("arm_state", "")),
            active_task_id=str(payload.get("active_task_id", "")),
            active_transfer_direction=str(payload.get("active_transfer_direction", "")),
            active_item_id=str(payload.get("active_item_id", "")),
            active_robot_slot_id=str(payload.get("active_robot_slot_id", "")),
            fault_code=str(payload.get("fault_code", "")),
            measured_at_sec=int(timestamp.get("sec", 0)),
            measured_at_nanosec=int(timestamp.get("nanosec", 0)),
            received_at_sec=int(received_at.sec),
            received_at_nanosec=int(received_at.nanosec),
            stale=False,
        )

        with self._lock:
            self._latest_view = view

        self.get_logger().info(f"Jetcobot JSON received: {msg.data}")

    def _check_stale(self):
        with self._lock:
            view = self._latest_view

        if view is None:
            self.get_logger().warning("No Jetcobot JSON snapshot received yet")
            return

        now = self.get_clock().now().nanoseconds / 1_000_000_000
        received = view.received_at_sec + (view.received_at_nanosec / 1_000_000_000)
        stale = (now - received) > self._stale_timeout_sec
        if stale and not view.stale:
            view.stale = True
            self.get_logger().warning(
                f"Jetcobot JSON became stale for {view.arm_id} "
                f"(timeout={self._stale_timeout_sec:.1f}s)"
            )


def main(args=None):
    rclpy.init(args=args)
    node = JetcobotStatusCommSubscriber()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
