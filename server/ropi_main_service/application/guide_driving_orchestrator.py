from server.ropi_main_service.application.goal_pose_navigation import (
    GoalPoseNavigationService,
)
from server.ropi_main_service.application.guide_command_lifecycle import (
    GuideCommandLifecycleService,
)
from server.ropi_main_service.application.guide_runtime import DEFAULT_GUIDE_PINKY_ID
from server.ropi_main_service.persistence.repositories.guide_task_lifecycle_repository import (
    GuideTaskLifecycleRepository,
)
from server.ropi_main_service.persistence.repositories.guide_task_navigation_repository import (
    GuideTaskNavigationRepository,
)


DEFAULT_GUIDE_NAVIGATION_TIMEOUT_SEC = 120.0
GUIDE_DESTINATION_NAV_PHASE = "GUIDE_DESTINATION"
START_GUIDANCE_COMMAND = "START_GUIDANCE"


class GuideDrivingOrchestrator:
    def __init__(
        self,
        *,
        guide_task_navigation_repository=None,
        guide_task_lifecycle_repository=None,
        guide_command_lifecycle_service=None,
        goal_pose_navigation_service=None,
        guide_navigation_starter=None,
        guide_navigation_timeout_sec=DEFAULT_GUIDE_NAVIGATION_TIMEOUT_SEC,
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
        self.goal_pose_navigation_service = (
            goal_pose_navigation_service or GoalPoseNavigationService()
        )
        self.guide_navigation_starter = guide_navigation_starter
        self.guide_navigation_timeout_sec = float(guide_navigation_timeout_sec)
        self.default_pinky_id = str(default_pinky_id).strip() or DEFAULT_GUIDE_PINKY_ID

    def start_guide_driving(
        self,
        *,
        task_id,
        target_track_id,
        pinky_id=None,
        navigation_timeout_sec=None,
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
        navigation_timeout_sec=None,
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

    def _start_guide_destination_navigation(
        self,
        *,
        task_id,
        pinky_id,
        goal_pose,
        timeout_sec,
    ):
        timeout = self._normalize_navigation_timeout(timeout_sec)
        if self.guide_navigation_starter is not None:
            return self.guide_navigation_starter(
                task_id=task_id,
                pinky_id=pinky_id,
                goal_pose=goal_pose,
                timeout_sec=timeout,
            )

        return self.goal_pose_navigation_service.navigate(
            task_id=task_id,
            pinky_id=pinky_id,
            nav_phase=GUIDE_DESTINATION_NAV_PHASE,
            goal_pose=goal_pose,
            timeout_sec=timeout,
        )

    async def _async_start_guide_destination_navigation(
        self,
        *,
        task_id,
        pinky_id,
        goal_pose,
        timeout_sec,
    ):
        timeout = self._normalize_navigation_timeout(timeout_sec)
        if self.guide_navigation_starter is not None:
            result = self.guide_navigation_starter(
                task_id=task_id,
                pinky_id=pinky_id,
                goal_pose=goal_pose,
                timeout_sec=timeout,
            )
            if hasattr(result, "__await__"):
                return await result
            return result

        return await self.goal_pose_navigation_service.async_navigate(
            task_id=task_id,
            pinky_id=pinky_id,
            nav_phase=GUIDE_DESTINATION_NAV_PHASE,
            goal_pose=goal_pose,
            timeout_sec=timeout,
        )

    def _normalize_navigation_timeout(self, timeout_sec):
        if timeout_sec is None:
            return self.guide_navigation_timeout_sec
        return float(timeout_sec)

    @staticmethod
    def _navigation_dispatch_accepted(navigation_response):
        result_code = str((navigation_response or {}).get("result_code") or "")
        return result_code.strip().upper() in {"ACCEPTED", "SUCCESS"}

    @staticmethod
    def _build_guide_navigation_transport_error_response(exc):
        message = str(exc).strip() or "안내 목적지 이동 시작에 실패했습니다."
        return {
            "result_code": "REJECTED",
            "result_message": message,
            "reason_code": "GUIDE_DESTINATION_NAVIGATION_TRANSPORT_ERROR",
        }

    def _resolve_guide_driving_pinky_id(self, pinky_id, context):
        return (
            str(
                pinky_id or context.get("assigned_robot_id") or self.default_pinky_id
            ).strip()
            or self.default_pinky_id
        )

    @staticmethod
    def _build_guide_navigation_failure_response(
        *,
        context,
        navigation_response,
        target_track_id,
        pinky_id,
    ):
        message = (navigation_response or {}).get(
            "result_message"
        ) or "안내 목적지 이동 시작이 수락되지 않았습니다."
        return {
            "result_code": (navigation_response or {}).get("result_code") or "REJECTED",
            "result_message": message,
            "reason_code": (navigation_response or {}).get("reason_code"),
            "task_id": context.get("task_id"),
            "task_type": "GUIDE",
            "task_status": context.get("task_status"),
            "phase": context.get("phase"),
            "guide_phase": context.get("guide_phase"),
            "assigned_robot_id": context.get("assigned_robot_id") or pinky_id,
            "target_track_id": target_track_id,
            "destination_id": context.get("destination_id"),
            "navigation_response": navigation_response,
            "command_response": None,
        }

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
    "DEFAULT_GUIDE_NAVIGATION_TIMEOUT_SEC",
    "GUIDE_DESTINATION_NAV_PHASE",
    "START_GUIDANCE_COMMAND",
    "GuideDrivingOrchestrator",
]
