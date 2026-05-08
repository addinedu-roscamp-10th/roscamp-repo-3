import argparse
import json
import math
from dataclasses import dataclass
from threading import Lock


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
    x: float
    y: float
    theta_deg: float
    received_at_sec: int
    received_at_nanosec: int
    stale: bool


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
    received_at_sec: int
    received_at_nanosec: int
    stale: bool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Monitor ROPI robot status ROS topics from the server package."
    )
    subparsers = parser.add_subparsers(dest="target", required=True)

    pinky_parser = subparsers.add_parser(
        "pinky",
        help="Subscribe to IF-COM-005 typed Pinky status.",
    )
    pinky_parser.add_argument("--pinky-id", default="pinky2")
    _add_common_options(pinky_parser)
    pinky_parser.set_defaults(factory=_create_pinky_status_monitor)

    pinky_json_parser = subparsers.add_parser(
        "pinky-json",
        help="Subscribe to copy-paste Pinky JSON status.",
    )
    pinky_json_parser.add_argument("--pinky-id", default="pinky2")
    _add_common_options(pinky_json_parser)
    pinky_json_parser.set_defaults(factory=_create_pinky_json_status_monitor)

    arm_parser = subparsers.add_parser(
        "arm",
        help="Subscribe to IF-DEL-004 typed Jetcobot arm status.",
    )
    arm_parser.add_argument("--arm-id", default="arm1")
    _add_common_options(arm_parser)
    arm_parser.set_defaults(factory=_create_arm_status_monitor)

    arm_json_parser = subparsers.add_parser(
        "arm-json",
        help="Subscribe to Jetcobot arm JSON status.",
    )
    arm_json_parser.add_argument("--arm-id", default="arm1")
    _add_common_options(arm_json_parser)
    arm_json_parser.set_defaults(factory=_create_arm_json_status_monitor)

    return parser


def run(argv=None) -> None:
    args = build_parser().parse_args(argv)

    import rclpy

    rclpy.init(args=None)
    node = args.factory(args)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


def main(argv=None):
    run(argv)


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--stale-timeout-sec",
        type=float,
        default=DEFAULT_STALE_TIMEOUT_SEC,
        help="Warn when no status snapshot arrives within this many seconds.",
    )


def _create_qos():
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

    return QoSProfile(
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.VOLATILE,
        history=HistoryPolicy.KEEP_LAST,
        depth=20,
    )


def _create_pinky_status_monitor(args):
    from rclpy.node import Node
    from ropi_interface.msg import PinkyStatus

    class PinkyStatusMonitor(Node):
        def __init__(self):
            super().__init__("ropi_server_pinky_status_monitor")
            self._stale_timeout_sec = float(args.stale_timeout_sec)
            self._latest_view = None
            self._lock = Lock()

            topic_name = f"/ropi/robots/{args.pinky_id}/status"
            self.create_subscription(PinkyStatus, topic_name, self._on_status, _create_qos())
            self.create_timer(1.0, self._check_stale)
            self.get_logger().info(f"Subscribed to IF-COM-005 Pinky status {topic_name}")

        def _on_status(self, msg):
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
                x=float(msg.pose.pose.position.x),
                y=float(msg.pose.pose.position.y),
                theta_deg=_yaw_deg(
                    float(msg.pose.pose.orientation.z),
                    float(msg.pose.pose.orientation.w),
                ),
                received_at_sec=int(received_at.sec),
                received_at_nanosec=int(received_at.nanosec),
                stale=False,
            )
            self._store_pinky_view(view)

        def _store_pinky_view(self, view: PinkyStatusView):
            with self._lock:
                self._latest_view = view
            self.get_logger().info(
                "IF-COM-005 status received: "
                f"id={view.pinky_id}, state={view.pinky_state}, "
                f"task={view.active_task_id or '-'}, charging={view.charging_state}, "
                f"docked={view.docked}, battery={view.battery_percent:.1f}%/"
                f"{view.battery_voltage:.2f}V, pose=({view.x:.2f}, {view.y:.2f}, "
                f"{view.theta_deg:.1f}deg), fail={view.fail_code or '-'}"
            )

        def _check_stale(self):
            _check_stale_view(
                node=self,
                lock=self._lock,
                latest_view_getter=lambda: self._latest_view,
                stale_timeout_sec=self._stale_timeout_sec,
                label=f"IF-COM-005 status for {args.pinky_id}",
            )

    return PinkyStatusMonitor()


def _create_pinky_json_status_monitor(args):
    from rclpy.node import Node
    from std_msgs.msg import String

    class PinkyJsonStatusMonitor(Node):
        def __init__(self):
            super().__init__("ropi_server_pinky_json_status_monitor")
            self._stale_timeout_sec = float(args.stale_timeout_sec)
            self._latest_view = None
            self._lock = Lock()

            topic_name = f"/ropi/robots/{args.pinky_id}/status_json"
            self.create_subscription(String, topic_name, self._on_status, _create_qos())
            self.create_timer(1.0, self._check_stale)
            self.get_logger().info(f"Subscribed to Pinky JSON status {topic_name}")

        def _on_status(self, msg):
            try:
                payload = json.loads(msg.data)
            except json.JSONDecodeError as exc:
                self.get_logger().warning(f"Invalid Pinky status JSON: {exc}")
                return

            pose = payload.get("pose", {})
            pose_pose = pose.get("pose", {})
            position = pose_pose.get("position", {})
            orientation = pose_pose.get("orientation", {})
            received_at = self.get_clock().now().to_msg()
            qz = _float_value(orientation.get("z"), 0.0)
            qw = _float_value(orientation.get("w"), 1.0)
            view = PinkyStatusView(
                pinky_id=_string_value(payload.get("pinky_id")),
                pinky_state=_string_value(payload.get("pinky_state")),
                active_task_id=_string_value(
                    payload.get("active_task_id", payload.get("task_id"))
                ),
                charging_state=_string_value(payload.get("charging_state")),
                docked=bool(payload.get("docked", False)),
                battery_percent=_float_value(payload.get("battery_percent"), 0.0),
                battery_voltage=_float_value(payload.get("battery_voltage"), 0.0),
                fail_code=_string_value(payload.get("fail_code", payload.get("fault_code"))),
                frame_id=_string_value(pose.get("header", {}).get("frame_id")),
                x=_float_value(position.get("x"), 0.0),
                y=_float_value(position.get("y"), 0.0),
                theta_deg=_yaw_deg(qz, qw),
                received_at_sec=int(received_at.sec),
                received_at_nanosec=int(received_at.nanosec),
                stale=False,
            )
            with self._lock:
                self._latest_view = view
            self.get_logger().info(f"IF-COM-005 JSON received: {msg.data}")

        def _check_stale(self):
            _check_stale_view(
                node=self,
                lock=self._lock,
                latest_view_getter=lambda: self._latest_view,
                stale_timeout_sec=self._stale_timeout_sec,
                label=f"Pinky JSON status for {args.pinky_id}",
            )

    return PinkyJsonStatusMonitor()


