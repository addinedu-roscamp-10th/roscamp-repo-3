from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy


DEFAULT_TOPIC_TEMPLATE = "/ropi/control/{pinky_id}/guide_tracking_update"


class RclpyGuideTrackingUpdatePublisher:
    def __init__(self, *, node, message_type_loader=None, topic_template=None):
        self.node = node
        self.message_type_loader = message_type_loader or self._load_message_type
        self.message_type = self.message_type_loader()
        self.topic_template = str(topic_template or DEFAULT_TOPIC_TEMPLATE).strip()
        self._publishers = {}
        self._qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )

    def publish(self, *, pinky_id, update):
        target_pinky_id = str(pinky_id or "").strip()
        publisher = self._publisher_for(target_pinky_id)
        msg = self._build_message(update)
        publisher.publish(msg)
        return {
            "accepted": True,
            "result_code": "ACCEPTED",
            "result_message": "guide tracking update published.",
        }

    async def async_publish(self, *, pinky_id, update):
        return self.publish(pinky_id=pinky_id, update=update)

    def _publisher_for(self, pinky_id):
        if pinky_id not in self._publishers:
            topic_name = self._topic_name(pinky_id)
            self._publishers[pinky_id] = self.node.create_publisher(
                self.message_type,
                topic_name,
                self._qos,
            )
            self.node.get_logger().info(
                f"[guide-publisher] pinky_id={pinky_id} tracking_update={topic_name}"
            )
        return self._publishers[pinky_id]

    def _topic_name(self, pinky_id):
        if "{pinky_id}" in self.topic_template:
            return self.topic_template.format(pinky_id=pinky_id)
        return self.topic_template

    def _build_message(self, update):
        msg = self.message_type()
        msg.task_id = str(update.get("task_id") or "")
        msg.target_track_id = str(update.get("target_track_id") or "")
        msg.tracking_status = str(update.get("tracking_status") or "")
        msg.tracking_result_seq = int(update.get("tracking_result_seq") or 0)
        msg.frame_ts.sec = int(update.get("frame_ts_sec") or 0)
        msg.frame_ts.nanosec = int(update.get("frame_ts_nanosec") or 0)
        msg.bbox_valid = bool(update.get("bbox_valid"))
        msg.bbox_xyxy = [int(value) for value in list(update.get("bbox_xyxy") or [0, 0, 0, 0])]
        msg.image_width_px = int(update.get("image_width_px") or 0)
        msg.image_height_px = int(update.get("image_height_px") or 0)
        return msg

    @staticmethod
    def _load_message_type():
        from ropi_interface.msg import GuideTrackingUpdate

        return GuideTrackingUpdate


__all__ = ["RclpyGuideTrackingUpdatePublisher"]
