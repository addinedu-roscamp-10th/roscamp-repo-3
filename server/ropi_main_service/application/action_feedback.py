import asyncio
import math
import time

from server.ropi_main_service.application.delivery_config import get_delivery_runtime_config
from server.ropi_main_service.ipc.uds_client import UnixDomainSocketCommandClient
from server.ropi_main_service.persistence.repositories.robot_data_log_repository import (
    RobotDataLogRepository,
)


DEFAULT_ACTION_FEEDBACK_TIMEOUT_SEC = 1.0
DEFAULT_ACTION_FEEDBACK_SAMPLE_INTERVAL_SEC = 5.0


class RosActionFeedbackService:
    def __init__(
        self,
        *,
        command_client=None,
        robot_data_log_repository=None,
        runtime_config=None,
        feedback_timeout_sec=DEFAULT_ACTION_FEEDBACK_TIMEOUT_SEC,
        sample_interval_sec=DEFAULT_ACTION_FEEDBACK_SAMPLE_INTERVAL_SEC,
    ):
        self.command_client = command_client or UnixDomainSocketCommandClient()
        self.robot_data_log_repository = robot_data_log_repository or RobotDataLogRepository()
        self.runtime_config = runtime_config or get_delivery_runtime_config()
        self.feedback_timeout_sec = float(feedback_timeout_sec)
        self.sample_interval_sec = float(sample_interval_sec)
        self._last_sampled_monotonic_by_key = {}

    def get_latest_feedback(self, *, task_id, action_name=None):
        response = self.command_client.send_command(
            "get_action_feedback",
            self._build_payload(task_id=task_id, action_name=action_name),
            timeout=self.feedback_timeout_sec,
        )
        self._record_feedback_samples(response)
        return response

    async def async_get_latest_feedback(self, *, task_id, action_name=None):
        payload = self._build_payload(task_id=task_id, action_name=action_name)
        async_send_command = getattr(self.command_client, "async_send_command", None)

        if async_send_command is not None:
            response = await async_send_command(
                "get_action_feedback",
                payload,
                timeout=self.feedback_timeout_sec,
            )
            await self._async_record_feedback_samples(response)
            return response

        response = await asyncio.to_thread(
            self.command_client.send_command,
            "get_action_feedback",
            payload,
            timeout=self.feedback_timeout_sec,
        )
        await self._async_record_feedback_samples(response)
        return response

    @staticmethod
    def _build_payload(*, task_id, action_name=None):
        payload = {
            "task_id": str(task_id).strip(),
        }
        if action_name is not None:
            payload["action_name"] = str(action_name).strip()
        return payload

    def _record_feedback_samples(self, response):
        for feedback in response.get("feedback") or []:
            sample = self._build_feedback_sample(feedback)
            if sample is None or not self._should_sample(feedback):
                continue

            try:
                self.robot_data_log_repository.insert_feedback_sample(**sample)
            except Exception:
                continue

    async def _async_record_feedback_samples(self, response):
        for feedback in response.get("feedback") or []:
            sample = self._build_feedback_sample(feedback)
            if sample is None or not self._should_sample(feedback):
                continue

            try:
                await self.robot_data_log_repository.async_insert_feedback_sample(**sample)
            except Exception:
                continue

    def _build_feedback_sample(self, feedback):
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

    def _should_sample(self, feedback):
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


__all__ = ["RosActionFeedbackService"]
