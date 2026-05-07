#!/usr/bin/env python3

import math
from dataclasses import dataclass

import rclpy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry
from rcl_interfaces.msg import SetParametersResult
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import BatteryState
from std_msgs.msg import Bool, Float32, String

from ropi_interface.msg import PinkyStatus


FAST_STATES = {"EXECUTING", "RETURNING_TO_DOCK"}
SLOW_PERIOD_SEC = 1.0
FAST_PERIOD_SEC = 0.2
SPEC_PINKY_STATES = {
    "IDLE",
    "EXECUTING",
    "RETURNING_TO_DOCK",
    "DOCK_IDLE",
    "CHARGING",
    "FAIL_RECOVERY",
}
SPEC_CHARGING_STATES = {
    "NOT_CHARGING",
    "CHARGING",
    "CHARGE_COMPLETE",
    "CHARGING_FAIL",
}


@dataclass
class PinkyStatusSnapshot:
    pinky_state: str = "IDLE"
    active_task_id: str = ""
    charging_state: str = "NOT_CHARGING"
    docked: bool = False
    battery_percent: float = 0.0
    battery_voltage: float = 0.0
    fail_code: str = ""
    frame_id: str = "map"
    x: float = 0.0
    y: float = 0.0
    yaw_rad: float = 0.0
    pose_stamp_sec: int = 0
    pose_stamp_nanosec: int = 0


