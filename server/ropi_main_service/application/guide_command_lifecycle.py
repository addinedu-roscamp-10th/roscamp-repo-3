from server.ropi_main_service.application.guide_command import GuideCommandService
from server.ropi_main_service.application.guide_runtime import DEFAULT_GUIDE_PINKY_ID
from server.ropi_main_service.persistence.repositories.guide_task_lifecycle_repository import (
    GuideTaskLifecycleRepository,
)


class GuideCommandLifecycleService:
    def __init__(
        self,
        *,
        guide_command_service=None,
        guide_task_lifecycle_repository=None,
        default_pinky_id=DEFAULT_GUIDE_PINKY_ID,
    ):
        self.guide_command_service = guide_command_service or GuideCommandService()
        self.guide_task_lifecycle_repository = (
            guide_task_lifecycle_repository or GuideTaskLifecycleRepository()
        )
        self.default_pinky_id = str(default_pinky_id).strip() or DEFAULT_GUIDE_PINKY_ID

    def send_command(
        self,
        *,
        task_id,
        command_type,
        pinky_id=None,
        target_track_id="",
        wait_timeout_sec=0,
        finish_reason="",
    ):
        target_pinky_id = self._resolve_pinky_id(pinky_id)
        try:
            response = self.guide_command_service.send(
                task_id=task_id,
                pinky_id=target_pinky_id,
                command_type=command_type,
                target_track_id=target_track_id,
                wait_timeout_sec=wait_timeout_sec,
                finish_reason=finish_reason,
            )
        except Exception as exc:
            response = self._build_transport_error_response(exc)
        response = self._attach_lifecycle(
            response=response,
            task_id=task_id,
            pinky_id=target_pinky_id,
            command_type=command_type,
            target_track_id=target_track_id,
            wait_timeout_sec=wait_timeout_sec,
            finish_reason=finish_reason,
        )
        return self._finalize_response(response)

    async def async_send_command(
        self,
        *,
        task_id,
        command_type,
        pinky_id=None,
        target_track_id="",
        wait_timeout_sec=0,
        finish_reason="",
    ):
        target_pinky_id = self._resolve_pinky_id(pinky_id)
        try:
            response = await self.guide_command_service.async_send(
                task_id=task_id,
                pinky_id=target_pinky_id,
                command_type=command_type,
                target_track_id=target_track_id,
                wait_timeout_sec=wait_timeout_sec,
                finish_reason=finish_reason,
            )
        except Exception as exc:
            response = self._build_transport_error_response(exc)
        response = await self._async_attach_lifecycle(
            response=response,
            task_id=task_id,
            pinky_id=target_pinky_id,
            command_type=command_type,
            target_track_id=target_track_id,
            wait_timeout_sec=wait_timeout_sec,
            finish_reason=finish_reason,
        )
        return self._finalize_response(response)

    def _attach_lifecycle(
        self,
        *,
        response,
        task_id,
        pinky_id,
        command_type,
        target_track_id,
        wait_timeout_sec,
        finish_reason,
    ):
        if self._normalize_positive_id(task_id) is None:
            return response

        lifecycle_result = self.guide_task_lifecycle_repository.record_command_result(
            task_id=task_id,
            pinky_id=pinky_id,
            command_type=command_type,
            target_track_id=target_track_id,
            wait_timeout_sec=wait_timeout_sec,
            finish_reason=finish_reason,
            command_response=response,
        )
        return self._merge_lifecycle_response(response, lifecycle_result)

    async def _async_attach_lifecycle(
        self,
        *,
        response,
        task_id,
        pinky_id,
        command_type,
        target_track_id,
        wait_timeout_sec,
        finish_reason,
    ):
        if self._normalize_positive_id(task_id) is None:
            return response

        lifecycle_result = (
            await self.guide_task_lifecycle_repository.async_record_command_result(
                task_id=task_id,
                pinky_id=pinky_id,
                command_type=command_type,
                target_track_id=target_track_id,
                wait_timeout_sec=wait_timeout_sec,
                finish_reason=finish_reason,
                command_response=response,
            )
        )
        return self._merge_lifecycle_response(response, lifecycle_result)

    @staticmethod
    def _merge_lifecycle_response(command_response, lifecycle_result):
        response = dict(command_response or {}) if isinstance(command_response, dict) else {}
        original_accepted = bool(response.get("accepted"))
        if lifecycle_result:
            response["lifecycle_result"] = lifecycle_result
            for key in (
                "result_code",
                "result_message",
                "reason_code",
                "task_id",
                "task_type",
                "task_status",
                "phase",
                "assigned_robot_id",
                "guide_phase",
                "target_track_id",
                "accepted",
            ):
                if lifecycle_result.get(key) is not None:
                    response[key] = lifecycle_result[key]
            if (
                not original_accepted
                and lifecycle_result.get("accepted")
                and lifecycle_result.get("result_message")
            ):
                response["message"] = lifecycle_result["result_message"]
        return response

    @staticmethod
    def _finalize_response(response):
        accepted = bool((response or {}).get("accepted"))
        message = str((response or {}).get("message") or "").strip()
        reason_code = str((response or {}).get("reason_code") or "").strip()
        if accepted:
            return True, message or "안내 제어 명령이 수락되었습니다.", response
        return False, message or "안내 제어 명령이 거부되었습니다.", (response or {}) | {
            "reason_code": reason_code
        }

    @staticmethod
    def _build_transport_error_response(exc):
        message = str(exc).strip() or "안내 제어 명령 전송에 실패했습니다."
        return {
            "accepted": False,
            "result_code": "REJECTED",
            "result_message": message,
            "reason_code": "GUIDE_COMMAND_TRANSPORT_ERROR",
            "message": message,
        }

    def _resolve_pinky_id(self, pinky_id):
        return str(pinky_id or self.default_pinky_id).strip() or self.default_pinky_id

    @staticmethod
    def _normalize_positive_id(value):
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            return None
        if numeric <= 0:
            return None
        return numeric


__all__ = ["GuideCommandLifecycleService"]
