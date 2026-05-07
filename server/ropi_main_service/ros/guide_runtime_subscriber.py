from dataclasses import dataclass
from threading import Lock
from typing import Dict

from ropi_interface.msg import GuidePhaseSnapshot
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy


DEFAULT_STALE_TIMEOUT_SEC = 3.0
DEFAULT_PINKY_IDS = ("pinky1",)


@dataclass
class GuidePhaseSnapshotView:
    pinky_id: str
    task_id: str
    guide_phase: str
    target_track_id: int
    reason_code: str
    seq: int
    occurred_at_sec: int
    occurred_at_nanosec: int
    received_at_sec: int
    received_at_nanosec: int
    stale: bool


class GuideRuntimeSubscriber:
    """Server-side IF-GUI-007 subscriber for guide phase snapshots."""

    def __init__(self, node: Node):
        self._node = node
        self._node.declare_parameter("guide_subscriber.pinky_ids", list(DEFAULT_PINKY_IDS))
        self._node.declare_parameter("guide_subscriber.phase_topic_names", [])
        self._node.declare_parameter(
            "guide_subscriber.phase_topic_template",
            "/ropi/control/{pinky_id}/guide_phase_snapshot",
        )
        self._node.declare_parameter(
            "guide_subscriber.stale_timeout_sec",
            DEFAULT_STALE_TIMEOUT_SEC,
        )

        pinky_ids = self._node.get_parameter("guide_subscriber.pinky_ids").value
        self._pinky_ids = [str(value).strip() for value in pinky_ids if str(value).strip()]
        if not self._pinky_ids:
            self._pinky_ids = list(DEFAULT_PINKY_IDS)

        raw_topic_names = self._node.get_parameter("guide_subscriber.phase_topic_names").value
        self._phase_topic_names = [str(value).strip() for value in raw_topic_names if str(value).strip()]
        self._phase_topic_template = str(
            self._node.get_parameter("guide_subscriber.phase_topic_template").value
        ).strip()
        self._stale_timeout_sec = float(
            self._node.get_parameter("guide_subscriber.stale_timeout_sec").value
        )

        self._lock = Lock()
        self._latest_updates: Dict[str, GuidePhaseSnapshotView] = {}
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
                    GuidePhaseSnapshot,
                    topic_name,
                    self._build_callback(pinky_id),
                    qos,
                )
            )
            self._node.get_logger().info(
                f"[guide-subscriber] pinky_id={pinky_id} guide_phase_snapshot={topic_name}"
            )

        self._stale_timer = self._node.create_timer(1.0, self._check_stale)

    @property
    def latest_updates(self) -> Dict[str, GuidePhaseSnapshotView]:
        with self._lock:
            return dict(self._latest_updates)

    def _build_callback(self, pinky_id: str):
        def _on_update(msg: GuidePhaseSnapshot):
            received_at = self._node.get_clock().now().to_msg()
            view = GuidePhaseSnapshotView(
                pinky_id=str(msg.pinky_id or pinky_id),
                task_id=str(msg.task_id),
                guide_phase=str(msg.guide_phase),
                target_track_id=int(msg.target_track_id),
                reason_code=str(msg.reason_code),
                seq=int(msg.seq),
                occurred_at_sec=int(msg.occurred_at.sec),
                occurred_at_nanosec=int(msg.occurred_at.nanosec),
                received_at_sec=int(received_at.sec),
                received_at_nanosec=int(received_at.nanosec),
                stale=False,
            )

            with self._lock:
                current = self._latest_updates.get(pinky_id)
                if current is not None and current.seq > view.seq:
                    return
                self._latest_updates[pinky_id] = view
                self._warned_stale.discard(pinky_id)

            self._node.get_logger().info(
                "IF-GUI-007 guide phase snapshot received: "
                f"pinky_id={view.pinky_id}, task_id={view.task_id or '-'}, "
                f"guide_phase={view.guide_phase or '-'}, "
                f"target_track_id={view.target_track_id}, seq={view.seq}"
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
                    f"IF-GUI-007 guide phase snapshot became stale for {pinky_id} "
                    f"(timeout={self._stale_timeout_sec:.1f}s)"
                )

    def _is_stale(self, view) -> bool:
        now = self._node.get_clock().now().nanoseconds / 1_000_000_000
        received = view.received_at_sec + (view.received_at_nanosec / 1_000_000_000)
        return (now - received) > self._stale_timeout_sec

    def _resolve_topic_name(self, *, index: int, pinky_id: str) -> str:
        if index < len(self._phase_topic_names):
            return self._phase_topic_names[index]
        if "{pinky_id}" in self._phase_topic_template:
            return self._phase_topic_template.format(pinky_id=pinky_id)
        return self._phase_topic_template


__all__ = ["GuidePhaseSnapshotView", "GuideRuntimeSubscriber"]