class PinkyStatusRuntimePublisher(Node):
    """IF-COM-005 typed Pinky status publisher using ropi_interface.msg.PinkyStatus."""

    def __init__(self):
        super().__init__("pinky_status_runtime_publisher")

        self.declare_parameter("pinky_id", "pinky2")
        self.declare_parameter("frame_id", "map")
        self.declare_parameter("pose_topic", "")
        self.declare_parameter("odom_topic", "/odom")
        self.declare_parameter("battery_topic", "")
        self.declare_parameter("battery_percent_topic", "")
        self.declare_parameter("battery_voltage_topic", "")
        self.declare_parameter("state_topic", "/transport/amr_status")
        self.declare_parameter("task_topic", "/ropi/robots/{pinky_id}/active_task_id")
        self.declare_parameter("charging_topic", "")
        self.declare_parameter("docked_topic", "")
        self.declare_parameter("fail_topic", "")
        self.declare_parameter("fallback_state", "IDLE")
        self.declare_parameter("fallback_active_task_id", "")
        self.declare_parameter("fallback_charging_state", "NOT_CHARGING")
        self.declare_parameter("fallback_docked", False)
        self.declare_parameter("fallback_battery_percent", 0.0)
        self.declare_parameter("fallback_battery_voltage", 0.0)
        self.declare_parameter("fallback_fail_code", "")
        self.declare_parameter("use_pinkylib_battery", False)
        self.declare_parameter("battery_poll_period_sec", 2.0)
        self.declare_parameter("infer_charging_from_pose", False)
        self.declare_parameter("dock_x_min", 0.0)
        self.declare_parameter("dock_x_max", 0.15)
        self.declare_parameter("dock_y_min", 0.4)
        self.declare_parameter("dock_y_max", 1.0)

        self._pinky_id = str(self.get_parameter("pinky_id").value)
        self._default_frame_id = str(self.get_parameter("frame_id").value)
        self._last_measurement = None
        self._battery = None

        self._snapshot = PinkyStatusSnapshot(
            pinky_state=self._normalize_pinky_state(
                str(self.get_parameter("fallback_state").value)
            ),
            active_task_id=str(self.get_parameter("fallback_active_task_id").value),
            charging_state=self._normalize_charging_state(
                str(self.get_parameter("fallback_charging_state").value)
            ),
            docked=bool(self.get_parameter("fallback_docked").value),
            battery_percent=float(self.get_parameter("fallback_battery_percent").value),
            battery_voltage=float(self.get_parameter("fallback_battery_voltage").value),
            fail_code=str(self.get_parameter("fallback_fail_code").value),
            frame_id=self._default_frame_id,
        )
        self._last_event_key = self._event_key(self._snapshot)

        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=20,
        )
        topic_name = f"/ropi/robots/{self._pinky_id}/status"
        self._publisher = self.create_publisher(PinkyStatus, topic_name, qos)

        pose_topic = str(self.get_parameter("pose_topic").value).strip()
        odom_topic = str(self.get_parameter("odom_topic").value).strip()
        if pose_topic:
            self.create_subscription(PoseStamped, pose_topic, self._on_pose, qos)
            self.get_logger().info(f"Using PoseStamped source topic: {pose_topic}")
        elif odom_topic:
            self.create_subscription(Odometry, odom_topic, self._on_odom, qos)
            self.get_logger().info(f"Using Odometry source topic: {odom_topic}")

        battery_topic = str(self.get_parameter("battery_topic").value).strip()
        battery_percent_topic = str(self.get_parameter("battery_percent_topic").value).strip()
        battery_voltage_topic = str(self.get_parameter("battery_voltage_topic").value).strip()
        if battery_topic:
            self.create_subscription(BatteryState, battery_topic, self._on_battery, qos)
            self.get_logger().info(f"Using BatteryState source topic: {battery_topic}")
        if battery_percent_topic:
            self.create_subscription(Float32, battery_percent_topic, self._on_battery_percent, qos)
            self.get_logger().info(
                f"Using battery percent source topic: {battery_percent_topic}"
            )
        if battery_voltage_topic:
            self.create_subscription(Float32, battery_voltage_topic, self._on_battery_voltage, qos)
            self.get_logger().info(
                f"Using battery voltage source topic: {battery_voltage_topic}"
            )

        state_topic = str(self.get_parameter("state_topic").value).strip()
        if state_topic:
            self.create_subscription(String, state_topic, self._on_state, qos)
            self.get_logger().info(f"Using state source topic: {state_topic}")

        task_topic = self._resolve_topic_parameter("task_topic")
        if task_topic:
            self.create_subscription(String, task_topic, self._on_task, qos)
            self.get_logger().info(f"Using task source topic: {task_topic}")

        charging_topic = self._resolve_topic_parameter("charging_topic")
        if charging_topic:
            self.create_subscription(String, charging_topic, self._on_charging, qos)
            self.get_logger().info(f"Using charging source topic: {charging_topic}")

        docked_topic = self._resolve_topic_parameter("docked_topic")
        if docked_topic:
            self.create_subscription(Bool, docked_topic, self._on_docked, qos)
            self.get_logger().info(f"Using docked source topic: {docked_topic}")

        fail_topic = self._resolve_topic_parameter("fail_topic")
        if fail_topic:
            self.create_subscription(String, fail_topic, self._on_fail, qos)
            self.get_logger().info(f"Using fail source topic: {fail_topic}")

        self._configure_pinkylib_battery()
        self.add_on_set_parameters_callback(self._on_parameters_changed)
        self._timer = self.create_timer(self._target_period_sec(), self._on_timer)
        self.get_logger().info(f"Publishing IF-COM-005 Pinky status on {topic_name}")
        self._publish_snapshot()

    @staticmethod
    def _normalize_pinky_state(raw_state: str) -> str:
        value = str(raw_state or "").strip().upper()
        if not value:
            return "IDLE"
        if value in SPEC_PINKY_STATES:
            return value
        if value.startswith("MOVING_") or value.endswith("_WORKING"):
            return "EXECUTING"
        if value == "MOVING":
            return "EXECUTING"
        if value == "ARRIVED":
            return "IDLE"
        if value in {"RETURNING_HOME", "DOCKING"}:
            return "RETURNING_TO_DOCK"
        if value in {"DONE", "AMR_REJECTED"} or value.endswith("_REJECTED"):
            return "IDLE"
        if value == "FAULT_RECOVERY":
            return "FAIL_RECOVERY"
        if value in {"FAILED", "AMR_FAILED"} or value.endswith("_FAILED"):
            return "FAIL_RECOVERY"
        return value

    def _resolve_topic_parameter(self, name: str) -> str:
        value = str(self.get_parameter(name).value).strip()
        if "{pinky_id}" in value:
            return value.format(pinky_id=self._pinky_id)
        return value

    @staticmethod
    def _normalize_charging_state(raw_state: str) -> str:
        value = str(raw_state or "").strip().upper()
        if not value or value == "UNKNOWN":
            return "NOT_CHARGING"
        if value == "CHARGING_FAULT":
            return "CHARGING_FAIL"
        if value in SPEC_CHARGING_STATES:
            return value
        return value

    def _configure_pinkylib_battery(self):
        if not bool(self.get_parameter("use_pinkylib_battery").value):
            return
        try:
            from pinkylib import Battery

            self._battery = Battery()
            poll_period_sec = max(float(self.get_parameter("battery_poll_period_sec").value), 0.2)
            self.create_timer(poll_period_sec, self._poll_pinkylib_battery)
            self.get_logger().info("Using pinkylib Battery for runtime battery telemetry")
        except Exception as exc:  # pragma: no cover - depends on Pinky runtime
            self.get_logger().warning(f"pinkylib Battery unavailable: {exc}")

    def _poll_pinkylib_battery(self):
        if self._battery is None:
            return
        try:
            self._snapshot.battery_percent = float(self._battery.battery_percentage())
            self._snapshot.battery_voltage = float(self._battery.get_voltage())
            self._mark_measured_now()
        except Exception as exc:  # pragma: no cover - depends on Pinky runtime
            self.get_logger().warning(f"Failed to poll pinkylib Battery: {exc}")
            self._battery = None

    def _target_period_sec(self) -> float:
        state = str(self._snapshot.pinky_state or "").strip().upper()
        return FAST_PERIOD_SEC if state in FAST_STATES else SLOW_PERIOD_SEC

    def _reset_timer_if_needed(self):
        target = self._target_period_sec()
        current = self._timer.timer_period_ns / 1_000_000_000
        if abs(current - target) < 1e-6:
            return
        self._timer.cancel()
        self._timer = self.create_timer(target, self._on_timer)
        self.get_logger().info(f"Adjusted publish period to {target:.1f}s")

    @staticmethod
    def _event_key(snapshot: PinkyStatusSnapshot):
        return (
            snapshot.pinky_state,
            snapshot.active_task_id,
            snapshot.charging_state,
            snapshot.docked,
            snapshot.fail_code,
        )

    @staticmethod
    def _yaw_from_quaternion(z: float, w: float) -> float:
        return 2.0 * math.atan2(z, w)

    @staticmethod
    def _inside_bounds(value: float, first: float, second: float) -> bool:
        lower = min(first, second)
        upper = max(first, second)
        return lower <= value <= upper

    def _infer_charging_from_pose_enabled(self) -> bool:
        return bool(self.get_parameter("infer_charging_from_pose").value)

    def _pose_inside_dock(self) -> bool:
        return (
            self._inside_bounds(
                self._snapshot.x,
                float(self.get_parameter("dock_x_min").value),
                float(self.get_parameter("dock_x_max").value),
            )
            and self._inside_bounds(
                self._snapshot.y,
                float(self.get_parameter("dock_y_min").value),
                float(self.get_parameter("dock_y_max").value),
            )
        )

    def _apply_pose_charging_inference(self) -> bool:
        if not self._infer_charging_from_pose_enabled():
            return False

        docked = self._pose_inside_dock()
        charging_state = "CHARGING" if docked else "NOT_CHARGING"
        changed = (
            docked != self._snapshot.docked
            or charging_state != self._snapshot.charging_state
        )
        self._snapshot.docked = docked
        self._snapshot.charging_state = charging_state
        return changed

    def _mark_measured_now(self):
        self._last_measurement = self.get_clock().now().to_msg()

    def _publish_if_changed(self, changed: bool):
        self._mark_measured_now()
        if changed:
            self._reset_timer_if_needed()
            self._publish_snapshot()

    def _on_pose(self, msg: PoseStamped):
        self._snapshot.frame_id = msg.header.frame_id or self._default_frame_id
        self._snapshot.x = float(msg.pose.position.x)
        self._snapshot.y = float(msg.pose.position.y)
        self._snapshot.yaw_rad = self._yaw_from_quaternion(
            float(msg.pose.orientation.z),
            float(msg.pose.orientation.w),
        )
        self._snapshot.pose_stamp_sec = int(msg.header.stamp.sec)
        self._snapshot.pose_stamp_nanosec = int(msg.header.stamp.nanosec)
        changed = self._apply_pose_charging_inference()
        self._publish_if_changed(changed)

    def _on_odom(self, msg: Odometry):
        self._snapshot.frame_id = msg.header.frame_id or self._default_frame_id
        self._snapshot.x = float(msg.pose.pose.position.x)
        self._snapshot.y = float(msg.pose.pose.position.y)
        self._snapshot.yaw_rad = self._yaw_from_quaternion(
            float(msg.pose.pose.orientation.z),
            float(msg.pose.pose.orientation.w),
        )
        self._snapshot.pose_stamp_sec = int(msg.header.stamp.sec)
        self._snapshot.pose_stamp_nanosec = int(msg.header.stamp.nanosec)
        changed = self._apply_pose_charging_inference()
        self._publish_if_changed(changed)

    def _on_battery(self, msg: BatteryState):
        if not math.isnan(float(msg.percentage)):
            self._snapshot.battery_percent = float(msg.percentage) * 100.0
        if not math.isnan(float(msg.voltage)):
            self._snapshot.battery_voltage = float(msg.voltage)
        self._mark_measured_now()

    def _on_battery_percent(self, msg: Float32):
        self._snapshot.battery_percent = float(msg.data)
        self._mark_measured_now()

    def _on_battery_voltage(self, msg: Float32):
        self._snapshot.battery_voltage = float(msg.data)
        self._mark_measured_now()

    def _on_state(self, msg: String):
        value = self._normalize_pinky_state(msg.data)
        changed = value != self._snapshot.pinky_state
        self._snapshot.pinky_state = value
        self._publish_if_changed(changed)

    def _on_task(self, msg: String):
        value = msg.data.strip()
        changed = value != self._snapshot.active_task_id
        self._snapshot.active_task_id = value
        self._publish_if_changed(changed)

    def _on_charging(self, msg: String):
        value = self._normalize_charging_state(msg.data)
        changed = value != self._snapshot.charging_state
        self._snapshot.charging_state = value
        self._publish_if_changed(changed)

    def _on_docked(self, msg: Bool):
        value = bool(msg.data)
        changed = value != self._snapshot.docked
        self._snapshot.docked = value
        self._publish_if_changed(changed)

    def _on_fail(self, msg: String):
        value = msg.data.strip()
        changed = value != self._snapshot.fail_code
        self._snapshot.fail_code = value
        self._publish_if_changed(changed)

    def _build_msg(self) -> PinkyStatus:
        now = self._last_measurement or self.get_clock().now().to_msg()

        msg = PinkyStatus()
        msg.pinky_id = self._pinky_id
        msg.pinky_state = self._snapshot.pinky_state
        msg.active_task_id = self._snapshot.active_task_id
        msg.charging_state = self._snapshot.charging_state
        msg.docked = self._snapshot.docked
        msg.battery_percent = float(self._snapshot.battery_percent)
        msg.battery_voltage = float(self._snapshot.battery_voltage)
        msg.fail_code = self._snapshot.fail_code
        msg.pose.header.stamp.sec = int(self._snapshot.pose_stamp_sec or now.sec)
        msg.pose.header.stamp.nanosec = int(self._snapshot.pose_stamp_nanosec or now.nanosec)
        msg.pose.header.frame_id = self._snapshot.frame_id or self._default_frame_id
        msg.pose.pose.position.x = float(self._snapshot.x)
        msg.pose.pose.position.y = float(self._snapshot.y)
        msg.pose.pose.position.z = 0.0
        msg.pose.pose.orientation.x = 0.0
        msg.pose.pose.orientation.y = 0.0
        msg.pose.pose.orientation.z = math.sin(self._snapshot.yaw_rad / 2.0)
        msg.pose.pose.orientation.w = math.cos(self._snapshot.yaw_rad / 2.0)
        msg.timestamp.sec = int(now.sec)
        msg.timestamp.nanosec = int(now.nanosec)
        return msg

    def _publish_snapshot(self):
        self._publisher.publish(self._build_msg())

    def _on_timer(self):
        event_key = self._event_key(self._snapshot)
        self._reset_timer_if_needed()
        self._publish_snapshot()
        if event_key != self._last_event_key:
            self.get_logger().info(
                "Published IF-COM-005 status change: "
                f"state={self._snapshot.pinky_state}, "
                f"task={self._snapshot.active_task_id or '-'}, "
                f"charging={self._snapshot.charging_state}, "
                f"docked={self._snapshot.docked}, "
                f"fail={self._snapshot.fail_code or '-'}"
            )
        self._last_event_key = event_key

    def _on_parameters_changed(self, params):
        for param in params:
            if param.name == "fallback_state":
                self._snapshot.pinky_state = self._normalize_pinky_state(str(param.value))
            elif param.name == "fallback_active_task_id":
                self._snapshot.active_task_id = str(param.value)
            elif param.name == "fallback_charging_state":
                self._snapshot.charging_state = self._normalize_charging_state(str(param.value))
            elif param.name == "fallback_docked":
                self._snapshot.docked = bool(param.value)
            elif param.name == "fallback_battery_percent":
                self._snapshot.battery_percent = float(param.value)
            elif param.name == "fallback_battery_voltage":
                self._snapshot.battery_voltage = float(param.value)
            elif param.name == "fallback_fail_code":
                self._snapshot.fail_code = str(param.value)
            elif param.name == "frame_id":
                self._default_frame_id = str(param.value)
            elif param.name in {
                "infer_charging_from_pose",
                "dock_x_min",
                "dock_x_max",
                "dock_y_min",
                "dock_y_max",
            }:
                pass
        self._apply_pose_charging_inference()
        self._mark_measured_now()
        self._reset_timer_if_needed()
        self._publish_snapshot()
        return SetParametersResult(successful=True)


def main(args=None):
    rclpy.init(args=args)
    node = PinkyStatusRuntimePublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        battery = getattr(node, "_battery", None)
        if battery is not None:
            try:
                battery.close()
            except Exception:
                pass
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
