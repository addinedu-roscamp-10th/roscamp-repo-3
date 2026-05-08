from server.ropi_main_service.application.guide_command_lifecycle import (
    GuideCommandLifecycleService,
)
from server.ropi_main_service.application.guide_command_runtime_preflight import (
    GuideCommandRuntimePreflight,
)
from server.ropi_main_service.application.guide_runtime import DEFAULT_GUIDE_PINKY_ID
from server.ropi_main_service.persistence.repositories.guide_task_lifecycle_repository import (
    GuideTaskLifecycleRepository,
)
from server.ropi_main_service.persistence.repositories.guide_task_navigation_repository import (
    GuideTaskNavigationRepository,
)


START_GUIDANCE_COMMAND = "START_GUIDANCE"


class GuideDrivingOrchestrator:
    def __init__(
        self,
        *,
        guide_task_navigation_repository=None,
        guide_task_lifecycle_repository=None,
        guide_command_lifecycle_service=None,
        guide_runtime_preflight=None,
        default_pinky_id=DEFAULT_GUIDE_PINKY_ID,
    ):
        self.guide_task_navigation_repository = (
            guide_task_navigation_repository or GuideTaskNavigationRepository()
        )
        self.guide_task_lifecycle_repository = (
            guide_task_lifecycle_repository or GuideTaskLifecycleRepository()
        )
        self.guide_command_lifecycle_service = (
            guide_command_lifecycle_service
            or GuideCommandLifecycleService(
                guide_task_lifecycle_repository=self.guide_task_lifecycle_repository,
                default_pinky_id=default_pinky_id,
            )
        )
        self.guide_runtime_preflight = (
            guide_runtime_preflight
            or GuideCommandRuntimePreflight(default_pinky_id=default_pinky_id)
        )
        self.default_pinky_id = str(default_pinky_id).strip() or DEFAULT_GUIDE_PINKY_ID

    def start_guide_driving(
        self,
        *,
        task_id,
        target_track_id,
        pinky_id=None,
    ):
        invalid = self._validate_start_guide_driving_request(
            task_id=task_id,
            target_track_id=target_track_id,
        )
        if invalid is not None:
            return False, invalid["result_message"], invalid

        context = self.guide_task_navigation_repository.get_guide_driving_context(
            task_id=task_id,
        )
        if context.get("result_code") != "ACCEPTED":
            target_pinky_id = self._resolve_guide_driving_pinky_id(pinky_id, context)
            response = self._record_guide_driving_start_rejection(
                response=context,
                task_id=context.get("task_id") or task_id,
                pinky_id=target_pinky_id,
                target_track_id=target_track_id,
            )
            return (
                False,
                response.get("result_message") or "안내 주행을 시작할 수 없습니다.",
                response,
            )

        target_pinky_id = self._resolve_guide_driving_pinky_id(pinky_id, context)
        preflight_response = self.guide_runtime_preflight.check(
            task_id=task_id,
            pinky_id=target_pinky_id,
        )
        if preflight_response.get("result_code") != "ACCEPTED":
            response = self._record_guide_driving_start_rejection(
                response=self._build_guide_runtime_preflight_failure_response(
                    context=context,
                    preflight_response=preflight_response,
                    target_track_id=target_track_id,
                    pinky_id=target_pinky_id,
                ),
                task_id=context.get("task_id") or task_id,
                pinky_id=target_pinky_id,
                target_track_id=target_track_id,
            )
            return (
                False,
                response.get("result_message") or "안내 주행을 시작할 수 없습니다.",
                response,
            )

        command_ok, command_message, command_response = (
            self.guide_command_lifecycle_service.send_command(
                task_id=task_id,
                pinky_id=target_pinky_id,
                command_type=START_GUIDANCE_COMMAND,
                target_track_id=target_track_id,
                destination_id=context.get("destination_id"),
                destination_pose=context.get("goal_pose"),
            )
        )
        response = self._build_guide_driving_response(
            context=context,
            command_response=command_response,
            target_track_id=target_track_id,
            pinky_id=target_pinky_id,
        )
        if not command_ok:
            return False, command_message, response

        response["result_code"] = "ACCEPTED"
        response["result_message"] = "안내 주행을 시작했습니다."
        return True, response["result_message"], response

    async def async_start_guide_driving(
        self,
        *,
        task_id,
        target_track_id,
        pinky_id=None,
    ):
        invalid = self._validate_start_guide_driving_request(
            task_id=task_id,
            target_track_id=target_track_id,
        )
        if invalid is not None:
            return False, invalid["result_message"], invalid

        context = (
            await self.guide_task_navigation_repository.async_get_guide_driving_context(
                task_id=task_id,
            )
        )
        if context.get("result_code") != "ACCEPTED":
            target_pinky_id = self._resolve_guide_driving_pinky_id(pinky_id, context)
            response = await self._async_record_guide_driving_start_rejection(
                response=context,
                task_id=context.get("task_id") or task_id,
                pinky_id=target_pinky_id,
                target_track_id=target_track_id,
            )
            return (
                False,
                response.get("result_message") or "안내 주행을 시작할 수 없습니다.",
                response,
            )

        target_pinky_id = self._resolve_guide_driving_pinky_id(pinky_id, context)
        preflight_response = await self.guide_runtime_preflight.async_check(
            task_id=task_id,
            pinky_id=target_pinky_id,
        )
        if preflight_response.get("result_code") != "ACCEPTED":
            response = await self._async_record_guide_driving_start_rejection(
                response=self._build_guide_runtime_preflight_failure_response(
                    context=context,
                    preflight_response=preflight_response,
                    target_track_id=target_track_id,
                    pinky_id=target_pinky_id,
                ),
                task_id=context.get("task_id") or task_id,
                pinky_id=target_pinky_id,
                target_track_id=target_track_id,
            )
            return (
                False,
                response.get("result_message") or "안내 주행을 시작할 수 없습니다.",
                response,
            )

        (
            command_ok,
            command_message,
            command_response,
        ) = await self.guide_command_lifecycle_service.async_send_command(
            task_id=task_id,
            pinky_id=target_pinky_id,
            command_type=START_GUIDANCE_COMMAND,
            target_track_id=target_track_id,
            destination_id=context.get("destination_id"),
            destination_pose=context.get("goal_pose"),
        )
        response = self._build_guide_driving_response(
            context=context,
            command_response=command_response,
            target_track_id=target_track_id,
            pinky_id=target_pinky_id,
        )
        if not command_ok:
            return False, command_message, response

        response["result_code"] = "ACCEPTED"
        response["result_message"] = "안내 주행을 시작했습니다."
        return True, response["result_message"], response

    def _resolve_guide_driving_pinky_id(self, pinky_id, context):
        return (
            str(
                pinky_id or context.get("assigned_robot_id") or self.default_pinky_id
            ).strip()
            or self.default_pinky_id
        )

    @staticmethod
    def _build_guide_runtime_preflight_failure_response(
        *,
        context,
        preflight_response,
        target_track_id,
        pinky_id,
    ):
        response = dict(preflight_response or {})
        response.update(
            {
                "result_code": response.get("result_code") or "REJECTED",
                "result_message": response.get("result_message")
                or "안내 주행을 시작할 수 없습니다.",
                "reason_code": response.get("reason_code") or "GUIDE_RUNTIME_NOT_READY",
                "accepted": False,
                "task_id": context.get("task_id"),
                "task_type": "GUIDE",
                "task_status": context.get("task_status"),
                "phase": context.get("phase"),
                "guide_phase": context.get("guide_phase"),
                "assigned_robot_id": context.get("assigned_robot_id") or pinky_id,
                "target_track_id": target_track_id,
                "destination_id": context.get("destination_id"),
            }
        )
        return response

    def _record_guide_driving_start_rejection(
        self,
        *,
        response,
        task_id,
        pinky_id,
        target_track_id,
    ):
        if self._normalize_positive_id(task_id) is None:
            return response

        command_response = dict(response or {})
        command_response["accepted"] = False
        lifecycle_result = self.guide_task_lifecycle_repository.record_command_result(
            task_id=task_id,
            pinky_id=pinky_id,
            command_type=START_GUIDANCE_COMMAND,
            target_track_id=target_track_id,
            wait_timeout_sec=0,
            finish_reason="",
            command_response=command_response,
        )
        return self._merge_start_guidance_rejection_lifecycle_response(
            response=response,
            lifecycle_result=lifecycle_result,
        )

    async def _async_record_guide_driving_start_rejection(
        self,
        *,
        response,
        task_id,
        pinky_id,
        target_track_id,
    ):
        if self._normalize_positive_id(task_id) is None:
            return response

        command_response = dict(response or {})
        command_response["accepted"] = False
        lifecycle_result = (
            await self.guide_task_lifecycle_repository.async_record_command_result(
                task_id=task_id,
                pinky_id=pinky_id,
                command_type=START_GUIDANCE_COMMAND,
                target_track_id=target_track_id,
                wait_timeout_sec=0,
                finish_reason="",
                command_response=command_response,
            )
        )
        return self._merge_start_guidance_rejection_lifecycle_response(
            response=response,
            lifecycle_result=lifecycle_result,
        )

    @staticmethod
    def _merge_start_guidance_rejection_lifecycle_response(
        *,
        response,
        lifecycle_result,
    ):
        merged = dict(response or {}) if isinstance(response, dict) else {}
        if not lifecycle_result:
            return merged

        merged["lifecycle_result"] = lifecycle_result
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
                merged[key] = lifecycle_result[key]
        return merged

    @staticmethod
    def _build_guide_driving_response(
        *, context, command_response, target_track_id, pinky_id
    ):
        response_target_track_id = command_response.get("target_track_id")
        if response_target_track_id is None:
            response_target_track_id = target_track_id
        response = {
            "result_code": command_response.get("result_code"),
            "result_message": command_response.get("result_message"),
            "reason_code": command_response.get("reason_code"),
            "task_id": command_response.get("task_id") or context.get("task_id"),
            "task_type": "GUIDE",
            "task_status": command_response.get("task_status")
            or context.get("task_status"),
            "phase": command_response.get("phase") or context.get("phase"),
            "guide_phase": command_response.get("guide_phase"),
            "assigned_robot_id": command_response.get("assigned_robot_id") or pinky_id,
            "target_track_id": response_target_track_id,
            "destination_id": context.get("destination_id"),
            "command_response": command_response,
        }
        return response

    @classmethod
    def _validate_start_guide_driving_request(cls, *, task_id, target_track_id):
        if cls._normalize_positive_id(task_id) is None:
            return cls._build_guide_driving_invalid_response(
                result_message="task_id를 확인할 수 없습니다.",
                reason_code="TASK_ID_INVALID",
            )
        if cls._is_blank(target_track_id):
            return cls._build_guide_driving_invalid_response(
                result_message="target_track_id가 필요합니다.",
                reason_code="TARGET_TRACK_ID_REQUIRED",
                task_id=task_id,
            )
        normalized_target_track_id = cls._normalize_non_negative_int(target_track_id)
        if normalized_target_track_id is None:
            return cls._build_guide_driving_invalid_response(
                result_message="target_track_id는 0 이상의 정수여야 합니다.",
                reason_code="TARGET_TRACK_ID_REQUIRED",
                task_id=task_id,
            )
        return None

    @staticmethod
    def _build_guide_driving_invalid_response(
        *, result_message, reason_code, task_id=None
    ):
        return {
            "result_code": "INVALID_REQUEST",
            "result_message": result_message,
            "reason_code": reason_code,
            "task_id": task_id,
            "task_type": "GUIDE",
        }

    @staticmethod
    def _normalize_positive_id(value):
        try:
            normalized = int(str(value or "").strip())
        except (TypeError, ValueError):
            return None
        if normalized <= 0:
            return None
        return normalized

    @staticmethod
    def _normalize_non_negative_int(value):
        try:
            normalized = int(str(value).strip())
        except (TypeError, ValueError):
            return None
        if normalized < 0:
            return None
        return normalized

    @staticmethod
    def _is_blank(value) -> bool:
        return not str(value or "").strip()


__all__ = [
    "START_GUIDANCE_COMMAND",
    "GuideDrivingOrchestrator",
]
