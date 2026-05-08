import asyncio

from server.ropi_main_service.application.command_execution import (
    CommandExecutionRecorder,
    CommandExecutionSpec,
)
from server.ropi_main_service.ipc.uds_client import UnixDomainSocketCommandClient


GUIDE_COMMAND = "guide_command"


class GuideCommandService:
    def __init__(
        self,
        *,
        command_client=None,
        command_execution_recorder=None,
        timeout_sec=None,
    ):
        self.command_client = command_client or UnixDomainSocketCommandClient()
        self.command_execution_recorder = (
            command_execution_recorder or CommandExecutionRecorder()
        )
        self.timeout_sec = None if timeout_sec is None else float(timeout_sec)

    def send(
        self,
        *,
        task_id,
        pinky_id,
        command_type,
        target_track_id=-1,
        destination_id="",
        destination_pose=None,
    ):
        payload = self.build_payload(
            task_id=task_id,
            pinky_id=pinky_id,
            command_type=command_type,
            target_track_id=target_track_id,
            destination_id=destination_id,
            destination_pose=destination_pose,
        )
        spec = self.build_command_execution_spec(task_id=task_id, pinky_id=pinky_id, payload=payload)
        return self.command_execution_recorder.record(
            spec,
            lambda: self.command_client.send_command(
                GUIDE_COMMAND,
                payload,
                timeout=self.timeout_sec,
            ),
        )

    async def async_send(
        self,
        *,
        task_id,
        pinky_id,
        command_type,
        target_track_id=-1,
        destination_id="",
        destination_pose=None,
    ):
        payload = self.build_payload(
            task_id=task_id,
            pinky_id=pinky_id,
            command_type=command_type,
            target_track_id=target_track_id,
            destination_id=destination_id,
            destination_pose=destination_pose,
        )
        spec = self.build_command_execution_spec(task_id=task_id, pinky_id=pinky_id, payload=payload)
        async_send_command = getattr(self.command_client, "async_send_command", None)

        if async_send_command is not None:
            async def _run_command():
                return await async_send_command(
                    GUIDE_COMMAND,
                    payload,
                    timeout=self.timeout_sec,
                )

            return await self.command_execution_recorder.async_record(spec, _run_command)

        async def _run_sync_in_thread():
            return await asyncio.to_thread(
                self.command_client.send_command,
                GUIDE_COMMAND,
                payload,
                timeout=self.timeout_sec,
            )

        return await self.command_execution_recorder.async_record(spec, _run_sync_in_thread)

    @staticmethod
    def build_payload(
        *,
        task_id,
        pinky_id,
        command_type,
        target_track_id=-1,
        destination_id="",
        destination_pose=None,
    ):
        return {
            "pinky_id": str(pinky_id or "").strip(),
            "task_id": str(task_id or "").strip(),
            "command_type": str(command_type or "").strip(),
            "target_track_id": GuideCommandService._normalize_target_track_id(
                target_track_id
            ),
            "destination_id": str(destination_id or "").strip(),
            "destination_pose": destination_pose or {},
        }

    @staticmethod
    def _normalize_target_track_id(value):
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return -1

    @staticmethod
    def build_command_execution_spec(*, task_id, pinky_id, payload):
        target_pinky_id = str(pinky_id or "").strip() or None
        return CommandExecutionSpec(
            task_id=str(task_id).strip(),
            transport="ROS_SERVICE",
            command_type="GUIDE_COMMAND",
            command_phase="GUIDE_SESSION_CONTROL",
            target_component="ros_service",
            target_robot_id=target_pinky_id,
            target_endpoint=build_guide_command_endpoint(target_pinky_id),
            request_payload=payload,
        )


def build_guide_command_endpoint(pinky_id):
    target_pinky_id = str(pinky_id or "").strip()
    if target_pinky_id:
        return f"/ropi/control/{target_pinky_id}/guide_command"
    return GUIDE_COMMAND


__all__ = ["GUIDE_COMMAND", "GuideCommandService", "build_guide_command_endpoint"]
