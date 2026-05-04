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
        self.recorded.append(kwargs)
        return {
            "result_code": "ACCEPTED",
            "task_id": int(kwargs["task_id"]),
            "task_status": "CANCELLED",
            "phase": "GUIDANCE_CANCELLED",
            "guide_phase": "CANCELLED",
            "assigned_robot_id": kwargs["pinky_id"],
        }


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


class FakeGuideNavigationStarter:
    def __init__(self, response=None):
        self.response = response or {
            "result_code": "ACCEPTED",
            "navigation_started": True,
            "nav_phase": "GUIDE_DESTINATION",
        }
        self.started = []

    def __call__(self, **kwargs):
        self.started.append(kwargs)
        return self.response


class FakeGuideTrackingSnapshotStore:
    def __init__(self, snapshot=None):
        self.snapshot = snapshot
        self.calls = []

    def get(self, *, task_id=None, pinky_id=None):
        self.calls.append({"task_id": task_id, "pinky_id": pinky_id})
        return self.snapshot


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


def test_visit_guide_service_returns_tracking_status_from_control_snapshot_store():
    snapshot_store = FakeGuideTrackingSnapshotStore(
        snapshot={
            "task_id": 3001,
            "pinky_id": "pinky1",
            "tracking_status": "TRACKING",
            "active_track_id": "track_17",
            "tracking_result_seq": 881,
        }
    )
    service = VisitGuideService(guide_tracking_snapshot_store=snapshot_store)

    ok, message, response = service.get_tracking_status(
        task_id=3001,
        pinky_id="pinky1",
    )

    assert ok is True
    assert message == "안내 대상을 확인했습니다."
    assert response["result_code"] == "FOUND"
    assert response["target_track_id"] == "track_17"
    assert response["active_track_id"] == "track_17"
    assert response["tracking_status"] == "TRACKING"
    assert snapshot_store.calls == [{"task_id": 3001, "pinky_id": "pinky1"}]


def test_visit_guide_service_returns_pending_when_tracking_snapshot_is_missing():
    snapshot_store = FakeGuideTrackingSnapshotStore(snapshot=None)
    service = VisitGuideService(guide_tracking_snapshot_store=snapshot_store)

    ok, message, response = service.get_tracking_status(
        task_id=3001,
        pinky_id="pinky1",
    )

    assert ok is False
    assert message == "안내 대상 확인 대기 중입니다."
    assert response["result_code"] == "PENDING"
    assert response["target_track_id"] is None


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


def test_visit_guide_service_start_guide_driving_sends_start_guidance_and_navigation():
    command_service = FakeGuideCommandService(response={"accepted": True, "message": ""})
    lifecycle_repository = FakeGuideTaskLifecycleRepository()
    navigation_repository = FakeGuideTaskNavigationRepository()
    navigation_starter = FakeGuideNavigationStarter()
    service = VisitGuideService(
        guide_command_service=command_service,
        guide_task_lifecycle_repository=lifecycle_repository,
        guide_task_navigation_repository=navigation_repository,
        guide_navigation_starter=navigation_starter,
    )

    ok, message, response = service.start_guide_driving(
        task_id=3001,
        target_track_id="track_17",
    )

    assert ok is True
    assert message == "안내 주행을 시작했습니다."
    assert command_service.sent[0]["command_type"] == "START_GUIDANCE"
    assert command_service.sent[0]["target_track_id"] == "track_17"
    assert navigation_starter.started == [
        {
            "task_id": 3001,
            "pinky_id": "pinky1",
            "goal_pose": navigation_repository.response["goal_pose"],
            "timeout_sec": 120.0,
        }
    ]
    assert response["task_status"] == "RUNNING"
    assert response["phase"] == "GUIDANCE_RUNNING"
    assert response["target_track_id"] == "track_17"
    assert response["navigation_response"]["navigation_started"] is True


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


def test_visit_guide_service_async_start_guide_driving_delegates_navigation():
    command_service = FakeGuideCommandService(response={"accepted": True, "message": ""})
    lifecycle_repository = FakeGuideTaskLifecycleRepository()
    navigation_repository = FakeGuideTaskNavigationRepository()
    navigation_starter = FakeGuideNavigationStarter()
    service = VisitGuideService(
        guide_command_service=command_service,
        guide_task_lifecycle_repository=lifecycle_repository,
        guide_task_navigation_repository=navigation_repository,
        guide_navigation_starter=navigation_starter,
    )

    ok, _message, response = asyncio.run(
        service.async_start_guide_driving(
            task_id=3001,
            target_track_id="track_17",
        )
    )

    assert ok is True
    assert navigation_starter.started[0]["pinky_id"] == "pinky1"
    assert response["navigation_response"]["result_code"] == "ACCEPTED"
