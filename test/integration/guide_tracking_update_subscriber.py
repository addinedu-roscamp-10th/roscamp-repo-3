#!/usr/bin/env python3

from dataclasses import dataclass
from threading import Lock

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

from ropi_interface.msg import GuideTrackingUpdate


@dataclass
class GuideTrackingSnapshot:
    task_id: str
    target_track_id: str
    tracking_status: str
    tracking_result_seq: int
    bbox_valid: bool
    bbox_xyxy: list[int]
    image_width_px: int
    image_height_px: int


class GuideTrackingUpdateSubscriber(Node):
    """Simple integration-test subscriber for IF-GUI-006."""

    def __init__(self):
        super().__init__("guide_tracking_update_subscriber")

        self.declare_parameter("pinky_id", "pinky1")
        self.declare_parameter("tracking_update_topic", "")

        pinky_id = str(self.get_parameter("pinky_id").value).strip() or "pinky1"
        topic_name = str(self.get_parameter("tracking_update_topic").value).strip()
        if not topic_name:
            topic_name = f"/ropi/guide/{pinky_id}/tracking_update"

        self._lock = Lock()
        self._latest = None

        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=20,
        )
        self.create_subscription(GuideTrackingUpdate, topic_name, self._on_update, qos)
        self.get_logger().info(f"Subscribed to IF-GUI-006 topic {topic_name}")

    def _on_update(self, msg: GuideTrackingUpdate):
        snapshot = GuideTrackingSnapshot(
            task_id=str(msg.task_id),
            target_track_id=str(msg.target_track_id),
            tracking_status=str(msg.tracking_status),
            tracking_result_seq=int(msg.tracking_result_seq),
            bbox_valid=bool(msg.bbox_valid),
            bbox_xyxy=[int(value) for value in list(msg.bbox_xyxy)],
            image_width_px=int(msg.image_width_px),
            image_height_px=int(msg.image_height_px),
        )
        with self._lock:
            self._latest = snapshot

        self.get_logger().info(
            "IF-GUI-006 received: "
            f"task_id={snapshot.task_id}, target_track_id={snapshot.target_track_id or '-'}, "
            f"tracking_status={snapshot.tracking_status}, tracking_result_seq={snapshot.tracking_result_seq}, "
            f"bbox_valid={snapshot.bbox_valid}"
        )


def main(args=None):
    rclpy.init(args=args)
    node = GuideTrackingUpdateSubscriber()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
