import asyncio
import math
from dataclasses import dataclass
from threading import Lock
from typing import Dict, TYPE_CHECKING

from server.ropi_main_service.persistence.background_db_writer import (
    get_default_background_db_writer,
)

if TYPE_CHECKING:
    from rclpy.node import Node


DEFAULT_PINKY_IDS = ("pinky1", "pinky2", "pinky3")
DEFAULT_ARM_IDS = ("arm1", "arm2")
DEFAULT_ARM_ROBOT_ID_MAP = {
    "arm1": "jetcobot1",
    "arm2": "jetcobot2",
}


@dataclass
class RuntimeStatusView:
    robot_id: str
    robot_kind: str
    runtime_state: str
    active_task_id: int | None
    battery_percent: float | None
    pose_x: float | None
    pose_y: float | None
    pose_yaw: float | None
    frame_id: str | None
    fault_code: str | None

    def to_db_status(self) -> dict:
        return {
            "robot_id": self.robot_id,
            "robot_kind": self.robot_kind,
            "runtime_state": self.runtime_state,
            "active_task_id": self.active_task_id,
            "battery_percent": self.battery_percent,
            "pose_x": self.pose_x,
            "pose_y": self.pose_y,
            "pose_yaw": self.pose_yaw,
            "frame_id": self.frame_id,
            "fault_code": self.fault_code,
        }


