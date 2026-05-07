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


class FakeGoalPoseNavigationService:
    def __init__(self, response=None, events=None):
        self.response = response or {
            "result_code": "ACCEPTED",
            "navigation_started": True,
            "nav_phase": "GUIDE_DESTINATION",
        }
        self.events = events
        self.navigated = []

    def navigate(self, **kwargs):
        self.navigated.append(kwargs)
        if self.events is not None:
            self.events.append("navigate")
        return self.response

    async def async_navigate(self, **kwargs):
        self.navigated.append(kwargs)
        if self.events is not None:
            self.events.append("navigate")
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
            self.response.get("message") or self.response.get("result_message") or "accepted",
            self.response,
        )

    async def async_send_command(self, **kwargs):
        self.sent.append(kwargs)
        if self.events is not None:
            self.events.append("command")
        return (
            bool(self.response.get("accepted", True)),
            self.response.get("message") or self.response.get("result_message") or "accepted",
            self.response,
        )


class FakeGuideTaskLifecycleRepository:
    def __init__(self):
        self.recorded = []

    def record_command_result(self, **kwargs):
        self.recorded.append(kwargs)
        return {
            "result_code": "REJECTED",
            "task_id": int(kwargs["task_id"]),
            "task_status": "RUNNING",
            "phase": "WAIT_TARGET_TRACKING",
            "guide_phase": "WAIT_TARGET_TRACKING",
            "assigned_robot_id": kwargs["pinky_id"],
            "accepted": False,
        }

    async def async_record_command_result(self, **kwargs):
        self.recorded.append(kwargs)
        return {
            "result_code": "REJECTED",
            "task_id": int(kwargs["task_id"]),
            "task_status": "RUNNING",
            "phase": "WAIT_TARGET_TRACKING",
            "guide_phase": "WAIT_TARGET_TRACKING",
            "assigned_robot_id": kwargs["pinky_id"],
            "accepted": False,
        }


def test_guide_driving_orchestrator_sends_start_guidance_without_destination_navigation():
    events = []
    navigation_repository = FakeGuideTaskNavigationRepository()
    navigation_service = FakeGoalPoseNavigationService(events=events)
    command_lifecycle_service = FakeGuideCommandLifecycleService(events=events)
    service = GuideDrivingOrchestrator(
        guide_task_navigation_repository=navigation_repository,
        guide_command_lifecycle_service=command_lifecycle_service,
        goal_pose_navigation_service=navigation_service,
        default_pinky_id="pinky1",
    )

    ok, message, response = service.start_guide_driving(
        task_id=3001,
        target_track_id=17,
        navigation_timeout_sec=42,
    )

    assert ok is True
    assert message == "안내 주행을 시작했습니다."
    assert events == ["command"]
    assert navigation_repository.requested == [{"task_id": 3001}]
    assert navigation_service.navigated == []
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


def test_guide_driving_orchestrator_returns_start_guidance_rejection_without_navigation():
    navigation_repository = FakeGuideTaskNavigationRepository()
    navigation_service = FakeGoalPoseNavigationService()
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
        goal_pose_navigation_service=navigation_service,
        default_pinky_id="pinky1",
    )

    ok, message, response = service.start_guide_driving(
        task_id=3001,
        target_track_id=17,
    )

    assert ok is False
    assert message == "guide command rejected"
    assert navigation_service.navigated == []
    assert command_lifecycle_service.sent[0]["destination_pose"] == (
        navigation_repository.response["goal_pose"]
    )
    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "GUIDE_STATE_MISMATCH"
    assert "navigation_response" not in response


def test_guide_driving_orchestrator_async_sends_start_guidance_without_destination_navigation():
    navigation_service = FakeGoalPoseNavigationService()
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
        goal_pose_navigation_service=navigation_service,
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
    assert navigation_service.navigated == []
    assert command_lifecycle_service.sent[0]["command_type"] == START_GUIDANCE_COMMAND
    assert command_lifecycle_service.sent[0]["target_track_id"] == 17
    assert command_lifecycle_service.sent[0]["destination_id"] == "delivery_room_301"
    assert response["phase"] == "GUIDANCE_RUNNING"
