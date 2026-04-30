#!/usr/bin/env python3

import json
import math
from dataclasses import dataclass

import rclpy
from rcl_interfaces.msg import SetParametersResult
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String


FAST_STATES = {"EXECUTING", "RETURNING_TO_DOCK"}
SLOW_PERIOD_SEC = 1.0
FAST_PERIOD_SEC = 0.2


@dataclass
class PinkyStatusSnapshot:
    pinky_state: str = "IDLE"
    active_task_id: str = ""
    charging_state: str = "NOT_CHARGING"
    docked: bool = False
    battery_percent: float = 82.3
    battery_voltage: float = 24.8
    fail_code: str = ""
    x: float = 0.0
    y: float = 0.0
    yaw_rad: float = 0.0


class PinkyStatusJsonTestPublisher(Node):
    """
    Copy-paste friendly IF-COM-005 publisher.

    This version avoids custom ROS messages so it can be copied to a Pinky
    machine and run with only common ROS2 Python packages installed.
    """

    def __init__(self):
        super().__init__("pinky_status_json_test_publisher")

        self.declare_parameter("pinky_id", "pinky2") #핑키 id
        self.declare_parameter("frame_id", "map") #map 이름
        self.declare_parameter("initial_state", "IDLE")
        self.declare_parameter("initial_active_task_id", "")
        self.declare_parameter("initial_charging_state", "NOT_CHARGING")
        self.declare_parameter("initial_docked", False)
        self.declare_parameter("initial_battery_percent", 82.3)
        self.declare_parameter("initial_battery_voltage", 24.8)
        self.declare_parameter("initial_fail_code", "")
        self.declare_parameter("simulate_motion", True)
        self.declare_parameter("pose_x", 0.0)
        self.declare_parameter("pose_y", 0.0)
        self.declare_parameter("pose_yaw_deg", 0.0)

        self._pinky_id = self.get_parameter("pinky_id").value
        self._frame_id = self.get_parameter("frame_id").value
        self._simulate_motion = bool(self.get_parameter("simulate_motion").value)

        self._snapshot = PinkyStatusSnapshot(
            pinky_state=str(self.get_parameter("initial_state").value),
            active_task_id=str(self.get_parameter("initial_active_task_id").value),
            charging_state=str(self.get_parameter("initial_charging_state").value),
            docked=bool(self.get_parameter("initial_docked").value),
            battery_percent=float(self.get_parameter("initial_battery_percent").value),
            battery_voltage=float(self.get_parameter("initial_battery_voltage").value),
            fail_code=str(self.get_parameter("initial_fail_code").value),
            x=float(self.get_parameter("pose_x").value),
            y=float(self.get_parameter("pose_y").value),
            yaw_rad=math.radians(float(self.get_parameter("pose_yaw_deg").value)),
        )

        self._last_event_key = self._event_key(self._snapshot)
        self._motion_tick = 0.0

        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )
        topic_name = f"/ropi/robots/{self._pinky_id}/status_json"
        self._publisher = self.create_publisher(String, topic_name, qos)
        self.add_on_set_parameters_callback(self._on_parameters_changed)
        self._timer = self.create_timer(self._target_period_sec(), self._on_timer)

        self.get_logger().info(f"Publishing test IF-COM-005 JSON on {topic_name}")
        self._publish_snapshot()

    def _target_period_sec(self) -> float:
        return FAST_PERIOD_SEC if self._snapshot.pinky_state in FAST_STATES else SLOW_PERIOD_SEC

    def _reset_timer_if_needed(self):
        target = self._target_period_sec()
        current = self._timer.timer_period_ns / 1_000_000_000
        if abs(current - target) < 1e-6:
            return
        self._timer.cancel()
        self._timer = self.create_timer(target, self._on_timer)
        self.get_logger().info(f"Adjusted publish period to {target:.1f}s")

    def _build_snapshot(self) -> PinkyStatusSnapshot:
        if self._simulate_motion and self._snapshot.pinky_state in FAST_STATES:
            self._motion_tick += 0.15
            self._snapshot.x = 1.5 + math.cos(self._motion_tick) * 0.8
            self._snapshot.y = 2.0 + math.sin(self._motion_tick) * 0.8
            self._snapshot.yaw_rad = self._motion_tick % (2 * math.pi)
        return self._snapshot

    def _event_key(self, snapshot: PinkyStatusSnapshot):
        return (
            snapshot.pinky_state,
            snapshot.active_task_id,
            snapshot.fail_code,
            snapshot.docked,
            snapshot.charging_state,
        )

    def _build_payload(self) -> dict:
        now = self.get_clock().now().to_msg()
        return {
            "pinky_id": self._pinky_id,
            "pinky_state": self._snapshot.pinky_state,
            "active_task_id": self._snapshot.active_task_id,
            "charging_state": self._snapshot.charging_state,
            "docked": self._snapshot.docked,
            "battery_percent": float(self._snapshot.battery_percent),
            "battery_voltage": float(self._snapshot.battery_voltage),
            "fail_code": self._snapshot.fail_code,
            "pose": {
                "header": {
                    "stamp": {"sec": int(now.sec), "nanosec": int(now.nanosec)},
                    "frame_id": self._frame_id,
                },
                "pose": {
                    "position": {
                        "x": float(self._snapshot.x),
                        "y": float(self._snapshot.y),
                        "z": 0.0,
                    },
                    "orientation": {
                        "x": 0.0,
                        "y": 0.0,
                        "z": math.sin(self._snapshot.yaw_rad / 2.0),
                        "w": math.cos(self._snapshot.yaw_rad / 2.0),
                    },
                },
            },
            "timestamp": {"sec": int(now.sec), "nanosec": int(now.nanosec)},
        }

    def _publish_snapshot(self):
        msg = String()
        msg.data = json.dumps(self._build_payload(), ensure_ascii=False)
        self._publisher.publish(msg)

    def _on_timer(self):
        snapshot = self._build_snapshot()
        event_key = self._event_key(snapshot)
        self._reset_timer_if_needed()
        self._publish_snapshot()
        if event_key != self._last_event_key:
            self.get_logger().info(
                f"Published immediate-change eligible status: state={snapshot.pinky_state}, "
                f"task={snapshot.active_task_id or '-'}, charging={snapshot.charging_state}, "
                f"docked={snapshot.docked}, fail={snapshot.fail_code or '-'}"
            )
        self._last_event_key = event_key

    def _on_parameters_changed(self, params):
        changed = False
        for param in params:
            if param.name == "simulate_motion":
                self._simulate_motion = bool(param.value)
                continue
            if param.name == "initial_state":
                self._snapshot.pinky_state = str(param.value)
            elif param.name == "initial_active_task_id":
                self._snapshot.active_task_id = str(param.value)
            elif param.name == "initial_charging_state":
                self._snapshot.charging_state = str(param.value)
            elif param.name == "initial_docked":
                self._snapshot.docked = bool(param.value)
            elif param.name == "initial_battery_percent":
                self._snapshot.battery_percent = float(param.value)
            elif param.name == "initial_battery_voltage":
                self._snapshot.battery_voltage = float(param.value)
            elif param.name == "initial_fail_code":
                self._snapshot.fail_code = str(param.value)
            elif param.name == "pose_x":
                self._snapshot.x = float(param.value)
            elif param.name == "pose_y":
                self._snapshot.y = float(param.value)
            elif param.name == "pose_yaw_deg":
                self._snapshot.yaw_rad = math.radians(float(param.value))
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
    node = PinkyStatusJsonTestPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
