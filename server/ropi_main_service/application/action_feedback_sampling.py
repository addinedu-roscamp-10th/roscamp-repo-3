import math
import time

from server.ropi_main_service.application.delivery_config import get_delivery_runtime_config


class ActionFeedbackSampleBuilder:
    def __init__(self, *, runtime_config=None):
        self.runtime_config = runtime_config or get_delivery_runtime_config()

    def build_sample(self, feedback):
        robot_id = self._resolve_robot_id(feedback)
        if not robot_id:
            return None

        pose_x, pose_y, pose_yaw = self._extract_pose(feedback.get("payload") or {})
        return {
            "robot_id": robot_id,
            "task_id": self._parse_numeric_task_id(feedback.get("task_id")),
            "data_type": str(feedback.get("feedback_type") or "ACTION_FEEDBACK"),
            "pose_x": pose_x,
            "pose_y": pose_y,
            "pose_yaw": pose_yaw,
            "battery_percent": None,
            "payload": feedback,
        }

    def _resolve_robot_id(self, feedback):
        parts = str(feedback.get("action_name") or "").strip("/").split("/")
        if len(parts) >= 4 and parts[0] == "ropi" and parts[1] == "control":
            return parts[2] or None

        if len(parts) >= 4 and parts[0] == "ropi" and parts[1] == "arm":
            arm_id = parts[2]
            if arm_id == self.runtime_config.pickup_arm_id:
                return self.runtime_config.pickup_arm_robot_id
            if arm_id == self.runtime_config.destination_arm_id:
                return self.runtime_config.destination_arm_robot_id

        return None

    @staticmethod
    def _parse_numeric_task_id(task_id):
        raw = str(task_id or "").strip()
        return int(raw) if raw.isdigit() else None

    @classmethod
    def _extract_pose(cls, payload):
        current_pose = payload.get("current_pose")
        if not isinstance(current_pose, dict):
            return None, None, None

        pose = current_pose.get("pose")
        if not isinstance(pose, dict):
            return None, None, None

        position = pose.get("position") or {}
        orientation = pose.get("orientation") or {}
        pose_x = position.get("x")
        pose_y = position.get("y")
        return pose_x, pose_y, cls._yaw_from_quaternion(orientation)

    @staticmethod
    def _yaw_from_quaternion(orientation):
        try:
            x = float(orientation.get("x") or 0.0)
            y = float(orientation.get("y") or 0.0)
            z = float(orientation.get("z") or 0.0)
            w = float(orientation.get("w") or 1.0)
        except (TypeError, ValueError):
            return None

        return math.atan2(
            2.0 * (w * z + x * y),
            1.0 - 2.0 * (y * y + z * z),
        )


class FeedbackSamplingGate:
    def __init__(self, *, sample_interval_sec):
        self.sample_interval_sec = float(sample_interval_sec)
        self._last_sampled_monotonic_by_key = {}

    def should_sample(self, feedback):
        key = (
            str(feedback.get("task_id") or "").strip(),
            str(feedback.get("action_name") or "").strip(),
            str(feedback.get("feedback_type") or "").strip(),
        )
        now = time.monotonic()
        last_sampled = self._last_sampled_monotonic_by_key.get(key)
        if last_sampled is not None and now - last_sampled < self.sample_interval_sec:
            return False

        self._last_sampled_monotonic_by_key[key] = now
        return True


__all__ = ["ActionFeedbackSampleBuilder", "FeedbackSamplingGate"]
