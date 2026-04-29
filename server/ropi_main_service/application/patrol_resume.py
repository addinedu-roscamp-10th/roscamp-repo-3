import asyncio

from server.ropi_main_service.application.fall_response_command import (
    FallResponseCommandService,
)
from server.ropi_main_service.ipc.uds_client import RosServiceCommandError
from server.ropi_main_service.persistence.repositories.task_request_repository import (
    TaskRequestRepository,
)


class PatrolResumeService:
    ACCEPTED = "ACCEPTED"

    def __init__(
        self,
        *,
        repository=None,
        command_client=None,
        command_execution_recorder=None,
        fall_response_command_service=None,
        timeout_sec=5.0,
    ):
        self.repository = repository or TaskRequestRepository()
        self.fall_response_command_service = (
            fall_response_command_service
            or FallResponseCommandService(
                command_client=command_client,
                command_execution_recorder=command_execution_recorder,
                timeout_sec=timeout_sec,
            )
        )

    def resume_patrol_task(self, task_id, caregiver_id, member_id, action_memo):
        validated = self._validate_resume_patrol_task_request(
            task_id=task_id,
            caregiver_id=caregiver_id,
            member_id=member_id,
            action_memo=action_memo,
        )
        if validated["error_response"] is not None:
            return validated["error_response"]

        target_response = self.repository.get_patrol_task_resume_target(task_id)
        if target_response.get("result_code") != self.ACCEPTED:
            return target_response

        try:
            resume_command_response = (
                self.fall_response_command_service.send_clear_and_restart(
                    task_id=task_id,
                    robot_id=target_response.get("assigned_robot_id"),
                )
            )
        except RosServiceCommandError as exc:
            return self.build_patrol_resume_response(
                result_code="NOT_ALLOWED",
                result_message=f"ROS service 순찰 재개 요청에 실패했습니다: {exc}",
                reason_code="ROS_SERVICE_UNAVAILABLE",
                task_id=target_response.get("task_id"),
                task_status=target_response.get("task_status"),
                phase=target_response.get("phase"),
                assigned_robot_id=target_response.get("assigned_robot_id"),
                cancellable=False,
            )

        rejected_response = self._build_command_rejected_response(
            target_response=target_response,
            resume_command_response=resume_command_response,
        )
        if rejected_response is not None:
            return rejected_response

        return self.repository.record_patrol_task_resume_result(
            task_id=task_id,
            caregiver_id=validated["caregiver_id"],
            member_id=validated["member_id"],
            action_memo=validated["action_memo"],
            resume_command_response=resume_command_response,
        )

    async def async_resume_patrol_task(self, task_id, caregiver_id, member_id, action_memo):
        validated = self._validate_resume_patrol_task_request(
            task_id=task_id,
            caregiver_id=caregiver_id,
            member_id=member_id,
            action_memo=action_memo,
        )
        if validated["error_response"] is not None:
            return validated["error_response"]

        async_get_target = getattr(self.repository, "async_get_patrol_task_resume_target", None)
        if async_get_target is not None:
            target_response = await async_get_target(task_id)
        else:
            target_response = await asyncio.to_thread(
                self.repository.get_patrol_task_resume_target,
                task_id,
            )
        if target_response.get("result_code") != self.ACCEPTED:
            return target_response

        try:
            resume_command_response = await (
                self.fall_response_command_service.async_send_clear_and_restart(
                    task_id=task_id,
                    robot_id=target_response.get("assigned_robot_id"),
                )
            )
        except RosServiceCommandError as exc:
            return self.build_patrol_resume_response(
                result_code="NOT_ALLOWED",
                result_message=f"ROS service 순찰 재개 요청에 실패했습니다: {exc}",
                reason_code="ROS_SERVICE_UNAVAILABLE",
                task_id=target_response.get("task_id"),
                task_status=target_response.get("task_status"),
                phase=target_response.get("phase"),
                assigned_robot_id=target_response.get("assigned_robot_id"),
                cancellable=False,
            )

        rejected_response = self._build_command_rejected_response(
            target_response=target_response,
            resume_command_response=resume_command_response,
        )
        if rejected_response is not None:
            return rejected_response

        async_record_resume = getattr(
            self.repository,
            "async_record_patrol_task_resume_result",
            None,
        )
        if async_record_resume is not None:
            return await async_record_resume(
                task_id=task_id,
                caregiver_id=validated["caregiver_id"],
                member_id=validated["member_id"],
                action_memo=validated["action_memo"],
                resume_command_response=resume_command_response,
            )

        return await asyncio.to_thread(
            self.repository.record_patrol_task_resume_result,
            task_id=task_id,
            caregiver_id=validated["caregiver_id"],
            member_id=validated["member_id"],
            action_memo=validated["action_memo"],
            resume_command_response=resume_command_response,
        )

    def _validate_resume_patrol_task_request(
        self,
        *,
        task_id,
        caregiver_id,
        member_id,
        action_memo,
    ):
        task_id_text = str(task_id or "").strip()
        if not task_id_text:
            return {
                "error_response": self.build_patrol_resume_response(
                    result_code="NOT_ALLOWED",
                    result_message="순찰 task_id가 필요합니다.",
                    reason_code="TASK_ID_REQUIRED",
                    task_id=task_id,
                    cancellable=False,
                )
            }

        numeric_caregiver_id = self._optional_int(caregiver_id)
        if numeric_caregiver_id is None:
            return {
                "error_response": self.build_patrol_resume_response(
                    result_code="NOT_ALLOWED",
                    result_message="요청자 caregiver_id가 필요합니다.",
                    reason_code="CAREGIVER_ID_REQUIRED",
                    task_id=task_id,
                    cancellable=False,
                )
            }

        numeric_member_id = self._optional_int(member_id)
        if numeric_member_id is None:
            return {
                "error_response": self.build_patrol_resume_response(
                    result_code="NOT_ALLOWED",
                    result_message="어르신 member_id가 필요합니다.",
                    reason_code="MEMBER_ID_REQUIRED",
                    task_id=task_id,
                    cancellable=False,
                )
            }

        memo = str(action_memo or "").strip()
        if not memo:
            return {
                "error_response": self.build_patrol_resume_response(
                    result_code="NOT_ALLOWED",
                    result_message="현장 조치 메모를 입력하세요.",
                    reason_code="ACTION_MEMO_REQUIRED",
                    task_id=task_id,
                    cancellable=False,
                )
            }

        return {
            "error_response": None,
            "caregiver_id": numeric_caregiver_id,
            "member_id": numeric_member_id,
            "action_memo": memo,
        }

    def _build_command_rejected_response(self, *, target_response, resume_command_response):
        if FallResponseCommandService.is_accepted(resume_command_response):
            return None

        return self.build_patrol_resume_response(
            result_code="NOT_ALLOWED",
            result_message=(
                resume_command_response.get("message")
                if isinstance(resume_command_response, dict)
                else "순찰 재개 명령이 거절되었습니다."
            ),
            reason_code="PATROL_RESUME_COMMAND_REJECTED",
            task_id=target_response.get("task_id"),
            task_status=target_response.get("task_status"),
            phase=target_response.get("phase"),
            assigned_robot_id=target_response.get("assigned_robot_id"),
            cancellable=False,
        )

    @staticmethod
    def build_patrol_resume_response(
        *,
        result_code,
        result_message=None,
        reason_code=None,
        task_id=None,
        task_status=None,
        phase=None,
        assigned_robot_id=None,
        cancellable=None,
    ):
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "task_id": task_id,
            "task_status": task_status,
            "phase": phase,
            "assigned_robot_id": assigned_robot_id,
            "cancellable": cancellable,
        }

    @staticmethod
    def _optional_int(value):
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


__all__ = ["PatrolResumeService"]
