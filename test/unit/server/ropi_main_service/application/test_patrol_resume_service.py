import asyncio

from server.ropi_main_service.application.patrol_resume import PatrolResumeService


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
    def __init__(self, response=None):
        self.response = response or {"accepted": True, "message": "restart"}
        self.calls = []

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


class FakePatrolResumeRepository:
    def __init__(self):
        self.record_calls = []

    def get_patrol_task_resume_target(self, task_id):
        return {
            "result_code": "ACCEPTED",
            "task_id": 2001,
            "task_status": "RUNNING",
            "phase": "WAIT_FALL_RESPONSE",
            "assigned_robot_id": "pinky3",
        }

    async def async_get_patrol_task_resume_target(self, task_id):
        return self.get_patrol_task_resume_target(task_id)

    def record_patrol_task_resume_result(self, **kwargs):
        self.record_calls.append({**kwargs, "mode": "sync"})
        return {
            "result_code": "ACCEPTED",
            "result_message": "순찰을 재개합니다.",
            "task_id": 2001,
            "task_status": "RUNNING",
            "phase": "FOLLOW_PATROL_PATH",
            "assigned_robot_id": "pinky3",
            "cancellable": True,
        }

    async def async_record_patrol_task_resume_result(self, **kwargs):
        self.record_calls.append({**kwargs, "mode": "async"})
        return {
            "result_code": "ACCEPTED",
            "result_message": "순찰을 재개합니다.",
            "task_id": 2001,
            "task_status": "RUNNING",
            "phase": "FOLLOW_PATROL_PATH",
            "assigned_robot_id": "pinky3",
            "cancellable": True,
        }


def test_patrol_resume_service_records_sync_fall_response_command():
    repository = FakePatrolResumeRepository()
    command_client = FakeCommandClient()
    recorder = FakeRecorder()
    service = PatrolResumeService(
        repository=repository,
        command_client=command_client,
        command_execution_recorder=recorder,
        timeout_sec=3.0,
    )

    response = service.resume_patrol_task(
        task_id="2001",
        caregiver_id=7,
        member_id=301,
        action_memo="119 신고 후 병원 이송",
    )

    assert response["result_code"] == "ACCEPTED"
    assert command_client.calls == [
        {
            "command": "fall_response_control",
            "payload": {"task_id": "2001", "command_type": "CLEAR_AND_RESTART"},
            "timeout": 3.0,
            "mode": "sync",
        }
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
            "mode": "sync",
        }
    ]


def test_patrol_resume_service_records_async_fall_response_command():
    repository = FakePatrolResumeRepository()
    command_client = FakeCommandClient(response={"accepted": True})
    service = PatrolResumeService(
        repository=repository,
        command_client=command_client,
        command_execution_recorder=FakeRecorder(),
        timeout_sec=3.0,
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
    assert command_client.calls == [
        {
            "command": "fall_response_control",
            "payload": {"task_id": "2001", "command_type": "CLEAR_AND_RESTART"},
            "timeout": 3.0,
            "mode": "async",
        }
    ]
    assert repository.record_calls[0]["resume_command_response"] == {"accepted": True}
    assert repository.record_calls[0]["mode"] == "async"


def test_patrol_resume_service_rejects_command_denial_before_recording_result():
    repository = FakePatrolResumeRepository()
    command_client = FakeCommandClient(response={"accepted": False, "message": "busy"})
    service = PatrolResumeService(
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
    assert response["reason_code"] == "PATROL_RESUME_COMMAND_REJECTED"
    assert response["result_message"] == "busy"
    assert repository.record_calls == []
