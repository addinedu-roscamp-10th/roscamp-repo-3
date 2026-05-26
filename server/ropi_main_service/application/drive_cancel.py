import asyncio

from server.ropi_main_service.application.command_execution import (
    CommandExecutionRecorder,
    CommandExecutionSpec,
)
from server.ropi_main_service.ipc.uds_client import (
    RosServiceCommandError,
    UnixDomainSocketCommandClient,
)
from server.ropi_main_service.persistence.repositories.task_request_repository import (
    TaskRequestRepository,
)


CANCEL_ACTION_COMMAND = "cancel_action"
DRIVE_PRE_DISPATCH_CANCEL_MESSAGE = "DRIVE task 취소 요청이 접수되었습니다."
USER_CANCEL_REQUESTED_REASON = "USER_CANCEL_REQUESTED"


class DriveCancelService:
    ACCEPTED = "ACCEPTED"

    def __init__(
        self,
        *,
        repository=None,
        command_client=None,
        command_execution_recorder=None,
        timeout_sec=5.0,
    ):
        self.repository = repository or TaskRequestRepository()
        self.command_client = command_client or UnixDomainSocketCommandClient()
        self.command_execution_recorder = (
            command_execution_recorder or CommandExecutionRecorder()
        )
        self.timeout_sec = float(timeout_sec)

    def cancel_drive_task(
        self,
        *,
        task_id,
        caregiver_id,
        reason,
        action_name=None,
    ):
        invalid_response = self._validate_cancel_request(
            task_id=task_id,
            caregiver_id=caregiver_id,
            reason=reason,
        )
        if invalid_response is not None:
            return invalid_response

        target_response = self.repository.get_drive_task_cancel_target(task_id)
        if target_response.get("result_code") != self.ACCEPTED:
            return target_response

        cancel_response = self._build_cancel_response(
            task_id=task_id,
            action_name=action_name,
            target_response=target_response,
            send_cancel=self._send_cancel_action,
        )
        return self.repository.record_drive_task_cancel_result(
            task_id=task_id,
            caregiver_id=caregiver_id,
            reason=reason,
            cancel_response=cancel_response,
        )

    async def async_cancel_drive_task(
        self,
        *,
        task_id,
        caregiver_id,
        reason,
        action_name=None,
    ):
        invalid_response = self._validate_cancel_request(
            task_id=task_id,
            caregiver_id=caregiver_id,
            reason=reason,
        )
        if invalid_response is not None:
            return invalid_response

        async_cancel_target = getattr(
            self.repository,
            "async_get_drive_task_cancel_target",
            None,
        )
        if async_cancel_target is not None:
            target_response = await async_cancel_target(task_id)
        else:
            target_response = await asyncio.to_thread(
                self.repository.get_drive_task_cancel_target,
                task_id,
            )
        if target_response.get("result_code") != self.ACCEPTED:
            return target_response

        cancel_response = await self._async_build_cancel_response(
            task_id=task_id,
            action_name=action_name,
            target_response=target_response,
        )
        async_record_cancel_result = getattr(
            self.repository,
            "async_record_drive_task_cancel_result",
            None,
        )
        if async_record_cancel_result is not None:
            return await async_record_cancel_result(
                task_id=task_id,
                caregiver_id=caregiver_id,
                reason=reason,
                cancel_response=cancel_response,
            )

        return await asyncio.to_thread(
            self.repository.record_drive_task_cancel_result,
            task_id=task_id,
            caregiver_id=caregiver_id,
            reason=reason,
            cancel_response=cancel_response,
        )

    def _build_cancel_response(
        self,
        *,
        task_id,
        action_name,
        target_response,
        send_cancel,
    ):
        assigned_robot_id = target_response.get("assigned_robot_id")
        effective_action_name = self._effective_action_name(
            action_name=action_name,
            assigned_robot_id=assigned_robot_id,
        )
        if not self._has_active_nav2_goal(target_response):
            return self.build_pre_dispatch_cancel_response(
                task_id=task_id,
                action_name=action_name,
            )

        try:
            return send_cancel(
                task_id=task_id,
                action_name=effective_action_name,
                assigned_robot_id=assigned_robot_id,
            )
        except RosServiceCommandError as exc:
            response = self._rejected(
                f"ROS service cancel 요청에 실패했습니다: {exc}",
                "ROS_SERVICE_UNAVAILABLE",
            )
            response["cancel_requested"] = False
            return response

    async def _async_build_cancel_response(
        self,
        *,
        task_id,
        action_name,
        target_response,
    ):
        assigned_robot_id = target_response.get("assigned_robot_id")
        effective_action_name = self._effective_action_name(
            action_name=action_name,
            assigned_robot_id=assigned_robot_id,
        )
        if not self._has_active_nav2_goal(target_response):
            return self.build_pre_dispatch_cancel_response(
                task_id=task_id,
                action_name=action_name,
            )

        try:
            return await self._async_send_cancel_action(
                task_id=task_id,
                action_name=effective_action_name,
                assigned_robot_id=assigned_robot_id,
            )
        except RosServiceCommandError as exc:
            response = self._rejected(
                f"ROS service cancel 요청에 실패했습니다: {exc}",
                "ROS_SERVICE_UNAVAILABLE",
            )
            response["cancel_requested"] = False
            return response

    def _send_cancel_action(self, *, task_id, action_name, assigned_robot_id=None):
        payload = self.build_cancel_action_payload(
            task_id=task_id,
            action_name=action_name,
        )
        spec = self.build_cancel_command_execution_spec(
            task_id=task_id,
            action_name=action_name,
            assigned_robot_id=assigned_robot_id,
            payload=payload,
        )
        return self.command_execution_recorder.record(
            spec,
            lambda: self.command_client.send_command(
                CANCEL_ACTION_COMMAND,
                payload,
                timeout=self.timeout_sec,
            ),
        )

    async def _async_send_cancel_action(
        self,
        *,
        task_id,
        action_name,
        assigned_robot_id=None,
    ):
        payload = self.build_cancel_action_payload(
            task_id=task_id,
            action_name=action_name,
        )
        spec = self.build_cancel_command_execution_spec(
            task_id=task_id,
            action_name=action_name,
            assigned_robot_id=assigned_robot_id,
            payload=payload,
        )
        async_send_command = getattr(self.command_client, "async_send_command", None)

        if async_send_command is not None:
            async def _send_async_cancel_command():
                return await async_send_command(
                    CANCEL_ACTION_COMMAND,
                    payload,
                    timeout=self.timeout_sec,
                )

            return await self.command_execution_recorder.async_record(
                spec,
                _send_async_cancel_command,
            )

        async def _send_sync_cancel_command_in_thread():
            return await asyncio.to_thread(
                self.command_client.send_command,
                CANCEL_ACTION_COMMAND,
                payload,
                timeout=self.timeout_sec,
            )

        return await self.command_execution_recorder.async_record(
            spec,
            _send_sync_cancel_command_in_thread,
        )

    @staticmethod
    def _validate_cancel_request(*, task_id, caregiver_id, reason):
        if not str(task_id or "").strip():
            return DriveCancelService._invalid_request(
                "task_id가 필요합니다.",
                "TASK_ID_INVALID",
            )
        if not str(caregiver_id or "").strip():
            return DriveCancelService._invalid_request(
                "caregiver_id가 필요합니다.",
                "CAREGIVER_ID_INVALID",
            )
        if not str(reason or "").strip():
            return DriveCancelService._invalid_request(
                "취소 사유가 필요합니다.",
                "CANCEL_REASON_REQUIRED",
            )
        return None

    @staticmethod
    def build_cancel_action_payload(*, task_id, action_name=None):
        payload = {
            "task_id": str(task_id).strip(),
        }
        normalized_action_name = str(action_name or "").strip()
        if normalized_action_name:
            payload["action_name"] = normalized_action_name
        return payload

    @staticmethod
    def build_pre_dispatch_cancel_response(*, task_id, action_name=None):
        return {
            "result_code": "CANCEL_REQUESTED",
            "result_message": DRIVE_PRE_DISPATCH_CANCEL_MESSAGE,
            "task_id": str(task_id).strip(),
            "action_name": action_name,
            "cancel_requested": True,
            "reason_code": USER_CANCEL_REQUESTED_REASON,
        }

    @staticmethod
    def build_cancel_command_execution_spec(
        *,
        task_id,
        action_name,
        assigned_robot_id=None,
        payload,
    ):
        normalized_action_name = str(action_name or "").strip()
        return CommandExecutionSpec(
            task_id=str(task_id).strip(),
            transport="ROS_ACTION",
            command_type="CANCEL_ACTION",
            command_phase="CANCEL",
            target_component="ros_service",
            target_robot_id=str(assigned_robot_id or "").strip() or None,
            target_endpoint=normalized_action_name or "active_action_for_task",
            request_payload=payload,
        )

    @staticmethod
    def _effective_action_name(*, action_name=None, assigned_robot_id=None):
        normalized_action_name = str(action_name or "").strip()
        if normalized_action_name:
            return normalized_action_name

        robot_id = str(assigned_robot_id or "").strip().strip("/")
        if not robot_id:
            return None
        return f"/{robot_id}/navigate_to_pose"

    @staticmethod
    def _has_active_nav2_goal(target_response):
        task_status = str(target_response.get("task_status") or "").strip().upper()
        return task_status == "RUNNING"

    @staticmethod
    def _invalid_request(message: str, reason_code: str):
        return {
            "result_code": "INVALID_REQUEST",
            "result_message": message,
            "reason_code": reason_code,
            "task_id": None,
            "task_type": "DRIVE",
            "task_status": None,
            "phase": None,
            "assigned_robot_id": None,
            "cancellable": False,
            "cancel_requested": False,
        }

    @staticmethod
    def _rejected(message: str, reason_code: str):
        return {
            "result_code": "REJECTED",
            "result_message": message,
            "reason_code": reason_code,
            "task_type": "DRIVE",
        }


__all__ = ["DriveCancelService", "CANCEL_ACTION_COMMAND"]
