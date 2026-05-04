import asyncio

from server.ropi_main_service.application.guide_command_lifecycle import (
    GuideCommandLifecycleService,
)


class FakeGuideCommandService:
    def __init__(self, response=None, error_message=None):
        self.response = response or {"accepted": True, "message": "accepted"}
        self.error_message = error_message
        self.sent = []

    def send(self, **kwargs):
        self.sent.append(kwargs)
        if self.error_message:
            raise RuntimeError(self.error_message)
        return self.response

    async def async_send(self, **kwargs):
        self.sent.append(kwargs)
        if self.error_message:
            raise RuntimeError(self.error_message)
        return self.response


class FakeGuideTaskLifecycleRepository:
    def __init__(self, response=None):
        self.response = response or {
            "result_code": "ACCEPTED",
            "task_id": 3001,
            "task_status": "RUNNING",
            "phase": "WAIT_TARGET_TRACKING",
            "guide_phase": "WAIT_TARGET_TRACKING",
            "assigned_robot_id": "pinky1",
            "accepted": True,
        }
        self.recorded = []

    def record_command_result(self, **kwargs):
        self.recorded.append(kwargs)
        return self.response

    async def async_record_command_result(self, **kwargs):
        self.recorded.append(kwargs)
        return self.response


def test_guide_command_lifecycle_service_records_and_merges_sync_command():
    command_service = FakeGuideCommandService(
        response={"accepted": True, "message": "done"}
    )
    lifecycle_repository = FakeGuideTaskLifecycleRepository()
    service = GuideCommandLifecycleService(
        guide_command_service=command_service,
        guide_task_lifecycle_repository=lifecycle_repository,
        default_pinky_id="pinky1",
    )

    ok, message, response = service.send_command(
        task_id=3001,
        command_type="WAIT_TARGET_TRACKING",
    )

    assert ok is True
    assert message == "done"
    assert command_service.sent == [
        {
            "task_id": 3001,
            "pinky_id": "pinky1",
            "command_type": "WAIT_TARGET_TRACKING",
            "target_track_id": "",
            "wait_timeout_sec": 0,
            "finish_reason": "",
        }
    ]
    assert lifecycle_repository.recorded == [
        {
            "task_id": 3001,
            "pinky_id": "pinky1",
            "command_type": "WAIT_TARGET_TRACKING",
            "target_track_id": "",
            "wait_timeout_sec": 0,
            "finish_reason": "",
            "command_response": {"accepted": True, "message": "done"},
        }
    ]
    assert response["accepted"] is True
    assert response["task_status"] == "RUNNING"
    assert response["phase"] == "WAIT_TARGET_TRACKING"
    assert response["lifecycle_result"] is lifecycle_repository.response


def test_guide_command_lifecycle_service_uses_lifecycle_success_after_transport_error():
    command_service = FakeGuideCommandService(
        error_message="/ropi/control/pinky1/guide_command service is not available."
    )
    lifecycle_repository = FakeGuideTaskLifecycleRepository(
        response={
            "result_code": "ACCEPTED",
            "result_message": "안내 시작 전 취소가 접수되었습니다.",
            "reason_code": "USER_CANCELLED",
            "task_id": 3001,
            "task_status": "CANCELLED",
            "phase": "GUIDANCE_CANCELLED",
            "guide_phase": "CANCELLED",
            "assigned_robot_id": "pinky1",
            "accepted": True,
        }
    )
    service = GuideCommandLifecycleService(
        guide_command_service=command_service,
        guide_task_lifecycle_repository=lifecycle_repository,
        default_pinky_id="pinky1",
    )

    ok, message, response = service.send_command(
        task_id=3001,
        command_type="FINISH_GUIDANCE",
        finish_reason="USER_CANCELLED",
    )

    assert ok is True
    assert message == "안내 시작 전 취소가 접수되었습니다."
    assert response["accepted"] is True
    assert response["reason_code"] == "USER_CANCELLED"
    assert response["task_status"] == "CANCELLED"
    assert lifecycle_repository.recorded[0]["command_response"] == {
        "accepted": False,
        "result_code": "REJECTED",
        "result_message": "/ropi/control/pinky1/guide_command service is not available.",
        "reason_code": "GUIDE_COMMAND_TRANSPORT_ERROR",
        "message": "/ropi/control/pinky1/guide_command service is not available.",
    }


def test_guide_command_lifecycle_service_records_async_command():
    command_service = FakeGuideCommandService(
        response={"accepted": True, "message": "async done"}
    )
    lifecycle_repository = FakeGuideTaskLifecycleRepository()
    service = GuideCommandLifecycleService(
        guide_command_service=command_service,
        guide_task_lifecycle_repository=lifecycle_repository,
        default_pinky_id="pinky1",
    )

    ok, message, response = asyncio.run(
        service.async_send_command(
            task_id=3001,
            pinky_id="pinky7",
            command_type="START_GUIDANCE",
            target_track_id="track_17",
        )
    )

    assert ok is True
    assert message == "async done"
    assert command_service.sent[0]["pinky_id"] == "pinky7"
    assert command_service.sent[0]["target_track_id"] == "track_17"
    assert lifecycle_repository.recorded[0]["pinky_id"] == "pinky7"
    assert lifecycle_repository.recorded[0]["target_track_id"] == "track_17"
    assert response["lifecycle_result"] is lifecycle_repository.response
