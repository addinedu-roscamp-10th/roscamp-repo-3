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


class FailingGuideCommandService:
    def __init__(self, error_message="ROS service command failed"):
        self.error_message = error_message
        self.sent = []

    def send(self, **kwargs):
        self.sent.append(kwargs)
        raise RuntimeError(self.error_message)

    async def async_send(self, **kwargs):
        self.sent.append(kwargs)
        raise RuntimeError(self.error_message)


class FakeGuideTaskLifecycleRepository:
    def __init__(self):
        self.recorded = []

    def record_command_result(self, **kwargs):
        self.recorded.append(kwargs)
        if not (kwargs.get("command_response") or {}).get("accepted"):
            return {
                "result_code": "REJECTED",
                "result_message": (kwargs.get("command_response") or {}).get("result_message"),
                "reason_code": (kwargs.get("command_response") or {}).get("reason_code"),
                "task_id": int(kwargs["task_id"]),
                "task_status": "WAITING_DISPATCH",
                "phase": "WAIT_GUIDE_START_CONFIRM",
                "guide_phase": "WAIT_GUIDE_START_CONFIRM",
                "assigned_robot_id": kwargs["pinky_id"],
                "accepted": False,
            }
        if kwargs["command_type"] == "START_GUIDANCE":
            return {
                "result_code": "ACCEPTED",
                "task_id": int(kwargs["task_id"]),
                "task_status": "RUNNING",
                "phase": "GUIDANCE_RUNNING",
                "guide_phase": "GUIDANCE_RUNNING",
                "assigned_robot_id": kwargs["pinky_id"],
                "target_track_id": kwargs["target_track_id"],
            }
        return {
            "result_code": "ACCEPTED",
            "task_id": int(kwargs["task_id"]),
            "task_status": "RUNNING",
            "phase": "WAIT_TARGET_TRACKING",
            "guide_phase": "WAIT_TARGET_TRACKING",
            "assigned_robot_id": kwargs["pinky_id"],
        }

    async def async_record_command_result(self, **kwargs):
        return self.record_command_result(**kwargs)


class FakeGuideTaskNavigationRepository:
    def __init__(self, response=None):
        self.response = response or {
            "result_code": "ACCEPTED",
            "result_message": "안내 목적지 좌표를 확인했습니다.",
            "task_id": 3001,
            "task_type": "GUIDE",
            "task_status": "RUNNING",
            "phase": "WAIT_TARGET_TRACKING",
            "assigned_robot_id": "pinky1",
            "destination_id": "delivery_room_301",
            "goal_pose": {
                "header": {"stamp": {"sec": 0, "nanosec": 0}, "frame_id": "map"},
                "pose": {
                    "position": {"x": 1.5, "y": 2.5, "z": 0.0},
                    "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                },
            },
        }
        self.requested = []

    def get_guide_driving_context(self, **kwargs):
        self.requested.append(kwargs)
        return self.response

    async def async_get_guide_driving_context(self, **kwargs):
        self.requested.append(kwargs)
        return self.response


class FakeGuideRuntimePreflight:
    def __init__(self, response=None):
        self.response = response or {
            "result_code": "ACCEPTED",
            "result_message": "안내 ROS 런타임이 준비되었습니다.",
            "ready": True,
        }
        self.checked = []

    def check(self, **kwargs):
        self.checked.append(kwargs)
        return self.response

    async def async_check(self, **kwargs):
        self.checked.append(kwargs)
        return self.response


class FakeGuideRuntimeService:
    def __init__(self, status):
        self.status = status
        self.calls = []

    def get_status(self, *, pinky_id=None):
        self.calls.append(pinky_id)
        return self.status


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


def test_visit_guide_service_returns_guide_runtime_status_from_phase_snapshot():
    runtime_service = FakeGuideRuntimeService(
        status={
            "guide_runtime": {
                "connected": True,
                "stale": False,
                "last_update": {
                    "task_id": "3001",
                    "pinky_id": "pinky1",
                    "guide_phase": "READY_TO_START_GUIDANCE",
                    "target_track_id": 17,
                    "seq": 881,
                },
            }
        }
    )
    service = VisitGuideService(guide_runtime_service=runtime_service)

    ok, message, response = service.get_guide_runtime_status(pinky_id="pinky1")

    assert ok is True
    assert message == "안내 추적 상태를 확인했습니다."
    assert response["guide_runtime"]["last_update"]["guide_phase"] == (
        "READY_TO_START_GUIDANCE"
    )
    assert response["guide_runtime"]["last_update"]["target_track_id"] == 17
    assert runtime_service.calls == ["pinky1"]


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
            "target_track_id": -1,
            "command_response": {"accepted": True, "message": ""},
        }
    ]
    assert response["task_status"] == "RUNNING"
    assert response["phase"] == "WAIT_TARGET_TRACKING"