def _create_arm_status_monitor(args):
    from rclpy.node import Node
    from ropi_arm_status_test.msg import ArmStatus

    class ArmStatusMonitor(Node):
        def __init__(self):
            super().__init__("ropi_server_arm_status_monitor")
            self._stale_timeout_sec = float(args.stale_timeout_sec)
            self._latest_view = None
            self._lock = Lock()

            topic_name = f"/ropi/arms/{args.arm_id}/status"
            self.create_subscription(ArmStatus, topic_name, self._on_status, _create_qos())
            self.create_timer(1.0, self._check_stale)
            self.get_logger().info(f"Subscribed to IF-DEL-004 Jetcobot status {topic_name}")

        def _on_status(self, msg):
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
                received_at_sec=int(received_at.sec),
                received_at_nanosec=int(received_at.nanosec),
                stale=False,
            )
            with self._lock:
                self._latest_view = view
            self.get_logger().info(
                "IF-DEL-004 status received: "
                f"id={view.arm_id}, role={view.station_role}, state={view.arm_state}, "
                f"task={view.active_task_id or '-'}, "
                f"direction={view.active_transfer_direction or '-'}, "
                f"item={view.active_item_id or '-'}, "
                f"slot={view.active_robot_slot_id or '-'}, fail={view.fail_code or '-'}"
            )

        def _check_stale(self):
            _check_stale_view(
                node=self,
                lock=self._lock,
                latest_view_getter=lambda: self._latest_view,
                stale_timeout_sec=self._stale_timeout_sec,
                label=f"IF-DEL-004 status for {args.arm_id}",
            )

    return ArmStatusMonitor()


def _create_arm_json_status_monitor(args):
    from rclpy.node import Node
    from std_msgs.msg import String

    class ArmJsonStatusMonitor(Node):
        def __init__(self):
            super().__init__("ropi_server_arm_json_status_monitor")
            self._stale_timeout_sec = float(args.stale_timeout_sec)
            self._latest_view = None
            self._lock = Lock()

            topic_name = f"/ropi/arms/{args.arm_id}/status_json"
            self.create_subscription(String, topic_name, self._on_status, _create_qos())
            self.create_timer(1.0, self._check_stale)
            self.get_logger().info(f"Subscribed to Jetcobot JSON status {topic_name}")

        def _on_status(self, msg):
            try:
                payload = json.loads(msg.data)
            except json.JSONDecodeError as exc:
                self.get_logger().warning(f"Invalid Jetcobot status JSON: {exc}")
                return

            received_at = self.get_clock().now().to_msg()
            view = ArmStatusView(
                arm_id=_string_value(payload.get("arm_id")),
                station_role=_string_value(payload.get("station_role")),
                arm_state=_string_value(payload.get("arm_state")),
                active_task_id=_string_value(payload.get("active_task_id")),
                active_transfer_direction=_string_value(payload.get("active_transfer_direction")),
                active_item_id=_string_value(payload.get("active_item_id")),
                active_robot_slot_id=_string_value(payload.get("active_robot_slot_id")),
                fail_code=_string_value(payload.get("fail_code", payload.get("fault_code"))),
                received_at_sec=int(received_at.sec),
                received_at_nanosec=int(received_at.nanosec),
                stale=False,
            )
            with self._lock:
                self._latest_view = view
            self.get_logger().info(f"Jetcobot JSON received: {msg.data}")

        def _check_stale(self):
            _check_stale_view(
                node=self,
                lock=self._lock,
                latest_view_getter=lambda: self._latest_view,
                stale_timeout_sec=self._stale_timeout_sec,
                label=f"Jetcobot JSON status for {args.arm_id}",
            )

    return ArmJsonStatusMonitor()


def _check_stale_view(*, node, lock, latest_view_getter, stale_timeout_sec, label):
    with lock:
        view = latest_view_getter()

    if view is None:
        node.get_logger().warning(f"No {label} snapshot received yet")
        return

    now = node.get_clock().now().nanoseconds / 1_000_000_000
    received = view.received_at_sec + (view.received_at_nanosec / 1_000_000_000)
    stale = (now - received) > stale_timeout_sec
    if stale and not view.stale:
        view.stale = True
        node.get_logger().warning(f"{label} became stale (timeout={stale_timeout_sec:.1f}s)")


def _yaw_deg(z: float, w: float) -> float:
    return math.degrees(2.0 * math.atan2(z, w))


def _string_value(value, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _float_value(value, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


if __name__ == "__main__":
    main()
