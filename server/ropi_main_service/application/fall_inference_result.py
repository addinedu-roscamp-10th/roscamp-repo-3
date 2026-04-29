import asyncio

from server.ropi_main_service.application.command_execution import (
    CommandExecutionRecorder,
    CommandExecutionSpec,
)
from server.ropi_main_service.ipc.uds_client import UnixDomainSocketCommandClient
from server.ropi_main_service.persistence.repositories.fall_inference_repository import (
    FALL_DETECTED_REASON,
    FALL_RESPONSE_MESSAGE,
    FallInferenceRepository,
)


DEFAULT_PINKY_ID = "pinky3"
DEFAULT_FALL_STREAK_THRESHOLD_MS = 1000
DEFAULT_COMMAND_TIMEOUT_SEC = 5.0


class FallInferenceResultProcessor:
    def __init__(
        self,
        *,
        repository=None,
        command_client=None,
        command_execution_recorder=None,
        task_event_publisher=None,
        pinky_id=DEFAULT_PINKY_ID,
        stream_name=None,
        fall_streak_threshold_ms=DEFAULT_FALL_STREAK_THRESHOLD_MS,
        command_timeout_sec=DEFAULT_COMMAND_TIMEOUT_SEC,
    ):
        self.repository = repository or FallInferenceRepository()
        self.command_client = command_client or UnixDomainSocketCommandClient()
        self.command_execution_recorder = command_execution_recorder or CommandExecutionRecorder()
        self.task_event_publisher = task_event_publisher
        self.pinky_id = str(pinky_id or DEFAULT_PINKY_ID).strip() or DEFAULT_PINKY_ID
        self.stream_name = str(stream_name or f"{self.pinky_id}_front_patrol").strip()
        self.fall_streak_threshold_ms = int(fall_streak_threshold_ms)
        self.command_timeout_sec = float(command_timeout_sec)

    async def async_process_batch(self, batch):
        results = list((batch or {}).get("results") or [])
        summary = {
            "processed_count": 0,
            "logged_count": 0,
            "alert_started_count": 0,
            "ignored_count": 0,
        }

        for result in results:
            outcome = await self._async_process_result(result if isinstance(result, dict) else {})
            summary["processed_count"] += 1
            if outcome.get("logged"):
                summary["logged_count"] += 1
            if outcome.get("alert_started"):
                summary["alert_started_count"] += 1
            if outcome.get("ignored"):
                summary["ignored_count"] += 1

        return summary

    async def _async_process_result(self, result):
        active_task = await self.repository.async_get_active_patrol_task_for_robot(self.pinky_id)
        await self.repository.async_record_ai_inference(
            task_id=(active_task or {}).get("task_id"),
            robot_id=self.pinky_id,
            stream_name=self.stream_name,
            result=result,
        )

        if not self._should_start_fall_alert(result, active_task):
            return {"logged": True, "ignored": True}

        command_payload = self._build_fall_response_command_payload(active_task)
        command_response = await self._async_send_fall_response_command(
            task_id=active_task.get("task_id"),
            robot_id=self.pinky_id,
            payload=command_payload,
        )
        if not self._is_command_accepted(command_response):
            return {"logged": True, "ignored": True}

        alert_response = await self.repository.async_record_fall_alert_started(
            task_id=active_task.get("task_id"),
            robot_id=self.pinky_id,
            trigger_result=result,
            command_response=command_response,
        )
        if alert_response.get("result_code") != "ACCEPTED":
            return {"logged": True, "ignored": True}

        await self._publish_task_updated(alert_response)
        return {"logged": True, "alert_started": True}

    def _should_start_fall_alert(self, result, active_task):
        if not active_task:
            return False
        if self._is_waiting_fall_response(active_task):
            return False
        if result.get("fall_detected") is not True:
            return False

        fall_streak_ms = self._optional_int(result.get("fall_streak_ms"))
        return fall_streak_ms is not None and fall_streak_ms >= self.fall_streak_threshold_ms

    async def _async_send_fall_response_command(self, *, task_id, robot_id, payload):
        spec = CommandExecutionSpec(
            task_id=str(task_id),
            transport="ROS_SERVICE",
            command_type="FALL_RESPONSE_CONTROL",
            command_phase="FALL_ALERT_START",
            target_component="ros_service",
            target_robot_id=robot_id,
            target_endpoint=f"/ropi/control/{robot_id}/fall_response_control",
            request_payload=payload,
        )

        async def _send_command():
            async_send_command = getattr(self.command_client, "async_send_command", None)
            if async_send_command is not None:
                return await async_send_command(
                    "fall_response_control",
                    payload,
                    timeout=self.command_timeout_sec,
                )
            return await asyncio.to_thread(
                self.command_client.send_command,
                "fall_response_control",
                payload,
                timeout=self.command_timeout_sec,
            )

        return await self.command_execution_recorder.async_record(spec, _send_command)

    def _build_fall_response_command_payload(self, active_task):
        return {
            "pinky_id": self.pinky_id,
            "task_id": str(active_task.get("task_id")),
            "command_type": "START_FALL_ALERT",
        }

    async def _publish_task_updated(self, alert_response):
        if self.task_event_publisher is None:
            return

        await self.task_event_publisher.publish(
            "TASK_UPDATED",
            {
                "source": "FALL_ALERT",
                "task_id": alert_response.get("task_id"),
                "task_type": "PATROL",
                "task_status": alert_response.get("task_status"),
                "phase": alert_response.get("phase"),
                "assigned_robot_id": alert_response.get("assigned_robot_id"),
                "latest_reason_code": alert_response.get("latest_reason_code")
                or FALL_DETECTED_REASON,
                "result_code": alert_response.get("result_code"),
                "result_message": alert_response.get("result_message")
                or FALL_RESPONSE_MESSAGE,
                "cancel_requested": None,
                "cancellable": alert_response.get("cancellable", True),
            },
        )

    @staticmethod
    def _is_command_accepted(response):
        return isinstance(response, dict) and bool(response.get("accepted"))

    @staticmethod
    def _is_waiting_fall_response(active_task):
        phase = str(active_task.get("phase") or "").strip()
        patrol_status = str(active_task.get("patrol_status") or "").strip()
        return phase in {"WAIT_FALL_RESPONSE", "WAITING_FALL_RESPONSE"} or patrol_status in {
            "WAIT_FALL_RESPONSE",
            "WAITING_FALL_RESPONSE",
        }

    @staticmethod
    def _optional_int(value):
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


__all__ = [
    "FallInferenceResultProcessor",
]
