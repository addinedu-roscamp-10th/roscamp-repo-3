import asyncio

from server.ropi_main_service.application.visit_guide import VisitGuideService


class FakeGuideTaskRepository:
    def __init__(self):
        self.created = None

    def create_guide_task(self, **kwargs):
        self.created = kwargs
        return {
            "result_code": "ACCEPTED",
            "task_id": 3001,
            "task_status": "WAITING_DISPATCH",
            "phase": "WAIT_GUIDE_START_CONFIRM",
            "assigned_robot_id": "pinky1",
            "resident_name": "김*수",
            "room_no": "301",
            "destination_id": "delivery_room_301",
        }

    async def async_create_guide_task(self, **kwargs):
        self.created = kwargs
        return self.create_guide_task(**kwargs)


class FakeGuideCommandService:
    def __init__(self, response=None):
        self.response = response or {"accepted": True, "message": "accepted"}
        self.sent = []

    def send(self, **kwargs):
        self.sent.append(kwargs)
        return self.response

    async def async_send(self, **kwargs):
        self.sent.append(kwargs)
        return self.response


class FakeGuideTaskLifecycleRepository:
    def __init__(self):
        self.recorded = []

    def record_command_result(self, **kwargs):
        self.recorded.append(kwargs)
        return {
            "result_code": "ACCEPTED",
            "task_id": int(kwargs["task_id"]),
            "task_status": "RUNNING",
            "phase": "WAIT_TARGET_TRACKING",
            "guide_phase": "WAIT_TARGET_TRACKING",
            "assigned_robot_id": kwargs["pinky_id"],
        }

    async def async_record_command_result(self, **kwargs):
        self.recorded.append(kwargs)
        return {
            "result_code": "ACCEPTED",
            "task_id": int(kwargs["task_id"]),
            "task_status": "CANCELLED",
            "phase": "GUIDANCE_CANCELLED",
            "guide_phase": "CANCELLED",
            "assigned_robot_id": kwargs["pinky_id"],
        }


def test_visit_guide_service_create_guide_task_validates_required_fields():
    service = VisitGuideService(guide_task_repository=FakeGuideTaskRepository())

    response = service.create_guide_task(
        request_id="",
        visitor_id=1,
        idempotency_key="idem_guide_001",
    )

    assert response["result_code"] == "INVALID_REQUEST"
    assert response["reason_code"] == "REQUEST_ID_INVALID"


def test_visit_guide_service_create_guide_task_delegates_to_repository():
    repository = FakeGuideTaskRepository()
    service = VisitGuideService(guide_task_repository=repository)

    response = service.create_guide_task(
        request_id="req_guide_001",
        visitor_id="1",
        idempotency_key="idem_guide_001",
    )

    assert response["result_code"] == "ACCEPTED"
    assert response["task_id"] == 3001
    assert repository.created == {
        "request_id": "req_guide_001",
        "visitor_id": 1,
        "priority": "NORMAL",
        "idempotency_key": "idem_guide_001",
    }


def test_visit_guide_service_async_create_guide_task_uses_async_repository():
    repository = FakeGuideTaskRepository()
    service = VisitGuideService(guide_task_repository=repository)

    response = asyncio.run(
        service.async_create_guide_task(
            request_id="req_guide_001",
            visitor_id="1",
            idempotency_key="idem_guide_001",
        )
    )

    assert response["result_code"] == "ACCEPTED"
    assert response["task_id"] == 3001
    assert repository.created["visitor_id"] == 1


def test_visit_guide_service_records_guide_command_lifecycle_after_command_success():
    command_service = FakeGuideCommandService(response={"accepted": True, "message": ""})
    lifecycle_repository = FakeGuideTaskLifecycleRepository()
    service = VisitGuideService(
        guide_command_service=command_service,
        guide_task_lifecycle_repository=lifecycle_repository,
    )

    ok, message, response = service.send_guide_command(
        task_id=3001,
        pinky_id="pinky1",
        command_type="WAIT_TARGET_TRACKING",
    )

    assert ok is True
    assert message == "안내 제어 명령이 수락되었습니다."
    assert lifecycle_repository.recorded == [
        {
            "task_id": 3001,
            "pinky_id": "pinky1",
            "command_type": "WAIT_TARGET_TRACKING",
            "target_track_id": "",
            "wait_timeout_sec": 0,
            "finish_reason": "",
            "command_response": {"accepted": True, "message": ""},
        }
    ]
    assert response["task_status"] == "RUNNING"
    assert response["phase"] == "WAIT_TARGET_TRACKING"


def test_visit_guide_service_async_finish_records_cancelled_lifecycle():
    command_service = FakeGuideCommandService(response={"accepted": True, "message": "finished"})
    lifecycle_repository = FakeGuideTaskLifecycleRepository()
    service = VisitGuideService(
        guide_command_service=command_service,
        guide_task_lifecycle_repository=lifecycle_repository,
    )

    ok, message, response = asyncio.run(
        service.async_finish_guide_session(
            task_id=3001,
            pinky_id="pinky1",
            finish_reason="USER_CANCELLED",
        )
    )

    assert ok is True
    assert message == "finished"
    assert lifecycle_repository.recorded[0]["command_type"] == "FINISH_GUIDANCE"
    assert lifecycle_repository.recorded[0]["finish_reason"] == "USER_CANCELLED"
    assert response["task_status"] == "CANCELLED"
    assert response["phase"] == "GUIDANCE_CANCELLED"
