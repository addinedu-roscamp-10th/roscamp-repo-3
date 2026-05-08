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
            "target_track_id": -1,
            "destination_id": "",
            "destination_pose": None,
        }
    ]
    assert lifecycle_repository.recorded == [
        {
            "task_id": 3001,
            "pinky_id": "pinky1",
            "command_type": "WAIT_TARGET_TRACKING",
            "target_track_id": -1,
            "command_response": {"accepted": True, "message": "done"},
        }
    ]
    assert response["accepted"] is True
    assert response["task_status"] == "RUNNING"
    assert response["phase"] == "WAIT_TARGET_TRACKING"
    assert response["lifecycle_result"] is lifecycle_repository.response


def test_guide_command_lifecycle_service_rejects_unsupported_post_start_command():
    command_service = FakeGuideCommandService()
    lifecycle_repository = FakeGuideTaskLifecycleRepository(
        response={
            "result_code": "REJECTED",
            "result_message": "지원하지 않는 안내 제어 명령입니다.",
            "reason_code": "COMMAND_TYPE_INVALID",
            "task_id": 3001,
            "task_status": "RUNNING",
            "phase": "WAIT_TARGET_TRACKING",
            "guide_phase": "WAIT_TARGET_TRACKING",
            "assigned_robot_id": "pinky1",
            "accepted": False,
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
    )

    assert ok is False
    assert message == "지원하지 않는 안내 제어 명령입니다."
    assert command_service.sent == []
    assert response["accepted"] is False
    assert response["reason_code"] == "COMMAND_TYPE_INVALID"
    assert lifecycle_repository.recorded[0]["command_response"] == {
        "accepted": False,
        "result_code": "REJECTED",
        "result_message": "지원하지 않는 안내 제어 명령입니다.",
        "reason_code": "COMMAND_TYPE_INVALID",
        "message": "지원하지 않는 안내 제어 명령입니다.",
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
            target_track_id=17,
            destination_id="delivery_room_301",
            destination_pose={"header": {"frame_id": "map"}},
        )
    )

    assert ok is True
    assert message == "async done"
    assert command_service.sent[0]["pinky_id"] == "pinky7"
    assert command_service.sent[0]["target_track_id"] == 17
    assert command_service.sent[0]["destination_id"] == "delivery_room_301"
    assert lifecycle_repository.recorded[0]["pinky_id"] == "pinky7"
    assert lifecycle_repository.recorded[0]["target_track_id"] == 17
    assert response["lifecycle_result"] is lifecycle_repository.response
