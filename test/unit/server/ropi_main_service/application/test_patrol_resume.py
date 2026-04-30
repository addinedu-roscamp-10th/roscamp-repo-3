import asyncio

from server.ropi_main_service.application.task_request import DeliveryRequestService
from server.ropi_main_service.ipc.uds_client import RosServiceCommandError


class FakeRecorder:
    def __init__(self):
        self.specs = []

    def record(self, spec, command_runner):
        self.specs.append(spec)
        return command_runner()

    async def async_record(self, spec, command_runner):
        self.specs.append(spec)
        return await command_runner()


class FakeCommandClient:
    def __init__(self, response=None, exc=None):
        self.response = response or {"accepted": True, "message": ""}
        self.exc = exc
        self.calls = []

    def send_command(self, command, payload, timeout=None):
        self.calls.append((command, payload, timeout))
        if self.exc is not None:
            raise self.exc
        return self.response

    async def async_send_command(self, command, payload, timeout=None):
        self.calls.append((command, payload, timeout))
        if self.exc is not None:
            raise self.exc
        return self.response


class FakeRepository:
    def __init__(self, target=None, final_response=None):
        self.target = target or {
            "result_code": "ACCEPTED",
            "task_id": 2001,
            "task_status": "RUNNING",
            "phase": "WAIT_FALL_RESPONSE",
            "assigned_robot_id": "pinky3",
        }
        self.final_response = final_response or {
            "result_code": "ACCEPTED",
            "result_message": "순찰을 재개합니다.",
            "task_id": 2001,
            "task_status": "RUNNING",
            "phase": "FOLLOW_PATROL_PATH",
            "assigned_robot_id": "pinky3",
            "cancellable": True,
        }
        self.record_calls = []

    def get_patrol_task_resume_target(self, task_id):
        return self.target

    async def async_get_patrol_task_resume_target(self, task_id):
        return self.target

    def record_patrol_task_resume_result(self, **kwargs):
        self.record_calls.append(kwargs)
        return self.final_response

    async def async_record_patrol_task_resume_result(self, **kwargs):
        self.record_calls.append(kwargs)
        return self.final_response


def test_resume_patrol_task_sends_fall_response_control_and_records_action():
    repository = FakeRepository()
    recorder = FakeRecorder()
    command_client = FakeCommandClient(response={"accepted": True, "message": "restart"})
    service = DeliveryRequestService(
        repository=repository,
        command_client=command_client,
        command_execution_recorder=recorder,
        cancel_timeout_sec=3.0,
    )

    response = service.resume_patrol_task(
        task_id="2001",
        caregiver_id=7,
        member_id=301,
        action_memo="119 신고 후 병원 이송",
    )

    assert response["result_code"] == "ACCEPTED"
    assert command_client.calls == [
        (
            "fall_response_control",
            {"task_id": "2001", "command_type": "CLEAR_AND_RESTART"},
            3.0,
        )
    ]
    assert recorder.specs[0].command_type == "FALL_RESPONSE_CONTROL"
    assert recorder.specs[0].command_phase == "PATROL_RESUME"
    assert recorder.specs[0].target_robot_id == "pinky3"
    assert repository.record_calls == [
        {
            "task_id": "2001",
            "caregiver_id": 7,
            "member_id": 301,
            "action_memo": "119 신고 후 병원 이송",
            "resume_command_response": {"accepted": True, "message": "restart"},
        }
    ]


def test_resume_patrol_task_requires_action_memo_before_command():
    repository = FakeRepository()
    command_client = FakeCommandClient()
    service = DeliveryRequestService(
        repository=repository,
        command_client=command_client,
        command_execution_recorder=FakeRecorder(),
    )

    response = service.resume_patrol_task(
        task_id="2001",
        caregiver_id=7,
        member_id=301,
        action_memo="",
    )

    assert response["result_code"] == "NOT_ALLOWED"
    assert response["reason_code"] == "ACTION_MEMO_REQUIRED"
    assert command_client.calls == []
    assert repository.record_calls == []


def test_resume_patrol_task_rejects_ros_command_failure():
    repository = FakeRepository()
    command_client = FakeCommandClient(exc=RosServiceCommandError("uds down"))
    service = DeliveryRequestService(
        repository=repository,
        command_client=command_client,
        command_execution_recorder=FakeRecorder(),
    )

    response = service.resume_patrol_task(
        task_id="2001",
        caregiver_id=7,
        member_id=301,
        action_memo="119 신고 후 병원 이송",
    )

    assert response["result_code"] == "NOT_ALLOWED"
    assert response["reason_code"] == "ROS_SERVICE_UNAVAILABLE"
    assert response["task_id"] == 2001
    assert response["task_status"] == "RUNNING"
    assert repository.record_calls == []


def test_async_resume_patrol_task_uses_async_command_client_and_repository():
    repository = FakeRepository()
    command_client = FakeCommandClient(response={"accepted": True})
    service = DeliveryRequestService(
        repository=repository,
        command_client=command_client,
        command_execution_recorder=FakeRecorder(),
    )

    response = asyncio.run(
        service.async_resume_patrol_task(
            task_id="2001",
            caregiver_id=7,
            member_id=301,
            action_memo="119 신고 후 병원 이송",
        )
    )

    assert response["result_code"] == "ACCEPTED"
    assert command_client.calls[0][0] == "fall_response_control"
    assert repository.record_calls[0]["resume_command_response"] == {"accepted": True}
