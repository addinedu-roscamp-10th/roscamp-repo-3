import asyncio

from server.ropi_main_service.application.command_execution import (
    CommandExecutionRecorder,
    CommandExecutionSpec,
)
from server.ropi_main_service.application.delivery_task_create import DeliveryTaskCreateService
from server.ropi_main_service.ipc.uds_client import (
    RosServiceCommandError,
    UnixDomainSocketCommandClient,
)
from server.ropi_main_service.persistence.repositories.task_request_repository import (
    TaskRequestRepository,
)


CANCEL_ACTION_COMMAND = "cancel_action"


class DeliveryCancelService:
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

    def cancel_delivery_task(self, task_id, action_name=None):
        invalid_response = self._validate_cancel_delivery_task_request(task_id=task_id)
        if invalid_response is not None:
            return invalid_response

        target_response = self.repository.get_delivery_task_cancel_target(task_id)
        if target_response.get("result_code") != self.ACCEPTED:
            return target_response

        try:
            cancel_response = self._send_cancel_action(
                task_id=task_id,
                action_name=action_name,
                assigned_robot_id=target_response.get("assigned_robot_id"),
            )
        except RosServiceCommandError as exc:
            cancel_response = self._rejected(
                f"ROS service cancel 요청에 실패했습니다: {exc}",
                "ROS_SERVICE_UNAVAILABLE",
            )
            cancel_response["cancel_requested"] = False

        return self.repository.record_delivery_task_cancel_result(
            task_id=task_id,
            cancel_response=cancel_response,
        )

    async def async_cancel_delivery_task(self, task_id, action_name=None):
        invalid_response = self._validate_cancel_delivery_task_request(task_id=task_id)
        if invalid_response is not None:
            return invalid_response

        async_cancel_target = getattr(
            self.repository,
            "async_get_delivery_task_cancel_target",
            None,
        )
        if async_cancel_target is not None:
            target_response = await async_cancel_target(task_id)
        else:
            target_response = await asyncio.to_thread(
                self.repository.get_delivery_task_cancel_target,
                task_id,
            )
        if target_response.get("result_code") != self.ACCEPTED:
            return target_response

        try:
            cancel_response = await self._async_send_cancel_action(
                task_id=task_id,
                action_name=action_name,
                assigned_robot_id=target_response.get("assigned_robot_id"),
            )
        except RosServiceCommandError as exc:
            cancel_response = self._rejected(
                f"ROS service cancel 요청에 실패했습니다: {exc}",
                "ROS_SERVICE_UNAVAILABLE",
            )
            cancel_response["cancel_requested"] = False

        async_record_cancel_result = getattr(
            self.repository,
            "async_record_delivery_task_cancel_result",
            None,
        )
        if async_record_cancel_result is not None:
            return await async_record_cancel_result(
                task_id=task_id,
                cancel_response=cancel_response,
            )

        return await asyncio.to_thread(
            self.repository.record_delivery_task_cancel_result,
            task_id=task_id,
            cancel_response=cancel_response,
        )

    def _send_cancel_action(self, *, task_id, action_name=None, assigned_robot_id=None):
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

    async def _async_send_cancel_action(self, *, task_id, action_name=None, assigned_robot_id=None):
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

    def _validate_cancel_delivery_task_request(self, *, task_id):
        if not str(task_id or "").strip():
            return self._invalid_request("task_id가 필요합니다.", "TASK_ID_INVALID")

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
    def build_cancel_command_execution_spec(
        *,
        task_id,
        action_name=None,
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
    def _invalid_request(message: str, reason_code: str):
        return DeliveryTaskCreateService._invalid_request(message, reason_code)

    @staticmethod
    def _rejected(message: str, reason_code: str):
        return DeliveryTaskCreateService._rejected(message, reason_code)


__all__ = ["CANCEL_ACTION_COMMAND", "DeliveryCancelService"]