def test_visit_guide_service_records_rejected_lifecycle_when_guide_command_transport_fails():
    command_service = FailingGuideCommandService("UDS socket missing")
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

    assert ok is False
    assert "UDS socket missing" in message
    assert lifecycle_repository.recorded == [
        {
            "task_id": 3001,
            "pinky_id": "pinky1",
            "command_type": "WAIT_TARGET_TRACKING",
            "target_track_id": -1,
            "command_response": {
                "accepted": False,
                "result_code": "REJECTED",
                "result_message": "UDS socket missing",
                "reason_code": "GUIDE_COMMAND_TRANSPORT_ERROR",
                "message": "UDS socket missing",
            },
        }
    ]
    assert response["accepted"] is False
    assert response["reason_code"] == "GUIDE_COMMAND_TRANSPORT_ERROR"


def test_visit_guide_service_rejects_finish_guide_session_command_boundary():
    command_service = FailingGuideCommandService(
        "/ropi/control/pinky1/guide_command service is not available."
    )
    lifecycle_repository = FakeGuideTaskLifecycleRepository()
    service = VisitGuideService(
        guide_command_service=command_service,
        guide_task_lifecycle_repository=lifecycle_repository,
    )

    ok, message, response = service.finish_guide_session(
        task_id=3001,
        pinky_id="pinky1",
        finish_reason="USER_CANCELLED",
    )

    assert ok is False
    assert message == "지원하지 않는 안내 제어 명령입니다."
    assert response["accepted"] is False
    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "COMMAND_TYPE_INVALID"
    assert response["task_id"] == 3001
    assert response["task_type"] == "GUIDE"
    assert response["assigned_robot_id"] == "pinky1"
    assert command_service.sent == []
    assert lifecycle_repository.recorded == []


def test_visit_guide_service_async_records_rejected_lifecycle_when_guide_command_transport_fails():
    command_service = FailingGuideCommandService("UDS socket missing")
    lifecycle_repository = FakeGuideTaskLifecycleRepository()
    service = VisitGuideService(
        guide_command_service=command_service,
        guide_task_lifecycle_repository=lifecycle_repository,
    )

    ok, message, response = asyncio.run(
        service.async_send_guide_command(
            task_id=3001,
            pinky_id="pinky1",
            command_type="WAIT_TARGET_TRACKING",
        )
    )

    assert ok is False
    assert "UDS socket missing" in message
    assert lifecycle_repository.recorded[0]["command_response"]["reason_code"] == (
        "GUIDE_COMMAND_TRANSPORT_ERROR"
    )
    assert response["accepted"] is False
    assert response["reason_code"] == "GUIDE_COMMAND_TRANSPORT_ERROR"


def test_visit_guide_service_async_finish_rejects_command_boundary():
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

    assert ok is False
    assert message == "지원하지 않는 안내 제어 명령입니다."
    assert response["reason_code"] == "COMMAND_TYPE_INVALID"
    assert response["task_id"] == 3001
    assert response["task_type"] == "GUIDE"
    assert response["assigned_robot_id"] == "pinky1"
    assert command_service.sent == []
    assert lifecycle_repository.recorded == []


def test_visit_guide_service_start_guide_driving_sends_start_guidance_without_navigation():
    command_service = FakeGuideCommandService(response={"accepted": True, "message": ""})
    lifecycle_repository = FakeGuideTaskLifecycleRepository()
    navigation_repository = FakeGuideTaskNavigationRepository()
    runtime_preflight = FakeGuideRuntimePreflight()
    service = VisitGuideService(
        guide_command_service=command_service,
        guide_task_lifecycle_repository=lifecycle_repository,
        guide_task_navigation_repository=navigation_repository,
        guide_runtime_preflight=runtime_preflight,
    )

    ok, message, response = service.start_guide_driving(
        task_id=3001,
        target_track_id=17,
    )

    assert ok is True
    assert message == "안내 주행을 시작했습니다."
    assert command_service.sent[0]["command_type"] == "START_GUIDANCE"
    assert command_service.sent[0]["target_track_id"] == 17
    assert command_service.sent[0]["destination_id"] == "delivery_room_301"
    assert command_service.sent[0]["destination_pose"] == navigation_repository.response["goal_pose"]
    assert runtime_preflight.checked == [{"task_id": 3001, "pinky_id": "pinky1"}]
    assert response["task_status"] == "RUNNING"
    assert response["phase"] == "GUIDANCE_RUNNING"
    assert response["target_track_id"] == 17
    assert "navigation_response" not in response


def test_visit_guide_service_start_guide_driving_returns_command_rejection_without_navigation():
    command_service = FakeGuideCommandService(
        response={
            "accepted": False,
            "result_code": "REJECTED",
            "result_message": "guide command rejected",
            "reason_code": "GUIDE_STATE_MISMATCH",
            "message": "guide command rejected",
        }
    )
    lifecycle_repository = FakeGuideTaskLifecycleRepository()
    navigation_repository = FakeGuideTaskNavigationRepository()
    runtime_preflight = FakeGuideRuntimePreflight()
    service = VisitGuideService(
        guide_command_service=command_service,
        guide_task_lifecycle_repository=lifecycle_repository,
        guide_task_navigation_repository=navigation_repository,
        guide_runtime_preflight=runtime_preflight,
    )

    ok, message, response = service.start_guide_driving(
        task_id=3001,
        target_track_id=17,
    )

    assert ok is False
    assert message == "guide command rejected"
    assert runtime_preflight.checked == [{"task_id": 3001, "pinky_id": "pinky1"}]
    assert command_service.sent[0]["target_track_id"] == 17
    assert lifecycle_repository.recorded[0]["command_type"] == "START_GUIDANCE"
    assert lifecycle_repository.recorded[0]["target_track_id"] == 17
    assert lifecycle_repository.recorded[0]["command_response"]["reason_code"] == (
        "GUIDE_STATE_MISMATCH"
    )
    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "GUIDE_STATE_MISMATCH"
    assert "navigation_response" not in response


