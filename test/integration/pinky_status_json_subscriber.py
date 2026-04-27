#!/usr/bin/env python3

from dataclasses import dataclass
import json
import math
from threading import Lock

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String


@dataclass
class PinkyStatusJsonView:
    pinky_id: str
    pinky_state: str
    active_task_id: str
    charging_state: str
    docked: bool
    battery_percent: float
    battery_voltage: float
    fault_code: str
    frame_id: str
    x: float
    y: float
    theta_deg: float
    measured_at_sec: int
    measured_at_nanosec: int
    received_at_sec: int
    received_at_nanosec: int
    stale: bool


class PinkyStatusJsonSubscriber(Node):
    """
    Copy-paste friendly server-side subscriber for the JSON String topic.
    """

    def __init__(self):
        super().__init__("pinky_status_json_subscriber")

        self.declare_parameter("pinky_id", "pinky_01")
        self.declare_parameter("stale_timeout_sec", 3.0)

        pinky_id = self.get_parameter("pinky_id").value
        self._stale_timeout_sec = float(self.get_parameter("stale_timeout_sec").value)
        self._latest_view = None
        self._lock = Lock()

        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=20,
        )
        topic_name = f"/ropi/robots/{pinky_id}/status_json"
        self.create_subscription(String, topic_name, self._on_status, qos)
        self.create_timer(1.0, self._check_stale)
        self.get_logger().info(f"Subscribed to copy-paste IF-COM-005 JSON topic {topic_name}")

    def _on_status(self, msg: String):
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError as exc:
            self.get_logger().warning(f"Invalid Pinky status JSON: {exc}")
            return

        pose = payload.get("pose", {})
        pose_header = pose.get("header", {})
        pose_pose = pose.get("pose", {})
        position = pose_pose.get("position", {})
        orientation = pose_pose.get("orientation", {})
        timestamp = payload.get("timestamp", {})
        received_at = self.get_clock().now().to_msg()

        view = PinkyStatusJsonView(
            pinky_id=str(payload.get("pinky_id", "")),
            pinky_state=str(payload.get("pinky_state", "")),
            active_task_id=str(payload.get("active_task_id", "")),
            charging_state=str(payload.get("charging_state", "")),
            docked=bool(payload.get("docked", False)),
            battery_percent=float(payload.get("battery_percent", 0.0)),
            battery_voltage=float(payload.get("battery_voltage", 0.0)),
            fault_code=str(payload.get("fault_code", "")),
            frame_id=str(pose_header.get("frame_id", "")),
            x=float(position.get("x", 0.0)),
            y=float(position.get("y", 0.0)),
            theta_deg=self._yaw_deg(
                float(orientation.get("z", 0.0)),
                float(orientation.get("w", 1.0)),
            ),
            measured_at_sec=int(timestamp.get("sec", 0)),
            measured_at_nanosec=int(timestamp.get("nanosec", 0)),
            received_at_sec=int(received_at.sec),
            received_at_nanosec=int(received_at.nanosec),
            stale=False,
        )

        with self._lock:
            self._latest_view = view

        self.get_logger().info(f"IF-COM-005 JSON received: {msg.data}")

    def _check_stale(self):
        with self._lock:
            view = self._latest_view

        if view is None:
            self.get_logger().warning("No IF-COM-005 JSON snapshot received yet")
            return

        now = self.get_clock().now().nanoseconds / 1_000_000_000
        received = view.received_at_sec + (view.received_at_nanosec / 1_000_000_000)
        stale = (now - received) > self._stale_timeout_sec
        if stale and not view.stale:
            view.stale = True
            self.get_logger().warning(
                f"IF-COM-005 JSON became stale for {view.pinky_id} "
                f"(timeout={self._stale_timeout_sec:.1f}s)"
            )

    @staticmethod
    def _yaw_deg(z: float, w: float) -> float:
        return math.degrees(2.0 * math.atan2(z, w))


def main(args=None):
    rclpy.init(args=args)
    node = PinkyStatusJsonSubscriber()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
