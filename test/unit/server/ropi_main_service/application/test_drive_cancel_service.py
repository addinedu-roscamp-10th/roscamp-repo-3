import asyncio

from server.ropi_main_service.application.delivery_cancel import CANCEL_ACTION_COMMAND
from server.ropi_main_service.application.drive_cancel import DriveCancelService


class FakeCancelCommandClient:
    def __init__(self):
        self.calls = []

    async def async_send_command(self, command, payload, timeout=None):
        self.calls.append(
            {
                "command": command,
                "payload": payload,
                "timeout": timeout,
            }
        )
        return {
            "result_code": "CANCEL_REQUESTED",
            "result_message": "action cancel request was accepted.",
            "task_id": payload["task_id"],
            "action_name": payload.get("action_name"),
            "cancel_requested": True,
        }


class FakeCancelRepository:
    def __init__(self, target):
        self.target = target
        self.precheck_calls = []
        self.record_calls = []

    async def async_get_drive_task_cancel_target(self, task_id):
        self.precheck_calls.append(task_id)
        return {
            "result_code": "ACCEPTED",
            "task_id": int(task_id),
            "task_type": "DRIVE",
            "assigned_robot_id": "pinky3",
            **self.target,
        }

    async def async_record_drive_task_cancel_result(
        self,
        *,
        task_id,
        caregiver_id,
        reason,
        cancel_response,
    ):
        self.record_calls.append(
            {
                "task_id": task_id,
                "caregiver_id": caregiver_id,
                "reason": reason,
                "cancel_response": cancel_response,
            }
        )
        return {
            "result_code": "CANCEL_REQUESTED",
            "task_id": int(task_id),
            "task_type": "DRIVE",
            "task_status": "CANCEL_REQUESTED",
            "phase": "CANCEL_REQUESTED",
            "assigned_robot_id": "pinky3",
            "cancel_requested": True,
        }


class RecordingCommandExecutionRecorder:
    def __init__(self):
        self.specs = []

    async def async_record(self, spec, command_runner):
        self.specs.append(spec)
        return await command_runner()


def test_drive_cancel_service_targets_namespaced_nav2_action_when_running():
    command_client = FakeCancelCommandClient()
    repository = FakeCancelRepository(
        {
            "task_status": "RUNNING",
            "phase": "FOLLOW_DRIVE_ROUTE",
        }
    )
    recorder = RecordingCommandExecutionRecorder()
    service = DriveCancelService(
        repository=repository,
        command_client=command_client,
        command_execution_recorder=recorder,
        timeout_sec=4.0,
    )

    response = asyncio.run(
        service.async_cancel_drive_task(
            task_id="3001",
            caregiver_id=7,
            reason="operator_cancel",
        )
    )

    assert response["result_code"] == "CANCEL_REQUESTED"
    assert command_client.calls == [
        {
            "command": CANCEL_ACTION_COMMAND,
            "payload": {
                "task_id": "3001",
                "action_name": "/pinky3/navigate_to_pose",
            },
            "timeout": 4.0,
        }
    ]
    assert recorder.specs[0].target_robot_id == "pinky3"
    assert recorder.specs[0].target_endpoint == "/pinky3/navigate_to_pose"
    assert repository.record_calls[0]["cancel_response"]["cancel_requested"] is True


def test_drive_cancel_service_skips_ros_cancel_before_nav2_dispatch():
    command_client = FakeCancelCommandClient()
    repository = FakeCancelRepository(
        {
            "task_status": "WAITING_DISPATCH",
            "phase": "WAITING_FMS_RESERVATION",
        }
    )
    recorder = RecordingCommandExecutionRecorder()
    service = DriveCancelService(
        repository=repository,
        command_client=command_client,
        command_execution_recorder=recorder,
        timeout_sec=4.0,
    )

    response = asyncio.run(
        service.async_cancel_drive_task(
            task_id="3001",
            caregiver_id=7,
            reason="operator_cancel",
        )
    )

    assert response["result_code"] == "CANCEL_REQUESTED"
    assert command_client.calls == []
    assert recorder.specs == []
    assert repository.record_calls[0]["cancel_response"] == {
        "result_code": "CANCEL_REQUESTED",
        "result_message": "DRIVE task 취소 요청이 접수되었습니다.",
        "task_id": "3001",
        "action_name": None,
        "cancel_requested": True,
        "reason_code": "USER_CANCEL_REQUESTED",
    }
