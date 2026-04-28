import asyncio

from server.ropi_main_service.application.action_feedback_sampling import (
    ActionFeedbackSampleBuilder,
    FeedbackSamplingGate,
)
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
        feedback_sample_builder=None,
        feedback_sampling_gate=None,
        feedback_timeout_sec=DEFAULT_ACTION_FEEDBACK_TIMEOUT_SEC,
        sample_interval_sec=DEFAULT_ACTION_FEEDBACK_SAMPLE_INTERVAL_SEC,
    ):
        self.command_client = command_client or UnixDomainSocketCommandClient()
        self.robot_data_log_repository = robot_data_log_repository or RobotDataLogRepository()
        self.feedback_sample_builder = feedback_sample_builder or ActionFeedbackSampleBuilder(
            runtime_config=runtime_config
        )
        self.feedback_sampling_gate = feedback_sampling_gate or FeedbackSamplingGate(
            sample_interval_sec=sample_interval_sec
        )
        self.feedback_timeout_sec = float(feedback_timeout_sec)

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
            sample = self.feedback_sample_builder.build_sample(feedback)
            if sample is None or not self.feedback_sampling_gate.should_sample(feedback):
                continue

            try:
                self.robot_data_log_repository.insert_feedback_sample(**sample)
            except Exception:
                continue

    async def _async_record_feedback_samples(self, response):
        for feedback in response.get("feedback") or []:
            sample = self.feedback_sample_builder.build_sample(feedback)
            if sample is None or not self.feedback_sampling_gate.should_sample(feedback):
                continue

            try:
                await self.robot_data_log_repository.async_insert_feedback_sample(**sample)
            except Exception:
                continue


__all__ = ["RosActionFeedbackService"]
