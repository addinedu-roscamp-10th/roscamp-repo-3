#!/usr/bin/env python3

from dataclasses import dataclass
from threading import Lock

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

from ropi_arm_status_test.msg import ArmStatus


DEFAULT_STALE_TIMEOUT_SEC = 3.0


@dataclass
class ArmStatusView:
    arm_id: str
    station_role: str
    arm_state: str
    active_task_id: str
    active_transfer_direction: str
    active_item_id: str
    active_robot_slot_id: str
    fail_code: str
    measured_at_sec: int
    measured_at_nanosec: int
    received_at_sec: int
    received_at_nanosec: int
    stale: bool


class JetcobotStatusSubscriber(Node):
    """Test-side IF-DEL-004 subscriber before moving into server."""

    def __init__(self):
        super().__init__("jetcobot_status_subscriber")

        self.declare_parameter("arm_id", "arm1")
        self.declare_parameter("stale_timeout_sec", DEFAULT_STALE_TIMEOUT_SEC)

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
        topic_name = f"/ropi/arms/{arm_id}/status"
        self.create_subscription(ArmStatus, topic_name, self._on_status, qos)
        self.create_timer(1.0, self._check_stale)
        self.get_logger().info(f"Subscribed to IF-DEL-004 Jetcobot status topic {topic_name}")

    def _on_status(self, msg: ArmStatus):
        received_at = self.get_clock().now().to_msg()

        view = ArmStatusView(
            arm_id=str(msg.arm_id),
            station_role=str(msg.station_role),
            arm_state=str(msg.arm_state),
            active_task_id=str(msg.active_task_id),
            active_transfer_direction=str(msg.active_transfer_direction),
            active_item_id=str(msg.active_item_id),
            active_robot_slot_id=str(msg.active_robot_slot_id),
            fail_code=str(msg.fail_code),
            measured_at_sec=int(msg.timestamp.sec),
            measured_at_nanosec=int(msg.timestamp.nanosec),
            received_at_sec=int(received_at.sec),
            received_at_nanosec=int(received_at.nanosec),
            stale=False,
        )

        with self._lock:
            self._latest_view = view

        self.get_logger().info(
            "IF-DEL-004 status received: "
            f"id={view.arm_id}, role={view.station_role}, state={view.arm_state}, "
            f"task={view.active_task_id or '-'}, direction={view.active_transfer_direction or '-'}, "
            f"item={view.active_item_id or '-'}, slot={view.active_robot_slot_id or '-'}, "
            f"fail={view.fail_code or '-'}"
        )

    def _check_stale(self):
        with self._lock:
            view = self._latest_view

        if view is None:
            self.get_logger().warning("No IF-DEL-004 Jetcobot status snapshot received yet")
            return

        now = self.get_clock().now().nanoseconds / 1_000_000_000
        received = view.received_at_sec + (view.received_at_nanosec / 1_000_000_000)
        stale = (now - received) > self._stale_timeout_sec
        if stale and not view.stale:
            view.stale = True
            self.get_logger().warning(
                f"IF-DEL-004 status became stale for {view.arm_id} "
                f"(timeout={self._stale_timeout_sec:.1f}s)"
            )


def main(args=None):
    rclpy.init(args=args)
    node = JetcobotStatusSubscriber()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
