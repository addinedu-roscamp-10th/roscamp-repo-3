from dataclasses import dataclass
from threading import Lock
from typing import Dict

from ropi_interface.msg import GuideTrackingUpdate
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy


DEFAULT_STALE_TIMEOUT_SEC = 3.0
DEFAULT_PINKY_IDS = ("pinky1",)


@dataclass
class GuideTrackingUpdateView:
    pinky_id: str
    task_id: str
    target_track_id: str
    tracking_status: str
    tracking_result_seq: int
    frame_ts_sec: int
    frame_ts_nanosec: int
    bbox_valid: bool
    bbox_xyxy: list[int]
    image_width_px: int
    image_height_px: int
    received_at_sec: int
    received_at_nanosec: int
    stale: bool


class GuideRuntimeSubscriber:
    """Server-side IF-GUI-006 subscriber for guide tracking updates."""

    def __init__(self, node: Node):
        self._node = node
        self._node.declare_parameter("guide_subscriber.pinky_ids", list(DEFAULT_PINKY_IDS))
        self._node.declare_parameter("guide_subscriber.tracking_topic_names", [])
        self._node.declare_parameter(
            "guide_subscriber.tracking_topic_template",
            "/ropi/guide/{pinky_id}/tracking_update",
        )
        self._node.declare_parameter(
            "guide_subscriber.stale_timeout_sec",
            DEFAULT_STALE_TIMEOUT_SEC,
        )

        pinky_ids = self._node.get_parameter("guide_subscriber.pinky_ids").value
        self._pinky_ids = [str(value).strip() for value in pinky_ids if str(value).strip()]
        if not self._pinky_ids:
            self._pinky_ids = list(DEFAULT_PINKY_IDS)

        raw_topic_names = self._node.get_parameter("guide_subscriber.tracking_topic_names").value
        self._tracking_topic_names = [str(value).strip() for value in raw_topic_names if str(value).strip()]
        self._tracking_topic_template = str(
            self._node.get_parameter("guide_subscriber.tracking_topic_template").value
        ).strip()
        self._stale_timeout_sec = float(
            self._node.get_parameter("guide_subscriber.stale_timeout_sec").value
        )

        self._lock = Lock()
        self._latest_updates: Dict[str, GuideTrackingUpdateView] = {}
        self._warned_stale = set()
        self._subscriptions = []

        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=20,
        )

        for index, pinky_id in enumerate(self._pinky_ids):
            topic_name = self._resolve_topic_name(index=index, pinky_id=pinky_id)
            self._subscriptions.append(
                self._node.create_subscription(
                    GuideTrackingUpdate,
                    topic_name,
                    self._build_callback(pinky_id),
                    qos,
                )
            )
            self._node.get_logger().info(
                f"[guide-subscriber] pinky_id={pinky_id} tracking_update={topic_name}"
            )

        self._stale_timer = self._node.create_timer(1.0, self._check_stale)

    @property
    def latest_updates(self) -> Dict[str, GuideTrackingUpdateView]:
        with self._lock:
            return dict(self._latest_updates)

    def _build_callback(self, pinky_id: str):
        def _on_update(msg: GuideTrackingUpdate):
            received_at = self._node.get_clock().now().to_msg()
            view = GuideTrackingUpdateView(
                pinky_id=pinky_id,
                task_id=str(msg.task_id),
                target_track_id=str(msg.target_track_id),
                tracking_status=str(msg.tracking_status),
                tracking_result_seq=int(msg.tracking_result_seq),
                frame_ts_sec=int(msg.frame_ts.sec),
                frame_ts_nanosec=int(msg.frame_ts.nanosec),
                bbox_valid=bool(msg.bbox_valid),
                bbox_xyxy=[int(value) for value in list(msg.bbox_xyxy)],
                image_width_px=int(msg.image_width_px),
                image_height_px=int(msg.image_height_px),
                received_at_sec=int(received_at.sec),
                received_at_nanosec=int(received_at.nanosec),
                stale=False,
            )

            with self._lock:
                current = self._latest_updates.get(pinky_id)
                if current is not None and current.tracking_result_seq > view.tracking_result_seq:
                    return
                self._latest_updates[pinky_id] = view
                self._warned_stale.discard(pinky_id)

            self._node.get_logger().info(
                "IF-GUI-006 tracking update received: "
                f"pinky_id={view.pinky_id}, task_id={view.task_id or '-'}, "
                f"target_track_id={view.target_track_id or '-'}, "
                f"tracking_status={view.tracking_status or '-'}, "
                f"tracking_result_seq={view.tracking_result_seq}"
            )

        return _on_update

    def _check_stale(self):
        with self._lock:
            update_items = list(self._latest_updates.items())

        for pinky_id, view in update_items:
            if self._is_stale(view) and pinky_id not in self._warned_stale:
                self._warned_stale.add(pinky_id)
                view.stale = True
                self._node.get_logger().warning(
                    f"IF-GUI-006 tracking update became stale for {pinky_id} "
                    f"(timeout={self._stale_timeout_sec:.1f}s)"
                )

    def _is_stale(self, view) -> bool:
        now = self._node.get_clock().now().nanoseconds / 1_000_000_000
        received = view.received_at_sec + (view.received_at_nanosec / 1_000_000_000)
        return (now - received) > self._stale_timeout_sec

    def _resolve_topic_name(self, *, index: int, pinky_id: str) -> str:
        if index < len(self._tracking_topic_names):
            return self._tracking_topic_names[index]
        if "{pinky_id}" in self._tracking_topic_template:
            return self._tracking_topic_template.format(pinky_id=pinky_id)
        return self._tracking_topic_template


__all__ = ["GuideRuntimeSubscriber", "GuideTrackingUpdateView"]
