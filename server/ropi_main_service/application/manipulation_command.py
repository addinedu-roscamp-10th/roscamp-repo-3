import asyncio

from server.ropi_main_service.application.command_execution import (
    CommandExecutionRecorder,
    CommandExecutionSpec,
)
from server.ropi_main_service.application.delivery_config import (
    DEFAULT_DELIVERY_ROBOT_SLOT_ID,
    get_delivery_runtime_config,
)
from server.ropi_main_service.ipc.uds_client import UnixDomainSocketCommandClient


FIXED_PHASE1_ROBOT_SLOT_ID = DEFAULT_DELIVERY_ROBOT_SLOT_ID
ALLOWED_TRANSFER_DIRECTIONS = {
    "TO_ROBOT",
    "FROM_ROBOT",
}
DEFAULT_COMMAND_TIMEOUT_SEC = 30.0


class ManipulationCommandService:
    def __init__(
        self,
        command_client=None,
        runtime_config=None,
        command_execution_recorder=None,
        command_timeout_sec=DEFAULT_COMMAND_TIMEOUT_SEC,
    ):
        self.command_client = command_client or UnixDomainSocketCommandClient()
        self.runtime_config = runtime_config or get_delivery_runtime_config()
        self.command_execution_recorder = command_execution_recorder or CommandExecutionRecorder()
        self.command_timeout_sec = float(command_timeout_sec)

    def execute(
        self,
        *,
        arm_id,
        task_id,
        transfer_direction,
        item_id,
        quantity,
        robot_slot_id=None,
    ):
        command, payload, timeout = self._build_manipulation_command(
            arm_id=arm_id,
            task_id=task_id,
            transfer_direction=transfer_direction,
            item_id=item_id,
            quantity=quantity,
            robot_slot_id=robot_slot_id,
        )

        return self.command_execution_recorder.record(
            self._build_command_execution_spec(
                arm_id=arm_id,
                task_id=task_id,
                transfer_direction=transfer_direction,
                payload=payload,
            ),
            lambda: self.command_client.send_command(
                command,
                payload,
                timeout=timeout,
            ),
        )

    async def async_execute(
        self,
        *,
        arm_id,
        task_id,
        transfer_direction,
        item_id,
        quantity,
        robot_slot_id=None,
    ):
        command, payload, timeout = self._build_manipulation_command(
            arm_id=arm_id,
            task_id=task_id,
            transfer_direction=transfer_direction,
            item_id=item_id,
            quantity=quantity,
            robot_slot_id=robot_slot_id,
        )
        async_send_command = getattr(self.command_client, "async_send_command", None)
        spec = self._build_command_execution_spec(
            arm_id=arm_id,
            task_id=task_id,
            transfer_direction=transfer_direction,
            payload=payload,
        )

        if async_send_command is not None:
            async def _send_async_command():
                return await async_send_command(command, payload, timeout=timeout)

            return await self.command_execution_recorder.async_record(spec, _send_async_command)

        async def _send_sync_command_in_thread():
            return await asyncio.to_thread(
                self.command_client.send_command,
                command,
                payload,
                timeout=timeout,
            )

        return await self.command_execution_recorder.async_record(spec, _send_sync_command_in_thread)

    def _build_manipulation_command(
        self,
        *,
        arm_id,
        task_id,
        transfer_direction,
        item_id,
        quantity,
        robot_slot_id=None,
    ):
        robot_slot_id = robot_slot_id or self.runtime_config.robot_slot_id
        self._validate_request(
            arm_id=arm_id,
            task_id=task_id,
            transfer_direction=transfer_direction,
            item_id=item_id,
            quantity=quantity,
            robot_slot_id=robot_slot_id,
        )

        goal = {
            "task_id": str(task_id).strip(),
            "transfer_direction": str(transfer_direction).strip(),
            "item_id": str(item_id).strip(),
            "quantity": int(quantity),
            "robot_slot_id": str(robot_slot_id).strip(),
        }

        return (
            "execute_manipulation",
            {
                "arm_id": str(arm_id).strip(),
                "goal": goal,
            },
            self.command_timeout_sec,
        )

    @staticmethod
    def _build_target_endpoint(arm_id):
        return f"/ropi/arm/{arm_id}/execute_manipulation"

    def _build_command_execution_spec(self, *, arm_id, task_id, transfer_direction, payload):
        normalized_arm_id = str(arm_id).strip()
        return CommandExecutionSpec(
            task_id=str(task_id).strip(),
            transport="ROS_ACTION",
            command_type="ARM_MANIPULATION",
            command_phase=str(transfer_direction).strip(),
            target_component="ros_service",
            target_robot_id=self._resolve_target_robot_id(normalized_arm_id),
            target_endpoint=self._build_target_endpoint(normalized_arm_id),
            request_payload=payload,
        )

    def _resolve_target_robot_id(self, arm_id):
        if arm_id == self.runtime_config.pickup_arm_id:
            return self.runtime_config.pickup_arm_robot_id
        if arm_id == self.runtime_config.destination_arm_id:
            return self.runtime_config.destination_arm_robot_id
        return arm_id

    @staticmethod
    def _validate_request(*, arm_id, task_id, transfer_direction, item_id, quantity, robot_slot_id):
        if not str(arm_id or "").strip():
            raise ValueError("arm_id가 필요합니다.")

        if not str(task_id or "").strip():
            raise ValueError("task_id가 필요합니다.")

        if str(transfer_direction or "").strip() not in ALLOWED_TRANSFER_DIRECTIONS:
            raise ValueError(f"transfer_direction이 범위를 벗어났습니다: {transfer_direction}")

        if not str(item_id or "").strip():
            raise ValueError("item_id가 필요합니다.")

        if int(quantity) <= 0:
            raise ValueError("quantity는 1 이상이어야 합니다.")

        if not str(robot_slot_id or "").strip():
            raise ValueError("robot_slot_id가 필요합니다.")
