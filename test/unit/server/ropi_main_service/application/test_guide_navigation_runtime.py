import asyncio

from server.ropi_main_service.application.guide_navigation_runtime import (
    GUIDE_DESTINATION_NAV_PHASE,
    GuideNavigationRuntimeStarter,
)


class FakeReadinessService:
    def __init__(self, *, response, calls):
        self.response = response
        self.calls = calls

    def get_status(self):
        return self.response


class FakeNavigationService:
    def __init__(self, *, calls, events):
        self.calls = calls
        self.events = events

    async def async_navigate(self, **kwargs):
        self.events.append("navigate")
        self.calls.append(kwargs)
        return {"result_code": "SUCCESS", **kwargs}


class FakeTask:
    def __init__(self):
        self.callback = None

    def add_done_callback(self, callback):
        self.callback = callback


class FakeWorkflowTaskManager:
    def __init__(self, *, events):
        self.events = events
        self.queued = []

    def create_task(self, coro, **kwargs):
        self.events.append("queue")
        self.queued.append(kwargs)
        coro.close()
        return FakeTask()


def test_guide_navigation_runtime_rejects_when_guide_runtime_is_not_ready():
    readiness_calls = []
    events = []
    workflow_task_manager = FakeWorkflowTaskManager(events=events)

    def readiness_service_factory(**kwargs):
        readiness_calls.append(kwargs)
        return FakeReadinessService(
            response={
                "ready": False,
                "checks": [
                    {
                        "ready": True,
                        "action_name": "/ropi/control/pinky1/navigate_to_goal",
                    },
                    {
                        "ready": False,
                        "service_name": "/ropi/control/pinky1/guide_command",
                    },
                ],
            },
            calls=readiness_calls,
        )

    async def scenario():
        starter = GuideNavigationRuntimeStarter(
            workflow_task_manager=workflow_task_manager,
            readiness_service_factory=readiness_service_factory,
        )
        return starter.start_destination_navigation(
            task_id="3001",
            pinky_id="pinky1",
            goal_pose={"pose": {"position": {"x": 1.0}}},
            timeout_sec=3,
        )

    response = asyncio.run(scenario())

    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "GUIDE_RUNTIME_NOT_READY"
    assert response["navigation_started"] is False
    assert response["task_id"] == "3001"
    assert response["pinky_id"] == "pinky1"
    assert response["nav_phase"] == GUIDE_DESTINATION_NAV_PHASE
    assert workflow_task_manager.queued == []
    assert readiness_calls[0]["include_guide"] is True
    assert readiness_calls[0]["arm_ids"] == []


def test_guide_navigation_runtime_preflights_before_queueing_background_navigation():
    readiness_calls = []
    navigation_calls = []
    events = []
    workflow_task_manager = FakeWorkflowTaskManager(events=events)

    def readiness_service_factory(**kwargs):
        events.append("readiness")
        readiness_calls.append(kwargs)
        return FakeReadinessService(
            response={
                "ready": True,
                "checks": [
                    {
                        "ready": True,
                        "action_name": "/ropi/control/pinky1/navigate_to_goal",
                    },
                    {
                        "ready": True,
                        "service_name": "/ropi/control/pinky1/guide_command",
                    },
                ],
            },
            calls=readiness_calls,
        )

    def navigation_service_factory(**kwargs):
        navigation_calls.append(kwargs)
        return FakeNavigationService(calls=[], events=events)

    async def scenario():
        starter = GuideNavigationRuntimeStarter(
            workflow_task_manager=workflow_task_manager,
            readiness_service_factory=readiness_service_factory,
            navigation_service_factory=navigation_service_factory,
        )
        return starter.start_destination_navigation(
            task_id="3001",
            pinky_id="pinky1",
            goal_pose={"pose": {"position": {"x": 1.0}}},
            timeout_sec=3,
        )

    response = asyncio.run(scenario())

    assert response["result_code"] == "ACCEPTED"
    assert response["navigation_started"] is True
    assert response["task_id"] == "3001"
    assert response["pinky_id"] == "pinky1"
    assert response["nav_phase"] == GUIDE_DESTINATION_NAV_PHASE
    assert events == ["readiness", "queue"]
    assert workflow_task_manager.queued[0]["name"] == "guide_destination_navigation_3001"
    assert workflow_task_manager.queued[0]["cancel_on_shutdown"] is True
    assert readiness_calls[0]["include_guide"] is True
    assert readiness_calls[0]["arm_ids"] == []
    assert navigation_calls[0]["runtime_config"].pinky_id == "pinky1"
