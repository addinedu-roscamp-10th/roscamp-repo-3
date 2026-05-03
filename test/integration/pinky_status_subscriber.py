#!/usr/bin/env python3

from dataclasses import dataclass
import math
from threading import Lock

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

from ropi_interface.msg import PinkyStatus


DEFAULT_STALE_TIMEOUT_SEC = 3.0


@dataclass
class PinkyStatusView:
    pinky_id: str
    pinky_state: str
    active_task_id: str
    charging_state: str
    docked: bool
    battery_percent: float
    battery_voltage: float
    fail_code: str
    frame_id: str
    pose_stamp_sec: int
    pose_stamp_nanosec: int
    x: float
    y: float
    z: float
    qx: float
    qy: float
    qz: float
    qw: float
    theta_deg: float
    measured_at_sec: int
    measured_at_nanosec: int
    received_at_sec: int
    received_at_nanosec: int
    stale: bool


class PinkyStatusSubscriber(Node):
    """Test-side IF-COM-005 subscriber before moving into server."""

    def __init__(self):
        super().__init__("pinky_status_subscriber")

        self.declare_parameter("pinky_id", "pinky2")
        self.declare_parameter("stale_timeout_sec", DEFAULT_STALE_TIMEOUT_SEC)

        pinky_id = str(self.get_parameter("pinky_id").value)
        self._stale_timeout_sec = float(self.get_parameter("stale_timeout_sec").value)
        self._latest_view = None
        self._lock = Lock()

        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=20,
        )
        topic_name = f"/ropi/robots/{pinky_id}/status"
        self.create_subscription(PinkyStatus, topic_name, self._on_status, qos)
        self.create_timer(1.0, self._check_stale)
        self.get_logger().info(f"Subscribed to IF-COM-005 Pinky status topic {topic_name}")

    def _on_status(self, msg: PinkyStatus):
        received_at = self.get_clock().now().to_msg()

        view = PinkyStatusView(
            pinky_id=str(msg.pinky_id),
            pinky_state=str(msg.pinky_state),
            active_task_id=str(msg.active_task_id),
            charging_state=str(msg.charging_state),
            docked=bool(msg.docked),
            battery_percent=float(msg.battery_percent),
            battery_voltage=float(msg.battery_voltage),
            fail_code=str(msg.fail_code),
            frame_id=str(msg.pose.header.frame_id),
            pose_stamp_sec=int(msg.pose.header.stamp.sec),
            pose_stamp_nanosec=int(msg.pose.header.stamp.nanosec),
            x=float(msg.pose.pose.position.x),
            y=float(msg.pose.pose.position.y),
            z=float(msg.pose.pose.position.z),
            qx=float(msg.pose.pose.orientation.x),
            qy=float(msg.pose.pose.orientation.y),
            qz=float(msg.pose.pose.orientation.z),
            qw=float(msg.pose.pose.orientation.w),
            theta_deg=self._yaw_deg(
                float(msg.pose.pose.orientation.z),
                float(msg.pose.pose.orientation.w),
            ),
            measured_at_sec=int(msg.timestamp.sec),
            measured_at_nanosec=int(msg.timestamp.nanosec),
            received_at_sec=int(received_at.sec),
            received_at_nanosec=int(received_at.nanosec),
            stale=False,
        )

        with self._lock:
            self._latest_view = view

        self.get_logger().info(
            "IF-COM-005 status received: "
            f"id={view.pinky_id}, state={view.pinky_state}, "
            f"task={view.active_task_id or '-'}, charging={view.charging_state}, "
            f"docked={view.docked}, fail={view.fail_code or '-'}"
        )

    def _check_stale(self):
        with self._lock:
            view = self._latest_view

        if view is None:
            self.get_logger().warning("No IF-COM-005 Pinky status snapshot received yet")
            return

        now = self.get_clock().now().nanoseconds / 1_000_000_000
        received = view.received_at_sec + (view.received_at_nanosec / 1_000_000_000)
        stale = (now - received) > self._stale_timeout_sec
        if stale and not view.stale:
            view.stale = True
            self.get_logger().warning(
                f"IF-COM-005 status became stale for {view.pinky_id} "
                f"(timeout={self._stale_timeout_sec:.1f}s)"
            )

    @staticmethod
    def _yaw_deg(z: float, w: float) -> float:
        return math.degrees(2.0 * math.atan2(z, w))


def main(args=None):
    rclpy.init(args=args)
    node = PinkyStatusSubscriber()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
