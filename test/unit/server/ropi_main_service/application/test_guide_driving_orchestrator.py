import asyncio

from server.ropi_main_service.application.guide_driving_orchestrator import (
    START_GUIDANCE_COMMAND,
    GuideDrivingOrchestrator,
)


class FakeGuideTaskNavigationRepository:
    def __init__(self, response=None):
        self.response = response or {
            "result_code": "ACCEPTED",
            "result_message": "안내 목적지 좌표를 확인했습니다.",
            "task_id": 3001,
            "task_type": "GUIDE",
            "task_status": "RUNNING",
            "phase": "WAIT_TARGET_TRACKING",
            "guide_phase": "WAIT_TARGET_TRACKING",
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


class FakeGuideCommandLifecycleService:
    def __init__(self, response=None, events=None):
        self.response = response or {
            "accepted": True,
            "result_code": "ACCEPTED",
            "result_message": "안내 제어 명령이 수락되었습니다.",
            "message": "",
            "task_id": 3001,
            "task_status": "RUNNING",
            "phase": "GUIDANCE_RUNNING",
            "guide_phase": "GUIDANCE_RUNNING",
            "assigned_robot_id": "pinky1",
            "target_track_id": 17,
        }
        self.events = events
        self.sent = []

    def send_command(self, **kwargs):
        self.sent.append(kwargs)
        if self.events is not None:
            self.events.append("command")
        return (
            bool(self.response.get("accepted", True)),
            self.response.get("message")
            or self.response.get("result_message")
            or "accepted",
            self.response,
        )

    async def async_send_command(self, **kwargs):
        self.sent.append(kwargs)
        if self.events is not None:
            self.events.append("command")
        return (
            bool(self.response.get("accepted", True)),
            self.response.get("message")
            or self.response.get("result_message")
            or "accepted",
            self.response,
        )


class FakeGuideRuntimePreflight:
    def __init__(self, response=None, events=None):
        self.response = response or {
            "result_code": "ACCEPTED",
            "result_message": "안내 ROS 런타임이 준비되었습니다.",
            "ready": True,
        }
        self.events = events
        self.checked = []

    def check(self, **kwargs):
        self.checked.append(kwargs)
        if self.events is not None:
            self.events.append("preflight")
        return self.response

    async def async_check(self, **kwargs):
        self.checked.append(kwargs)
        if self.events is not None:
            self.events.append("preflight")
        return self.response


class FakeGuideTaskLifecycleRepository:
    def __init__(self):
        self.recorded = []

    def record_command_result(self, **kwargs):
        self.recorded.append(kwargs)
        return {
            "result_code": "REJECTED",
            "result_message": kwargs["command_response"].get("result_message"),
            "reason_code": kwargs["command_response"].get("reason_code"),
            "task_id": int(kwargs["task_id"]),
            "task_status": "RUNNING",
            "phase": kwargs["command_response"].get("phase") or "WAIT_TARGET_TRACKING",
            "guide_phase": kwargs["command_response"].get("guide_phase")
            or kwargs["command_response"].get("phase")
            or "WAIT_TARGET_TRACKING",
            "assigned_robot_id": kwargs["pinky_id"],
            "accepted": False,
        }

    async def async_record_command_result(self, **kwargs):
        self.recorded.append(kwargs)
        return {
            "result_code": "REJECTED",
            "result_message": kwargs["command_response"].get("result_message"),
            "reason_code": kwargs["command_response"].get("reason_code"),
            "task_id": int(kwargs["task_id"]),
            "task_status": "RUNNING",
            "phase": kwargs["command_response"].get("phase") or "WAIT_TARGET_TRACKING",
            "guide_phase": kwargs["command_response"].get("guide_phase")
            or kwargs["command_response"].get("phase")
            or "WAIT_TARGET_TRACKING",
            "assigned_robot_id": kwargs["pinky_id"],
            "accepted": False,
        }


def test_guide_driving_orchestrator_preflights_guide_command_and_sends_start_guidance():
    events = []
    navigation_repository = FakeGuideTaskNavigationRepository()
    guide_runtime_preflight = FakeGuideRuntimePreflight(events=events)
    command_lifecycle_service = FakeGuideCommandLifecycleService(events=events)
    service = GuideDrivingOrchestrator(
        guide_task_navigation_repository=navigation_repository,
        guide_command_lifecycle_service=command_lifecycle_service,
        guide_runtime_preflight=guide_runtime_preflight,
        default_pinky_id="pinky1",
    )

    ok, message, response = service.start_guide_driving(
        task_id=3001,
        target_track_id=17,
    )

    assert ok is True
    assert message == "안내 주행을 시작했습니다."
    assert events == ["preflight", "command"]
    assert navigation_repository.requested == [{"task_id": 3001}]
    assert guide_runtime_preflight.checked == [
        {
            "task_id": 3001,
            "pinky_id": "pinky1",
        }
    ]
    assert command_lifecycle_service.sent == [
        {
            "task_id": 3001,
            "pinky_id": "pinky1",
            "command_type": START_GUIDANCE_COMMAND,
            "target_track_id": 17,
            "destination_id": "delivery_room_301",
            "destination_pose": navigation_repository.response["goal_pose"],
        }
    ]
    assert response["task_status"] == "RUNNING"
    assert response["phase"] == "GUIDANCE_RUNNING"
    assert response["target_track_id"] == 17
    assert "navigation_response" not in response


def test_guide_driving_orchestrator_rejects_when_guide_command_runtime_is_not_ready():
    navigation_repository = FakeGuideTaskNavigationRepository()
    guide_runtime_preflight = FakeGuideRuntimePreflight(
        response={
            "result_code": "REJECTED",
            "result_message": "안내 ROS 런타임이 준비되지 않았습니다.",
            "reason_code": "GUIDE_RUNTIME_NOT_READY",
            "runtime_status": {
                "ready": False,
                "checks": [
                    {
                        "ready": False,
                        "service_name": "/ropi/control/pinky1/guide_command",
                    }
                ],
            },
        }
    )
    lifecycle_repository = FakeGuideTaskLifecycleRepository()
    command_lifecycle_service = FakeGuideCommandLifecycleService()
    service = GuideDrivingOrchestrator(
        guide_task_navigation_repository=navigation_repository,
        guide_task_lifecycle_repository=lifecycle_repository,
        guide_command_lifecycle_service=command_lifecycle_service,
        guide_runtime_preflight=guide_runtime_preflight,
        default_pinky_id="pinky1",
    )

    ok, message, response = service.start_guide_driving(
        task_id=3001,
        target_track_id=17,
    )

    assert ok is False
    assert message == "안내 ROS 런타임이 준비되지 않았습니다."
    assert command_lifecycle_service.sent == []
    assert guide_runtime_preflight.checked == [{"task_id": 3001, "pinky_id": "pinky1"}]
    assert lifecycle_repository.recorded[0]["command_type"] == START_GUIDANCE_COMMAND
    assert lifecycle_repository.recorded[0]["command_response"]["accepted"] is False
    assert lifecycle_repository.recorded[0]["command_response"]["reason_code"] == (
        "GUIDE_RUNTIME_NOT_READY"
    )
    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "GUIDE_RUNTIME_NOT_READY"
    assert response["phase"] == "WAIT_TARGET_TRACKING"
    assert response["guide_phase"] == "WAIT_TARGET_TRACKING"
    assert response["runtime_status"]["checks"][0]["service_name"] == (
        "/ropi/control/pinky1/guide_command"
    )
    assert response["lifecycle_result"]["accepted"] is False
    assert "navigation_response" not in response


def test_guide_driving_orchestrator_returns_start_guidance_rejection_without_navigation():
    navigation_repository = FakeGuideTaskNavigationRepository()
    guide_runtime_preflight = FakeGuideRuntimePreflight()
    command_lifecycle_service = FakeGuideCommandLifecycleService(
        response={
            "accepted": False,
            "result_code": "REJECTED",
            "result_message": "guide command rejected",
            "reason_code": "GUIDE_STATE_MISMATCH",
        }
    )
    service = GuideDrivingOrchestrator(
        guide_task_navigation_repository=navigation_repository,
        guide_command_lifecycle_service=command_lifecycle_service,
        guide_runtime_preflight=guide_runtime_preflight,
        default_pinky_id="pinky1",
    )

    ok, message, response = service.start_guide_driving(
        task_id=3001,
        target_track_id=17,
    )

    assert ok is False
    assert message == "guide command rejected"
    assert (
        command_lifecycle_service.sent[0]["destination_pose"]
        == (navigation_repository.response["goal_pose"])
    )
    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "GUIDE_STATE_MISMATCH"
    assert "navigation_response" not in response


def test_guide_driving_orchestrator_records_context_rejection_as_start_guidance():
    navigation_repository = FakeGuideTaskNavigationRepository(
        response={
            "result_code": "REJECTED",
            "result_message": "안내 주행을 시작할 수 없는 상태입니다.",
            "reason_code": "GUIDE_STATE_MISMATCH",
            "task_id": 3001,
            "task_type": "GUIDE",
            "task_status": "RUNNING",
            "phase": "WAIT_TARGET_TRACKING",
            "guide_phase": "WAIT_TARGET_TRACKING",
            "assigned_robot_id": "pinky1",
            "destination_id": "delivery_room_301",
        }
    )
    lifecycle_repository = FakeGuideTaskLifecycleRepository()
    command_lifecycle_service = FakeGuideCommandLifecycleService()
    guide_runtime_preflight = FakeGuideRuntimePreflight()
    service = GuideDrivingOrchestrator(
        guide_task_navigation_repository=navigation_repository,
        guide_task_lifecycle_repository=lifecycle_repository,
        guide_command_lifecycle_service=command_lifecycle_service,
        guide_runtime_preflight=guide_runtime_preflight,
        default_pinky_id="pinky1",
    )

    ok, message, response = service.start_guide_driving(
        task_id=3001,
        target_track_id=17,
    )

    assert ok is False
    assert message == "안내 주행을 시작할 수 없는 상태입니다."
    assert command_lifecycle_service.sent == []
    assert guide_runtime_preflight.checked == []
    assert lifecycle_repository.recorded == [
        {
            "task_id": 3001,
            "pinky_id": "pinky1",
            "command_type": START_GUIDANCE_COMMAND,
            "target_track_id": 17,
            "wait_timeout_sec": 0,
            "finish_reason": "",
            "command_response": {
                "result_code": "REJECTED",
                "result_message": "안내 주행을 시작할 수 없는 상태입니다.",
                "reason_code": "GUIDE_STATE_MISMATCH",
                "task_id": 3001,
                "task_type": "GUIDE",
                "task_status": "RUNNING",
                "phase": "WAIT_TARGET_TRACKING",
                "guide_phase": "WAIT_TARGET_TRACKING",
                "assigned_robot_id": "pinky1",
                "destination_id": "delivery_room_301",
                "accepted": False,
            },
        }
    ]
    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "GUIDE_STATE_MISMATCH"
    assert response["phase"] == "WAIT_TARGET_TRACKING"
    assert response["guide_phase"] == "WAIT_TARGET_TRACKING"
    assert response["lifecycle_result"]["accepted"] is False


def test_guide_driving_orchestrator_async_preflights_and_sends_start_guidance():
    guide_runtime_preflight = FakeGuideRuntimePreflight()
    command_lifecycle_service = FakeGuideCommandLifecycleService(
        response={
            "accepted": True,
            "result_code": "ACCEPTED",
            "result_message": "안내 제어 명령이 수락되었습니다.",
            "phase": "GUIDANCE_RUNNING",
            "target_track_id": 17,
        }
    )
    service = GuideDrivingOrchestrator(
        guide_task_navigation_repository=FakeGuideTaskNavigationRepository(),
        guide_command_lifecycle_service=command_lifecycle_service,
        guide_runtime_preflight=guide_runtime_preflight,
        default_pinky_id="pinky1",
    )

    ok, message, response = asyncio.run(
        service.async_start_guide_driving(
            task_id=3001,
            target_track_id=17,
        )
    )

    assert ok is True
    assert message == "안내 주행을 시작했습니다."
    assert guide_runtime_preflight.checked == [{"task_id": 3001, "pinky_id": "pinky1"}]
    assert command_lifecycle_service.sent[0]["command_type"] == START_GUIDANCE_COMMAND
    assert command_lifecycle_service.sent[0]["target_track_id"] == 17
    assert command_lifecycle_service.sent[0]["destination_id"] == "delivery_room_301"
    assert response["phase"] == "GUIDANCE_RUNNING"


def test_guide_driving_orchestrator_async_records_context_rejection_as_start_guidance():
    navigation_repository = FakeGuideTaskNavigationRepository(
        response={
            "result_code": "REJECTED",
            "result_message": "안내 목적지 좌표가 설정되어 있지 않습니다.",
            "reason_code": "GUIDE_DESTINATION_NOT_CONFIGURED",
            "task_id": 3001,
            "task_type": "GUIDE",
            "task_status": "RUNNING",
            "phase": "READY_TO_START_GUIDANCE",
            "guide_phase": "READY_TO_START_GUIDANCE",
            "assigned_robot_id": "pinky1",
        }
    )
    lifecycle_repository = FakeGuideTaskLifecycleRepository()
    command_lifecycle_service = FakeGuideCommandLifecycleService()
    guide_runtime_preflight = FakeGuideRuntimePreflight()
    service = GuideDrivingOrchestrator(
        guide_task_navigation_repository=navigation_repository,
        guide_task_lifecycle_repository=lifecycle_repository,
        guide_command_lifecycle_service=command_lifecycle_service,
        guide_runtime_preflight=guide_runtime_preflight,
        default_pinky_id="pinky1",
    )

    ok, message, response = asyncio.run(
        service.async_start_guide_driving(
            task_id=3001,
            target_track_id=17,
        )
    )

    assert ok is False
    assert message == "안내 목적지 좌표가 설정되어 있지 않습니다."
    assert command_lifecycle_service.sent == []
    assert guide_runtime_preflight.checked == []
    assert lifecycle_repository.recorded[0]["command_type"] == START_GUIDANCE_COMMAND
    assert lifecycle_repository.recorded[0]["command_response"]["accepted"] is False
    assert lifecycle_repository.recorded[0]["command_response"]["reason_code"] == (
        "GUIDE_DESTINATION_NOT_CONFIGURED"
    )
    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "GUIDE_DESTINATION_NOT_CONFIGURED"
    assert response["phase"] == "READY_TO_START_GUIDANCE"
    assert response["guide_phase"] == "READY_TO_START_GUIDANCE"
