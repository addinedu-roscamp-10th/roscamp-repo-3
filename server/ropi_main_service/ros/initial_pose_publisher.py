import math


DEFAULT_INITIAL_POSE_COVARIANCE_X = 0.25
DEFAULT_INITIAL_POSE_COVARIANCE_Y = 0.25
DEFAULT_INITIAL_POSE_COVARIANCE_YAW = 0.0685


class InitialPosePublisher:
    def __init__(self, *, node, message_type=None):
        self.node = node
        self.message_type = message_type or self._default_message_type()
        self._publishers_by_topic = {}

    def publish_initial_pose(
        self,
        *,
        robot_id,
        x,
        y,
        yaw,
        frame_id="map",
        covariance=None,
    ):
        normalized_robot_id = self._normalize_robot_id(robot_id)
        topic = f"/{normalized_robot_id}/initialpose"
        message = self._build_message(
            frame_id=str(frame_id or "map").strip() or "map",
            x=float(x),
            y=float(y),
            yaw=float(yaw),
            covariance=covariance,
        )
        self._publisher_for_topic(topic).publish(message)
        return {
            "result_code": "ACCEPTED",
            "robot_id": normalized_robot_id,
            "topic": topic,
            "frame_id": message.header.frame_id,
            "x": float(x),
            "y": float(y),
            "yaw": float(yaw),
        }

    def _build_message(self, *, frame_id, x, y, yaw, covariance):
        message = self.message_type()
        message.header.stamp = self.node.get_clock().now().to_msg()
        message.header.frame_id = frame_id
        message.pose.pose.position.x = x
        message.pose.pose.position.y = y
        message.pose.pose.position.z = 0.0
        message.pose.pose.orientation.x = 0.0
        message.pose.pose.orientation.y = 0.0
        message.pose.pose.orientation.z = math.sin(yaw / 2.0)
        message.pose.pose.orientation.w = math.cos(yaw / 2.0)
        message.pose.covariance = self._normalize_covariance(covariance)
        return message

    def _publisher_for_topic(self, topic):
        publisher = self._publishers_by_topic.get(topic)
        if publisher is None:
            publisher = self.node.create_publisher(self.message_type, topic, 10)
            self._publishers_by_topic[topic] = publisher
        return publisher

    @staticmethod
    def _normalize_robot_id(robot_id):
        value = str(robot_id or "").strip()
        if not value or value.startswith("/") or "/" in value:
            raise ValueError("robot_id must be a relative robot namespace.")
        return value

    @staticmethod
    def _normalize_covariance(covariance):
        if covariance is None:
            values = [0.0] * 36
            values[0] = DEFAULT_INITIAL_POSE_COVARIANCE_X
            values[7] = DEFAULT_INITIAL_POSE_COVARIANCE_Y
            values[35] = DEFAULT_INITIAL_POSE_COVARIANCE_YAW
            return values
        if not isinstance(covariance, (list, tuple)) or len(covariance) != 36:
            raise ValueError("covariance must contain 36 numeric values.")
        return [float(value) for value in covariance]

    @staticmethod
    def _default_message_type():
        from geometry_msgs.msg import PoseWithCovarianceStamped

        return PoseWithCovarianceStamped


__all__ = [
    "DEFAULT_INITIAL_POSE_COVARIANCE_X",
    "DEFAULT_INITIAL_POSE_COVARIANCE_Y",
    "DEFAULT_INITIAL_POSE_COVARIANCE_YAW",
    "InitialPosePublisher",
]
