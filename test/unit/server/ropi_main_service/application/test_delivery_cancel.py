import asyncio

from server.ropi_main_service.application.task_request import DeliveryRequestService


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
    def __init__(self, target_response=None, record_response=None):
        self.target_response = target_response or {
            "result_code": "ACCEPTED",
            "task_id": 101,
            "task_status": "RUNNING",
            "assigned_robot_id": "pinky2",
        }
        self.record_response = record_response
        self.precheck_calls = []
        self.record_calls = []

    def get_delivery_task_cancel_target(self, task_id):
        self.precheck_calls.append({"task_id": task_id, "mode": "sync"})
        return dict(self.target_response)

    async def async_get_delivery_task_cancel_target(self, task_id):
        self.precheck_calls.append({"task_id": task_id, "mode": "async"})
        return dict(self.target_response)

    def record_delivery_task_cancel_result(self, *, task_id, cancel_response):
        self.record_calls.append(
            {
                "task_id": task_id,
                "cancel_response": cancel_response,
                "mode": "sync",
            }
        )
        if self.record_response is not None:
            return dict(self.record_response)
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
        if self.record_response is not None:
            return dict(self.record_response)
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


def test_cancel_delivery_task_sends_cancel_action_to_ros_service():
    command_client = FakeCancelCommandClient()
    repository = FakeCancelRepository()
    command_execution_recorder = RecordingCommandExecutionRecorder()
    service = DeliveryRequestService(
        repository=repository,
        command_client=command_client,
        command_execution_recorder=command_execution_recorder,
    )

    response = service.cancel_delivery_task(task_id="101")

    assert response["result_code"] == "CANCEL_REQUESTED"
    assert response["task_status"] == "CANCEL_REQUESTED"
    assert repository.precheck_calls == [{"task_id": "101", "mode": "sync"}]
    assert repository.record_calls == [
        {
            "task_id": "101",
            "cancel_response": command_client.response,
            "mode": "sync",
        }
    ]
    assert command_client.calls == [
        {
            "command": "cancel_action",
            "payload": {
                "task_id": "101",
            },
            "timeout": 5.0,
            "mode": "sync",
        }
    ]
    assert len(command_execution_recorder.specs) == 1
    spec = command_execution_recorder.specs[0]
    assert spec.task_id == "101"
    assert spec.transport == "ROS_ACTION"
    assert spec.command_type == "CANCEL_ACTION"
    assert spec.command_phase == "CANCEL"
    assert spec.target_robot_id == "pinky2"
    assert spec.target_endpoint == "active_action_for_task"


def test_async_cancel_delivery_task_uses_async_ros_service_client():
    command_client = FakeCancelCommandClient()
    repository = FakeCancelRepository()
    command_execution_recorder = RecordingCommandExecutionRecorder()
    service = DeliveryRequestService(
        repository=repository,
        command_client=command_client,
        command_execution_recorder=command_execution_recorder,
    )

    response = asyncio.run(
        service.async_cancel_delivery_task(
            task_id="101",
            action_name="/ropi/control/pinky2/navigate_to_goal",
        )
    )

    assert response["result_code"] == "CANCEL_REQUESTED"
    assert response["task_status"] == "CANCEL_REQUESTED"
    assert repository.precheck_calls == [{"task_id": "101", "mode": "async"}]
    assert repository.record_calls == [
        {
            "task_id": "101",
            "cancel_response": command_client.response,
            "mode": "async",
        }
    ]
    assert command_execution_recorder.specs[0].command_type == "CANCEL_ACTION"
    assert command_execution_recorder.specs[0].target_endpoint == "/ropi/control/pinky2/navigate_to_goal"
    assert command_client.calls == [
        {
            "command": "cancel_action",
            "payload": {
                "task_id": "101",
                "action_name": "/ropi/control/pinky2/navigate_to_goal",
            },
            "timeout": 5.0,
            "mode": "async",
        }
    ]


def test_cancel_delivery_task_rejects_blank_task_id_without_ros_call():
    command_client = FakeCancelCommandClient()
    repository = FakeCancelRepository()
    service = DeliveryRequestService(
        repository=repository,
        command_client=command_client,
    )

    response = service.cancel_delivery_task(task_id="")

    assert response == {
        "result_code": "INVALID_REQUEST",
        "result_message": "task_id가 필요합니다.",
        "reason_code": "TASK_ID_INVALID",
        "task_id": None,
        "task_status": None,
        "assigned_robot_id": None,
    }
    assert command_client.calls == []
    assert repository.precheck_calls == []
    assert repository.record_calls == []


def test_cancel_delivery_task_does_not_call_ros_when_task_is_not_cancellable():
    command_client = FakeCancelCommandClient()
    repository = FakeCancelRepository(
        target_response={
            "result_code": "REJECTED",
            "result_message": "이미 종료된 운반 task는 취소할 수 없습니다.",
            "reason_code": "TASK_NOT_CANCELLABLE",
            "task_id": 101,
            "task_status": "COMPLETED",
            "assigned_robot_id": "pinky2",
        }
    )
    service = DeliveryRequestService(
        repository=repository,
        command_client=command_client,
    )

    response = service.cancel_delivery_task(task_id="101")

    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "TASK_NOT_CANCELLABLE"
    assert command_client.calls == []
    assert repository.record_calls == []
