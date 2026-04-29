import asyncio

from server.ropi_main_service.application.command_execution import (
    CommandExecutionRecorder,
    CommandExecutionSpec,
)
from server.ropi_main_service.ipc.uds_client import UnixDomainSocketCommandClient


START_FALL_ALERT = "START_FALL_ALERT"
CLEAR_AND_RESTART = "CLEAR_AND_RESTART"
CLEAR_AND_STOP = "CLEAR_AND_STOP"
FALL_RESPONSE_CONTROL_COMMAND = "fall_response_control"


class FallResponseCommandService:
    def __init__(
        self,
        *,
        command_client=None,
        command_execution_recorder=None,
        timeout_sec=5.0,
    ):
        self.command_client = command_client or UnixDomainSocketCommandClient()
        self.command_execution_recorder = (
            command_execution_recorder or CommandExecutionRecorder()
        )
        self.timeout_sec = float(timeout_sec)

    def send_clear_and_restart(self, *, task_id, robot_id=None):
        payload = self.build_clear_and_restart_payload(task_id=task_id)
        spec = self.build_command_execution_spec(
            task_id=task_id,
            robot_id=robot_id,
            command_phase="PATROL_RESUME",
            payload=payload,
        )
        return self._send_sync(spec, payload)

    async def async_send_clear_and_restart(self, *, task_id, robot_id=None):
        payload = self.build_clear_and_restart_payload(task_id=task_id)
        spec = self.build_command_execution_spec(
            task_id=task_id,
            robot_id=robot_id,
            command_phase="PATROL_RESUME",
            payload=payload,
        )
        return await self._send_async(spec, payload)

    async def async_send_start_fall_alert(self, *, task_id, robot_id):
        payload = self.build_start_fall_alert_payload(
            task_id=task_id,
            robot_id=robot_id,
        )
        spec = self.build_command_execution_spec(
            task_id=task_id,
            robot_id=robot_id,
            command_phase="FALL_ALERT_START",
            payload=payload,
        )
        return await self._send_async(spec, payload)

    @staticmethod
    def build_clear_and_restart_payload(*, task_id):
        return {
            "task_id": str(task_id).strip(),
            "command_type": CLEAR_AND_RESTART,
        }

    @staticmethod
    def build_start_fall_alert_payload(*, task_id, robot_id):
        return {
            "pinky_id": str(robot_id or "").strip(),
            "task_id": str(task_id).strip(),
            "command_type": START_FALL_ALERT,
        }

    @staticmethod
    def build_command_execution_spec(
        *,
        task_id,
        robot_id=None,
        command_phase,
        payload,
    ):
        target_robot_id = str(robot_id or "").strip() or None
        return CommandExecutionSpec(
            task_id=str(task_id).strip(),
            transport="ROS_SERVICE",
            command_type="FALL_RESPONSE_CONTROL",
            command_phase=command_phase,
            target_component="ros_service",
            target_robot_id=target_robot_id,
            target_endpoint=build_fall_response_endpoint(target_robot_id),
            request_payload=payload,
        )

    @staticmethod
    def is_accepted(response):
        return isinstance(response, dict) and bool(response.get("accepted"))

    def _send_sync(self, spec, payload):
        return self.command_execution_recorder.record(
            spec,
            lambda: self.command_client.send_command(
                FALL_RESPONSE_CONTROL_COMMAND,
                payload,
                timeout=self.timeout_sec,
            ),
        )

    async def _send_async(self, spec, payload):
        async def _run_command():
            async_send_command = getattr(self.command_client, "async_send_command", None)
            if async_send_command is not None:
                return await async_send_command(
                    FALL_RESPONSE_CONTROL_COMMAND,
                    payload,
                    timeout=self.timeout_sec,
                )
            return await asyncio.to_thread(
                self.command_client.send_command,
                FALL_RESPONSE_CONTROL_COMMAND,
                payload,
                timeout=self.timeout_sec,
            )

        return await self.command_execution_recorder.async_record(spec, _run_command)


def build_fall_response_endpoint(robot_id):
    target_robot_id = str(robot_id or "").strip()
    if target_robot_id:
        return f"/ropi/control/{target_robot_id}/fall_response_control"
    return FALL_RESPONSE_CONTROL_COMMAND


__all__ = [
    "CLEAR_AND_RESTART",
    "CLEAR_AND_STOP",
    "FALL_RESPONSE_CONTROL_COMMAND",
    "FallResponseCommandService",
    "START_FALL_ALERT",
    "build_fall_response_endpoint",
]
