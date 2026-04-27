#!/usr/bin/env python3

import json
from dataclasses import dataclass

import rclpy
from rcl_interfaces.msg import SetParametersResult
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String


FAST_STATES = {"MOVING", "PICKING", "PLACING"}
SLOW_PERIOD_SEC = 1.0
FAST_PERIOD_SEC = 0.2


@dataclass
class JetcobotStatusSnapshot:
    station_role: str = "PICKUP"
    arm_state: str = "READY"
    active_task_id: str = ""
    active_transfer_direction: str = ""
    active_item_id: str = ""
    active_robot_slot_id: str = ""
    fault_code: str = ""


class JetcobotStatusJsonPublisher(Node):
    """Copy-paste friendly Jetcobot JSON status publisher."""

    def __init__(self):
        super().__init__("jetcobot_status_json_publisher")

        self.declare_parameter("arm_id", "jetcobot_01")
        self.declare_parameter("station_role", "PICKUP")
        self.declare_parameter("initial_arm_state", "READY")
        self.declare_parameter("initial_active_task_id", "")
        self.declare_parameter("initial_active_transfer_direction", "")
        self.declare_parameter("initial_active_item_id", "")
        self.declare_parameter("initial_active_robot_slot_id", "")
        self.declare_parameter("initial_fault_code", "")

        self._arm_id = str(self.get_parameter("arm_id").value)
        self._snapshot = JetcobotStatusSnapshot(
            station_role=str(self.get_parameter("station_role").value),
            arm_state=str(self.get_parameter("initial_arm_state").value),
            active_task_id=str(self.get_parameter("initial_active_task_id").value),
            active_transfer_direction=str(self.get_parameter("initial_active_transfer_direction").value),
            active_item_id=str(self.get_parameter("initial_active_item_id").value),
            active_robot_slot_id=str(self.get_parameter("initial_active_robot_slot_id").value),
            fault_code=str(self.get_parameter("initial_fault_code").value),
        )
        self._last_event_key = self._event_key(self._snapshot)

        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )
        topic_name = f"/ropi/arms/{self._arm_id}/status_json"
        self._publisher = self.create_publisher(String, topic_name, qos)
        self.add_on_set_parameters_callback(self._on_parameters_changed)
        self._timer = self.create_timer(self._target_period_sec(), self._on_timer)

        self.get_logger().info(f"Publishing Jetcobot JSON status on {topic_name}")
        self._publish_snapshot()

    def _target_period_sec(self) -> float:
        return FAST_PERIOD_SEC if self._snapshot.arm_state in FAST_STATES else SLOW_PERIOD_SEC

    def _reset_timer_if_needed(self):
        target = self._target_period_sec()
        current = self._timer.timer_period_ns / 1_000_000_000
        if abs(current - target) < 1e-6:
            return
        self._timer.cancel()
        self._timer = self.create_timer(target, self._on_timer)
        self.get_logger().info(f"Adjusted publish period to {target:.1f}s")

    @staticmethod
    def _event_key(snapshot: JetcobotStatusSnapshot):
        return (
            snapshot.arm_state,
            snapshot.active_task_id,
            snapshot.active_transfer_direction,
            snapshot.active_item_id,
            snapshot.active_robot_slot_id,
            snapshot.fault_code,
        )

    def _build_payload(self) -> dict:
        now = self.get_clock().now().to_msg()
        return {
            "arm_id": self._arm_id,
            "station_role": self._snapshot.station_role,
            "arm_state": self._snapshot.arm_state,
            "active_task_id": self._snapshot.active_task_id,
            "active_transfer_direction": self._snapshot.active_transfer_direction,
            "active_item_id": self._snapshot.active_item_id,
            "active_robot_slot_id": self._snapshot.active_robot_slot_id,
            "fault_code": self._snapshot.fault_code,
            "timestamp": {"sec": int(now.sec), "nanosec": int(now.nanosec)},
        }

    def _publish_snapshot(self):
        msg = String()
        msg.data = json.dumps(self._build_payload(), ensure_ascii=False)
        self._publisher.publish(msg)

    def _on_timer(self):
        self._reset_timer_if_needed()
        self._publish_snapshot()
        event_key = self._event_key(self._snapshot)
        if event_key != self._last_event_key:
            self.get_logger().info(
                f"Published state change: arm_state={self._snapshot.arm_state}, "
                f"task={self._snapshot.active_task_id or '-'}, "
                f"item={self._snapshot.active_item_id or '-'}, "
                f"fault={self._snapshot.fault_code or '-'}"
            )
        self._last_event_key = event_key

    def _on_parameters_changed(self, params):
        changed = False
        for param in params:
            if param.name == "station_role":
                self._snapshot.station_role = str(param.value)
            elif param.name == "initial_arm_state":
                self._snapshot.arm_state = str(param.value)
            elif param.name == "initial_active_task_id":
                self._snapshot.active_task_id = str(param.value)
            elif param.name == "initial_active_transfer_direction":
                self._snapshot.active_transfer_direction = str(param.value)
            elif param.name == "initial_active_item_id":
                self._snapshot.active_item_id = str(param.value)
            elif param.name == "initial_active_robot_slot_id":
                self._snapshot.active_robot_slot_id = str(param.value)
            elif param.name == "initial_fault_code":
                self._snapshot.fault_code = str(param.value)
            else:
                continue
            changed = True

        self._reset_timer_if_needed()
        if changed:
            self._publish_snapshot()
            self._last_event_key = self._event_key(self._snapshot)
        return SetParametersResult(successful=True)


def main(args=None):
    rclpy.init(args=args)
    node = JetcobotStatusJsonPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