def test_visit_guide_service_start_guide_driving_rejects_failed_runtime_preflight():
    command_service = FakeGuideCommandService(response={"accepted": True, "message": ""})
    lifecycle_repository = FakeGuideTaskLifecycleRepository()
    runtime_preflight = FakeGuideRuntimePreflight(
        response={
            "result_code": "REJECTED",
            "result_message": "안내 ROS 런타임이 준비되지 않았습니다.",
            "reason_code": "GUIDE_RUNTIME_NOT_READY",
        }
    )
    service = VisitGuideService(
        guide_command_service=command_service,
        guide_task_lifecycle_repository=lifecycle_repository,
        guide_task_navigation_repository=FakeGuideTaskNavigationRepository(),
        guide_runtime_preflight=runtime_preflight,
    )

    ok, message, response = service.start_guide_driving(
        task_id=3001,
        target_track_id=17,
    )

    assert ok is False
    assert message == "안내 ROS 런타임이 준비되지 않았습니다."
    assert command_service.sent == []
    assert runtime_preflight.checked == [{"task_id": 3001, "pinky_id": "pinky1"}]
    assert lifecycle_repository.recorded[0]["command_type"] == "START_GUIDANCE"
    assert lifecycle_repository.recorded[0]["command_response"]["reason_code"] == (
        "GUIDE_RUNTIME_NOT_READY"
    )
    assert response["reason_code"] == "GUIDE_RUNTIME_NOT_READY"
    assert "navigation_response" not in response


def test_visit_guide_service_start_guide_driving_requires_target_track_id():
    service = VisitGuideService(
        guide_task_navigation_repository=FakeGuideTaskNavigationRepository(),
    )

    ok, message, response = service.start_guide_driving(
        task_id=3001,
        target_track_id="",
    )

    assert ok is False
    assert message == "target_track_id가 필요합니다."
    assert response["reason_code"] == "TARGET_TRACK_ID_REQUIRED"


def test_visit_guide_service_async_start_guide_driving_sends_start_guidance():
    command_service = FakeGuideCommandService(response={"accepted": True, "message": ""})
    lifecycle_repository = FakeGuideTaskLifecycleRepository()
    navigation_repository = FakeGuideTaskNavigationRepository()
    runtime_preflight = FakeGuideRuntimePreflight()
    service = VisitGuideService(
        guide_command_service=command_service,
        guide_task_lifecycle_repository=lifecycle_repository,
        guide_task_navigation_repository=navigation_repository,
        guide_runtime_preflight=runtime_preflight,
    )

    ok, _message, response = asyncio.run(
        service.async_start_guide_driving(
            task_id=3001,
            target_track_id=17,
        )
    )

    assert ok is True
    assert runtime_preflight.checked == [{"task_id": 3001, "pinky_id": "pinky1"}]
    assert command_service.sent[0]["target_track_id"] == 17
    assert response["phase"] == "GUIDANCE_RUNNING"


def test_visit_guide_service_async_start_guide_driving_returns_command_rejection():
    command_service = FakeGuideCommandService(
        response={
            "accepted": False,
            "result_code": "REJECTED",
            "result_message": "guide command rejected",
            "reason_code": "GUIDE_STATE_MISMATCH",
            "message": "guide command rejected",
        }
    )
    lifecycle_repository = FakeGuideTaskLifecycleRepository()
    runtime_preflight = FakeGuideRuntimePreflight()
    service = VisitGuideService(
        guide_command_service=command_service,
        guide_task_lifecycle_repository=lifecycle_repository,
        guide_task_navigation_repository=FakeGuideTaskNavigationRepository(),
        guide_runtime_preflight=runtime_preflight,
    )

    ok, message, response = asyncio.run(
        service.async_start_guide_driving(
            task_id=3001,
            target_track_id=17,
        )
    )

    assert ok is False
    assert message == "guide command rejected"
    assert runtime_preflight.checked == [{"task_id": 3001, "pinky_id": "pinky1"}]
    assert lifecycle_repository.recorded[0]["command_type"] == "START_GUIDANCE"
    assert lifecycle_repository.recorded[0]["target_track_id"] == 17
    assert lifecycle_repository.recorded[0]["command_response"]["reason_code"] == (
        "GUIDE_STATE_MISMATCH"
    )
    assert response["reason_code"] == "GUIDE_STATE_MISMATCH"
    assert "navigation_response" not in response
