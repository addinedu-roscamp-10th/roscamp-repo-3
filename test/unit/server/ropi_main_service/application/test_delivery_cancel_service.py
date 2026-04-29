import asyncio

from server.ropi_main_service.application.delivery_cancel import (
    CANCEL_ACTION_COMMAND,
    DeliveryCancelService,
)


class FakeCancelCommandClient:
    def __init__(self, response=None):
        self.calls = []
        self.response = response or {
            "result_code": "CANCEL_REQUESTED",
            "result_message": "action cancel request was accepted.",
            "task_id": "101",
            "action_name": None,
            "cancel_requested": True,
        }

    def send_command(self, command, payload, timeout=None):
        self.calls.append(
            {
                "command": command,
                "payload": payload,
                "timeout": timeout,
                "mode": "sync",
            }
        )
        return dict(self.response)

    async def async_send_command(self, command, payload, timeout=None):
        self.calls.append(
            {
                "command": command,
                "payload": payload,
                "timeout": timeout,
                "mode": "async",
            }
        )
        return dict(self.response)


class FakeCancelRepository:
    def __init__(self):
        self.precheck_calls = []
        self.record_calls = []

    def get_delivery_task_cancel_target(self, task_id):
        self.precheck_calls.append({"task_id": task_id, "mode": "sync"})
        return {
            "result_code": "ACCEPTED",
            "task_id": 101,
            "task_status": "RUNNING",
            "assigned_robot_id": "pinky2",
        }

    async def async_get_delivery_task_cancel_target(self, task_id):
        self.precheck_calls.append({"task_id": task_id, "mode": "async"})
        return {
            "result_code": "ACCEPTED",
            "task_id": 101,
            "task_status": "RUNNING",
            "assigned_robot_id": "pinky2",
        }

    def record_delivery_task_cancel_result(self, *, task_id, cancel_response):
        self.record_calls.append(
            {
                "task_id": task_id,
                "cancel_response": cancel_response,
                "mode": "sync",
            }
        )
        response = dict(cancel_response)
        response.update(
            {
                "task_id": 101,
                "task_status": "CANCEL_REQUESTED",
                "assigned_robot_id": "pinky2",
            }
        )
        return response

    async def async_record_delivery_task_cancel_result(self, *, task_id, cancel_response):
        self.record_calls.append(
            {
                "task_id": task_id,
                "cancel_response": cancel_response,
                "mode": "async",
            }
        )
        response = dict(cancel_response)
        response.update(
            {
                "task_id": 101,
                "task_status": "CANCEL_REQUESTED",
                "assigned_robot_id": "pinky2",
            }
        )
        return response


class RecordingCommandExecutionRecorder:
    def __init__(self):
        self.specs = []

    def record(self, spec, command_runner):
        self.specs.append(spec)
        return command_runner()

    async def async_record(self, spec, command_runner):
        self.specs.append(spec)
        return await command_runner()


def test_delivery_cancel_service_records_sync_cancel_action_command():
    command_client = FakeCancelCommandClient()
    repository = FakeCancelRepository()
    recorder = RecordingCommandExecutionRecorder()
    service = DeliveryCancelService(
        repository=repository,
        command_client=command_client,
        command_execution_recorder=recorder,
        timeout_sec=4.0,
    )

    response = service.cancel_delivery_task("101")

    assert response["result_code"] == "CANCEL_REQUESTED"
    assert command_client.calls == [
        {
            "command": CANCEL_ACTION_COMMAND,
            "payload": {"task_id": "101"},
            "timeout": 4.0,
            "mode": "sync",
        }
    ]
    assert recorder.specs[0].command_type == "CANCEL_ACTION"
    assert recorder.specs[0].target_robot_id == "pinky2"
    assert recorder.specs[0].target_endpoint == "active_action_for_task"


def test_delivery_cancel_service_records_async_cancel_action_command():
    command_client = FakeCancelCommandClient()
    repository = FakeCancelRepository()
    recorder = RecordingCommandExecutionRecorder()
    service = DeliveryCancelService(
        repository=repository,
        command_client=command_client,
        command_execution_recorder=recorder,
        timeout_sec=4.0,
    )

    response = asyncio.run(
        service.async_cancel_delivery_task(
            "101",
            action_name="/ropi/control/pinky2/navigate_to_goal",
        )
    )

    assert response["result_code"] == "CANCEL_REQUESTED"
    assert command_client.calls[0]["mode"] == "async"
    assert command_client.calls[0]["payload"] == {
        "task_id": "101",
        "action_name": "/ropi/control/pinky2/navigate_to_goal",
    }
    assert recorder.specs[0].target_endpoint == "/ropi/control/pinky2/navigate_to_goal"
