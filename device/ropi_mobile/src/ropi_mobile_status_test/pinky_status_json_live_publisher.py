#!/usr/bin/env python3

import json
import math
from dataclasses import dataclass

import rclpy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry
from rcl_interfaces.msg import SetParametersResult
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import BatteryState
from std_msgs.msg import Bool, String


FAST_STATES = {"EXECUTING", "RETURNING_TO_DOCK", "MOVING"}
SLOW_PERIOD_SEC = 1.0
FAST_PERIOD_SEC = 0.2


@dataclass
class PinkyStatusSnapshot:
    pinky_state: str = "IDLE"
    active_task_id: str = ""
    charging_state: str = "UNKNOWN"
    docked: bool = False
    battery_percent: float = 0.0
    battery_voltage: float = 0.0
    fault_code: str = ""
    frame_id: str = "map"
    x: float = 0.0
    y: float = 0.0
    yaw_rad: float = 0.0


class PinkyStatusJsonLivePublisher(Node):
    """
    Publish Pinky JSON status using live ROS topics when available.

    This node subscribes to configurable source topics and combines them into
    the existing `/ropi/robots/{pinky_id}/status_json` payload.
    """

    def __init__(self):
        super().__init__("pinky_status_json_live_publisher")

        self.declare_parameter("pinky_id", "pinky_01")
        self.declare_parameter("frame_id", "map")
        self.declare_parameter("publish_topic_suffix", "status_json")
        self.declare_parameter("odom_topic", "/odom")
        self.declare_parameter("pose_topic", "")
        self.declare_parameter("battery_topic", "/battery_state")
        self.declare_parameter("state_topic", "/pinky/state")
        self.declare_parameter("task_topic", "/pinky/active_task_id")
        self.declare_parameter("charging_topic", "/pinky/charging_state")
        self.declare_parameter("docked_topic", "/pinky/docked")
        self.declare_parameter("fault_topic", "/pinky/fault_code")
        self.declare_parameter("fallback_state", "IDLE")
        self.declare_parameter("fallback_charging_state", "UNKNOWN")
        self.declare_parameter("fallback_docked", False)
        self.declare_parameter("fallback_battery_percent", 0.0)
        self.declare_parameter("fallback_battery_voltage", 0.0)
        self.declare_parameter("fallback_fault_code", "")
        self.declare_parameter("publish_even_if_missing_sources", True)

        self._pinky_id = str(self.get_parameter("pinky_id").value)
        self._default_frame_id = str(self.get_parameter("frame_id").value)
        self._publish_even_if_missing_sources = bool(
            self.get_parameter("publish_even_if_missing_sources").value
        )

        self._snapshot = PinkyStatusSnapshot(
            pinky_state=str(self.get_parameter("fallback_state").value),
            active_task_id="",
            charging_state=str(self.get_parameter("fallback_charging_state").value),
            docked=bool(self.get_parameter("fallback_docked").value),
            battery_percent=float(self.get_parameter("fallback_battery_percent").value),
            battery_voltage=float(self.get_parameter("fallback_battery_voltage").value),
            fault_code=str(self.get_parameter("fallback_fault_code").value),
            frame_id=self._default_frame_id,
        )
        self._received = {
            "pose": False,
            "battery": False,
            "state": False,
            "task": False,
            "charging": False,
            "docked": False,
            "fault": False,
        }
        self._last_event_key = self._event_key(self._snapshot)

        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=20,
        )

        publish_topic = (
            f"/ropi/robots/{self._pinky_id}/"
            f"{self.get_parameter('publish_topic_suffix').value}"
        )
        self._publisher = self.create_publisher(String, publish_topic, qos)

        pose_topic = str(self.get_parameter("pose_topic").value).strip()
        odom_topic = str(self.get_parameter("odom_topic").value).strip()
        if pose_topic:
            self.create_subscription(PoseStamped, pose_topic, self._on_pose, qos)
            self.get_logger().info(f"Using PoseStamped source topic: {pose_topic}")
        elif odom_topic:
            self.create_subscription(Odometry, odom_topic, self._on_odom, qos)
            self.get_logger().info(f"Using Odometry source topic: {odom_topic}")

        battery_topic = str(self.get_parameter("battery_topic").value).strip()
        if battery_topic:
            self.create_subscription(BatteryState, battery_topic, self._on_battery, qos)
            self.get_logger().info(f"Using BatteryState source topic: {battery_topic}")

        state_topic = str(self.get_parameter("state_topic").value).strip()
        if state_topic:
            self.create_subscription(String, state_topic, self._on_state, qos)
            self.get_logger().info(f"Using state source topic: {state_topic}")

        task_topic = str(self.get_parameter("task_topic").value).strip()
        if task_topic:
            self.create_subscription(String, task_topic, self._on_task, qos)
            self.get_logger().info(f"Using task source topic: {task_topic}")

        charging_topic = str(self.get_parameter("charging_topic").value).strip()
        if charging_topic:
            self.create_subscription(String, charging_topic, self._on_charging, qos)
            self.get_logger().info(f"Using charging source topic: {charging_topic}")

        docked_topic = str(self.get_parameter("docked_topic").value).strip()
        if docked_topic:
            self.create_subscription(Bool, docked_topic, self._on_docked, qos)
            self.get_logger().info(f"Using docked source topic: {docked_topic}")

        fault_topic = str(self.get_parameter("fault_topic").value).strip()
        if fault_topic:
            self.create_subscription(String, fault_topic, self._on_fault, qos)
            self.get_logger().info(f"Using fault source topic: {fault_topic}")

        self.add_on_set_parameters_callback(self._on_parameters_changed)
        self._timer = self.create_timer(self._target_period_sec(), self._on_timer)
        self.get_logger().info(f"Publishing live Pinky JSON on {publish_topic}")
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

    def _event_key(self, snapshot: PinkyStatusSnapshot):
        return (
            snapshot.pinky_state,
            snapshot.active_task_id,
            snapshot.charging_state,
            snapshot.docked,
            snapshot.fault_code,
        )

    def _yaw_from_quaternion(self, z: float, w: float) -> float:
        return 2.0 * math.atan2(z, w)

    def _on_pose(self, msg: PoseStamped):
        self._snapshot.frame_id = msg.header.frame_id or self._default_frame_id
        self._snapshot.x = float(msg.pose.position.x)
        self._snapshot.y = float(msg.pose.position.y)
        self._snapshot.yaw_rad = self._yaw_from_quaternion(
            float(msg.pose.orientation.z),
            float(msg.pose.orientation.w),
        )
        self._received["pose"] = True

    def _on_odom(self, msg: Odometry):
        self._snapshot.frame_id = msg.header.frame_id or self._default_frame_id
        self._snapshot.x = float(msg.pose.pose.position.x)
        self._snapshot.y = float(msg.pose.pose.position.y)
        self._snapshot.yaw_rad = self._yaw_from_quaternion(
            float(msg.pose.pose.orientation.z),
            float(msg.pose.pose.orientation.w),
        )
        self._received["pose"] = True

    def _on_battery(self, msg: BatteryState):
        if not math.isnan(float(msg.percentage)):
            self._snapshot.battery_percent = float(msg.percentage) * 100.0
        if not math.isnan(float(msg.voltage)):
            self._snapshot.battery_voltage = float(msg.voltage)
        self._received["battery"] = True

    def _on_state(self, msg: String):
        self._snapshot.pinky_state = msg.data.strip() or self._snapshot.pinky_state
        self._received["state"] = True
        self._reset_timer_if_needed()

    def _on_task(self, msg: String):
        self._snapshot.active_task_id = msg.data.strip()
        self._received["task"] = True

    def _on_charging(self, msg: String):
        self._snapshot.charging_state = msg.data.strip() or self._snapshot.charging_state
        self._received["charging"] = True

    def _on_docked(self, msg: Bool):
        self._snapshot.docked = bool(msg.data)
        self._received["docked"] = True

    def _on_fault(self, msg: String):
        self._snapshot.fault_code = msg.data.strip()
        self._received["fault"] = True

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
            "fault_code": self._snapshot.fault_code,
            "pose": {
                "header": {
                    "stamp": {"sec": int(now.sec), "nanosec": int(now.nanosec)},
                    "frame_id": self._snapshot.frame_id or self._default_frame_id,
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
            "sources": self._received,
        }

    def _publish_snapshot(self):
        if not self._publish_even_if_missing_sources and not any(self._received.values()):
            return
        msg = String()
        msg.data = json.dumps(self._build_payload(), ensure_ascii=False)
        self._publisher.publish(msg)

    def _on_timer(self):
        event_key = self._event_key(self._snapshot)
        self._reset_timer_if_needed()
        self._publish_snapshot()
        if event_key != self._last_event_key:
            self.get_logger().info(
                "Published live status change: "
                f"state={self._snapshot.pinky_state}, "
                f"task={self._snapshot.active_task_id or '-'}, "
                f"charging={self._snapshot.charging_state}, "
                f"docked={self._snapshot.docked}, "
                f"fault={self._snapshot.fault_code or '-'}"
            )
        self._last_event_key = event_key

    def _on_parameters_changed(self, params):
        for param in params:
            if param.name == "fallback_state":
                self._snapshot.pinky_state = str(param.value)
            elif param.name == "fallback_charging_state":
                self._snapshot.charging_state = str(param.value)
            elif param.name == "fallback_docked":
                self._snapshot.docked = bool(param.value)
            elif param.name == "fallback_battery_percent":
                self._snapshot.battery_percent = float(param.value)
            elif param.name == "fallback_battery_voltage":
                self._snapshot.battery_voltage = float(param.value)
            elif param.name == "fallback_fault_code":
                self._snapshot.fault_code = str(param.value)
            elif param.name == "frame_id":
                self._default_frame_id = str(param.value)
        self._reset_timer_if_needed()
        self._publish_snapshot()
        return SetParametersResult(successful=True)


def main(args=None):
    rclpy.init(args=args)
    node = PinkyStatusJsonLivePublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
