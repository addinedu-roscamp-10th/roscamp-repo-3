import logging

from server.ropi_main_service.application.fall_response_command import (
    FallResponseCommandService,
)
from server.ropi_main_service.application.patrol_states import (
    is_waiting_fall_response,
)
from server.ropi_main_service.persistence.repositories.fall_inference_repository import (
    FALL_DETECTED_REASON,
    FALL_RESPONSE_MESSAGE,
    FallInferenceRepository,
)


DEFAULT_PINKY_ID = "pinky3"
DEFAULT_FALL_STREAK_THRESHOLD_MS = 1000
DEFAULT_COMMAND_TIMEOUT_SEC = 5.0

logger = logging.getLogger(__name__)


class FallInferenceResultProcessor:
    def __init__(
        self,
        *,
        repository=None,
        command_client=None,
        command_execution_recorder=None,
        fall_response_command_service=None,
        task_event_publisher=None,
        pinky_id=DEFAULT_PINKY_ID,
        stream_name=None,
        fall_streak_threshold_ms=DEFAULT_FALL_STREAK_THRESHOLD_MS,
        command_timeout_sec=DEFAULT_COMMAND_TIMEOUT_SEC,
    ):
        self.repository = repository or FallInferenceRepository()
        self.fall_response_command_service = (
            fall_response_command_service
            or FallResponseCommandService(
                command_client=command_client,
                command_execution_recorder=command_execution_recorder,
                timeout_sec=command_timeout_sec,
            )
        )
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
        robot_id = self._result_robot_id(result)
        stream_name = self._result_stream_name(result, robot_id=robot_id)
        active_task = await self.repository.async_get_active_patrol_task_for_robot(robot_id)
        await self.repository.async_record_ai_inference(
            task_id=(active_task or {}).get("task_id"),
            robot_id=robot_id,
            stream_name=stream_name,
            result=result,
        )

        ignore_reason = self._fall_alert_ignore_reason(result, active_task)
        if ignore_reason is not None:
            logger.info(
                "Ignored AI fall inference result robot_id=%s result_seq=%s reason=%s",
                robot_id,
                result.get("result_seq"),
                ignore_reason,
            )
            return {"logged": True, "ignored": True}

        command_response = await self.fall_response_command_service.async_send_start_fall_alert(
            task_id=active_task.get("task_id"),
            robot_id=robot_id,
        )
        if not FallResponseCommandService.is_accepted(command_response):
            logger.warning(
                "Fall response command rejected robot_id=%s task_id=%s result_seq=%s response=%s",
                robot_id,
                active_task.get("task_id"),
                result.get("result_seq"),
                command_response,
            )
            return {"logged": True, "ignored": True}

        alert_response = await self.repository.async_record_fall_alert_started(
            task_id=active_task.get("task_id"),
            robot_id=robot_id,
            trigger_result=result,
            command_response=command_response,
        )
        if alert_response.get("result_code") != "ACCEPTED":
            logger.warning(
                "Fall alert state update rejected robot_id=%s task_id=%s result_seq=%s response=%s",
                robot_id,
                active_task.get("task_id"),
                result.get("result_seq"),
                alert_response,
            )
            return {"logged": True, "ignored": True}

        await self._publish_task_updated(alert_response)
        logger.info(
            "Fall alert started robot_id=%s task_id=%s result_seq=%s",
            robot_id,
            active_task.get("task_id"),
            result.get("result_seq"),
        )
        return {"logged": True, "alert_started": True}

    def _should_start_fall_alert(self, result, active_task):
        return self._fall_alert_ignore_reason(result, active_task) is None

    def _fall_alert_ignore_reason(self, result, active_task):
        if not active_task:
            return "NO_ACTIVE_PATROL_TASK"
        if self._is_waiting_fall_response(active_task):
            return "ALREADY_WAITING_FALL_RESPONSE"
        if result.get("fall_detected") is not True:
            return "NOT_FALL_DETECTED"
        if result.get("alert_candidate") is True:
            return None
        if result.get("alert_candidate") is False:
            return "NOT_ALERT_CANDIDATE"

        fall_streak_ms = self._optional_int(result.get("fall_streak_ms"))
        if fall_streak_ms is not None and fall_streak_ms >= self.fall_streak_threshold_ms:
            return None
        return "FALL_STREAK_BELOW_THRESHOLD"

    def _result_robot_id(self, result):
        return self._optional_text(result.get("pinky_id")) or self.pinky_id

    def _result_stream_name(self, result, *, robot_id):
        stream_name = self._optional_text(result.get("stream_name"))
        if stream_name is not None:
            return stream_name
        if robot_id == self.pinky_id:
            return self.stream_name
        return f"{robot_id}_front_patrol"

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
    def _is_waiting_fall_response(active_task):
        return is_waiting_fall_response(
            phase=active_task.get("phase"),
            patrol_status=active_task.get("patrol_status"),
        )

    @staticmethod
    def _optional_int(value):
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_text(value):
        normalized = str(value or "").strip()
        return normalized or None


__all__ = [
    "FallInferenceResultProcessor",
]