class StatusRuntimeSubscriber:
    """Server-side robot status subscriber that updates robot_runtime_status."""

    def __init__(self, node: "Node", *, loop=None, db_writer=None):
        self._node = node
        self._loop = loop or asyncio.get_running_loop()
        self._db_writer = db_writer or get_default_background_db_writer()
        self._lock = Lock()
        self._latest_by_robot_id: Dict[str, RuntimeStatusView] = {}
        self._subscriptions = []

        self._node.declare_parameter("status_runtime_subscriber.enabled", True)
        self._node.declare_parameter(
            "status_runtime_subscriber.pinky_ids",
            list(DEFAULT_PINKY_IDS),
        )
        self._node.declare_parameter(
            "status_runtime_subscriber.pinky_topic_template",
            "/ropi/robots/{pinky_id}/status",
        )
        self._node.declare_parameter(
            "status_runtime_subscriber.arm_ids",
            list(DEFAULT_ARM_IDS),
        )
        self._node.declare_parameter(
            "status_runtime_subscriber.arm_topic_template",
            "/ropi/arms/{arm_id}/status",
        )
        self._node.declare_parameter(
            "status_runtime_subscriber.arm_robot_ids",
            [DEFAULT_ARM_ROBOT_ID_MAP[arm_id] for arm_id in DEFAULT_ARM_IDS],
        )

        if not bool(self._node.get_parameter("status_runtime_subscriber.enabled").value):
            self._node.get_logger().info("Status runtime subscriber disabled by parameter.")
            return

        self._subscribe_pinky_status()
        self._subscribe_arm_status()

    @property
    def latest_by_robot_id(self) -> Dict[str, RuntimeStatusView]:
        with self._lock:
            return dict(self._latest_by_robot_id)

    def _subscribe_pinky_status(self):
        try:
            from ropi_interface.msg import PinkyStatus
        except ImportError as exc:
            self._node.get_logger().warning(
                f"Pinky status runtime subscriber disabled: {exc}"
            )
            return

        topic_template = str(
            self._node.get_parameter("status_runtime_subscriber.pinky_topic_template").value
        ).strip()
        for pinky_id in self._parameter_list("status_runtime_subscriber.pinky_ids"):
            topic_name = topic_template.format(pinky_id=pinky_id)
            self._subscriptions.append(
                self._node.create_subscription(
                    PinkyStatus,
                    topic_name,
                    self._build_pinky_callback(pinky_id),
                    _create_qos(),
                )
            )
            self._node.get_logger().info(
                f"[status-runtime] pinky_id={pinky_id} status_topic={topic_name}"
            )

    def _subscribe_arm_status(self):
        try:
            from ropi_arm_status_test.msg import ArmStatus
        except ImportError as exc:
            self._node.get_logger().warning(
                f"Arm status runtime subscriber disabled: {exc}"
            )
            return

        topic_template = str(
            self._node.get_parameter("status_runtime_subscriber.arm_topic_template").value
        ).strip()
        arm_robot_id_map = self._arm_robot_id_map()
        for arm_id in self._parameter_list("status_runtime_subscriber.arm_ids"):
            robot_id = arm_robot_id_map.get(arm_id, arm_id)
            topic_name = topic_template.format(arm_id=arm_id, robot_id=robot_id)
            self._subscriptions.append(
                self._node.create_subscription(
                    ArmStatus,
                    topic_name,
                    self._build_arm_callback(arm_id=arm_id, robot_id=robot_id),
                    _create_qos(),
                )
            )
            self._node.get_logger().info(
                f"[status-runtime] arm_id={arm_id} robot_id={robot_id} "
                f"status_topic={topic_name}"
            )

    def _build_pinky_callback(self, pinky_id: str):
        def _on_status(msg):
            runtime_state = _normalized_text(msg.pinky_state) or "UNKNOWN"
            view = RuntimeStatusView(
                robot_id=_normalized_text(msg.pinky_id) or pinky_id,
                robot_kind="PINKY",
                runtime_state=runtime_state,
                active_task_id=_numeric_task_id(msg.active_task_id),
                battery_percent=_optional_float(msg.battery_percent),
                pose_x=_optional_float(msg.pose.pose.position.x),
                pose_y=_optional_float(msg.pose.pose.position.y),
                pose_yaw=_yaw_from_quaternion(
                    x=msg.pose.pose.orientation.x,
                    y=msg.pose.pose.orientation.y,
                    z=msg.pose.pose.orientation.z,
                    w=msg.pose.pose.orientation.w,
                ),
                frame_id=_normalized_optional_text(msg.pose.header.frame_id),
                fault_code=_normalized_optional_text(msg.fail_code),
            )
            self._record_status(view)

        return _on_status

    def _build_arm_callback(self, *, arm_id: str, robot_id: str):
        def _on_status(msg):
            view = RuntimeStatusView(
                robot_id=robot_id,
                robot_kind="JETCOBOT",
                runtime_state=_normalized_text(msg.arm_state) or "UNKNOWN",
                active_task_id=_numeric_task_id(msg.active_task_id),
                battery_percent=None,
                pose_x=None,
                pose_y=None,
                pose_yaw=None,
                frame_id=None,
                fault_code=_normalized_optional_text(msg.fail_code),
            )
            self._record_status(view)

        return _on_status

    def _record_status(self, view: RuntimeStatusView):
        with self._lock:
            self._latest_by_robot_id[view.robot_id] = view

        self._loop.call_soon_threadsafe(
            self._db_writer.enqueue_robot_runtime_status,
            view.to_db_status(),
        )
        self._node.get_logger().debug(
            "Queued robot_runtime_status update: "
            f"robot_id={view.robot_id}, state={view.runtime_state}, "
            f"battery={view.battery_percent}"
        )

    def _parameter_list(self, name: str) -> list[str]:
        values = self._node.get_parameter(name).value
        result = [str(value).strip() for value in values if str(value).strip()]
        return result

    def _arm_robot_id_map(self):
        arm_ids = self._parameter_list("status_runtime_subscriber.arm_ids")
        robot_ids = self._parameter_list("status_runtime_subscriber.arm_robot_ids")
        mapping = dict(DEFAULT_ARM_ROBOT_ID_MAP)
        for index, arm_id in enumerate(arm_ids):
            if index < len(robot_ids):
                mapping[arm_id] = robot_ids[index]
        return mapping


def _create_qos():
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

    return QoSProfile(
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.VOLATILE,
        history=HistoryPolicy.KEEP_LAST,
        depth=20,
    )


def _normalized_text(value) -> str:
    return str(value or "").strip()


def _normalized_optional_text(value) -> str | None:
    text = _normalized_text(value)
    return text or None


def _optional_float(value) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric):
        return None
    return numeric


def _numeric_task_id(value) -> int | None:
    text = _normalized_text(value)
    return int(text) if text.isdigit() else None


def _yaw_from_quaternion(*, x, y, z, w) -> float | None:
    try:
        qx = float(x)
        qy = float(y)
        qz = float(z)
        qw = float(w)
    except (TypeError, ValueError):
        return None

    return math.atan2(
        2.0 * (qw * qz + qx * qy),
        1.0 - 2.0 * (qy * qy + qz * qz),
    )


__all__ = ["RuntimeStatusView", "StatusRuntimeSubscriber"]
