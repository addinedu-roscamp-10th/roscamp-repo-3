#!/usr/bin/env python3

import json
from dataclasses import dataclass

import rclpy
from builtin_interfaces.msg import Time
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String

from ropi_interface.msg import GuideTrackingUpdate


@dataclass
class DetectionView:
    found: bool
    track_id: str
    cx: int
    cy: int
    width: int
    height: int
    frame_width: int
    frame_height: int


class GuideTrackingUpdateBridge(Node):
    """Bridge guide-team JSON tracking topic into IF-GUI-006 typed updates."""

    def __init__(self):
        super().__init__("guide_tracking_update_bridge")

        self.declare_parameter("pinky_id", "pinky1")
        self.declare_parameter("task_id", "task_guide_test_001")
        self.declare_parameter("json_detection_topic", "tracking")
        self.declare_parameter(
            "tracking_update_topic",
            "",
        )
        self.declare_parameter("default_target_track_id", "")

        self._pinky_id = str(self.get_parameter("pinky_id").value).strip() or "pinky1"
        self._task_id = str(self.get_parameter("task_id").value).strip() or "task_guide_test_001"
        self._default_target_track_id = str(
            self.get_parameter("default_target_track_id").value
        ).strip()
        self._seq = 0

        detection_topic = str(self.get_parameter("json_detection_topic").value).strip() or "tracking"
        tracking_update_topic = str(self.get_parameter("tracking_update_topic").value).strip()
        if not tracking_update_topic:
            tracking_update_topic = f"/ropi/guide/{self._pinky_id}/tracking_update"

        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=20,
        )
        self._publisher = self.create_publisher(GuideTrackingUpdate, tracking_update_topic, qos)
        self.create_subscription(String, detection_topic, self._on_detection, qos)

        self.get_logger().info(
            f"Bridge ready pinky_id={self._pinky_id} "
            f"json_detection_topic={detection_topic} "
            f"tracking_update_topic={tracking_update_topic}"
        )

    def _on_detection(self, msg: String):
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError as exc:
            self.get_logger().warning(f"Invalid guide tracking JSON: {exc}")
            return

        detection = DetectionView(
            found=bool(payload.get("found", False)),
            track_id=str(payload.get("track_id", "")),
            cx=int(payload.get("cx", -1)),
            cy=int(payload.get("cy", -1)),
            width=max(0, int(payload.get("w", 0))),
            height=max(0, int(payload.get("h", 0))),
            frame_width=max(0, int(payload.get("frame_w", 0))),
            frame_height=max(0, int(payload.get("frame_h", 0))),
        )

        self._seq += 1
        update = GuideTrackingUpdate()
        update.task_id = self._task_id
        update.target_track_id = detection.track_id or self._default_target_track_id
        update.tracking_status = self._build_tracking_status(detection)
        update.tracking_result_seq = self._seq
        update.frame_ts = self._build_now()
        update.bbox_valid = detection.found and detection.width > 0 and detection.height > 0
        update.bbox_xyxy = self._build_bbox_xyxy(detection)
        update.image_width_px = detection.frame_width
        update.image_height_px = detection.frame_height

        self._publisher.publish(update)
        self.get_logger().info(
            "Published IF-GUI-006 tracking update: "
            f"task_id={update.task_id}, target_track_id={update.target_track_id or '-'}, "
            f"tracking_status={update.tracking_status}, tracking_result_seq={update.tracking_result_seq}"
        )

    def _build_tracking_status(self, detection: DetectionView) -> str:
        if detection.found and detection.width > 0 and detection.height > 0:
            return "TRACKING"
        return "LOST"

    def _build_bbox_xyxy(self, detection: DetectionView) -> list[int]:
        if not (detection.found and detection.width > 0 and detection.height > 0):
            return [0, 0, 0, 0]
        half_w = detection.width // 2
        half_h = detection.height // 2
        x1 = max(0, detection.cx - half_w)
        y1 = max(0, detection.cy - half_h)
        x2 = min(max(0, detection.frame_width), detection.cx + half_w)
        y2 = min(max(0, detection.frame_height), detection.cy + half_h)
        return [int(x1), int(y1), int(x2), int(y2)]

    def _build_now(self) -> Time:
        now = self.get_clock().now().to_msg()
        stamp = Time()
        stamp.sec = int(now.sec)
        stamp.nanosec = int(now.nanosec)
        return stamp


def main(args=None):
    rclpy.init(args=args)
    node = GuideTrackingUpdateBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
