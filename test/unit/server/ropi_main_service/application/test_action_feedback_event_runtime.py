import asyncio

import pytest

from server.ropi_main_service.application.action_feedback_event_runtime import (
    ActionFeedbackEventRuntime,
    start_action_feedback_event_polling_if_enabled,
)


class FakeTaskMonitorService:
    def __init__(self, tasks):
        self.tasks = tasks
        self.calls = []

    async def async_get_task_monitor_snapshot(self, **kwargs):
        self.calls.append(kwargs)
        return {"tasks": self.tasks}


class FakeActionFeedbackService:
    def __init__(self, responses=None, *, exception=None):
        self.responses = list(responses or [])
        self.exception = exception
        self.calls = []

    async def async_get_latest_feedback(self, **kwargs):
        self.calls.append(kwargs)
        if self.exception is not None:
            raise self.exception
        if self.responses:
            return self.responses.pop(0)
        return {"result_code": "NOT_FOUND", "feedback": []}


class FakeTaskEventPublisher:
    def __init__(self):
        self.events = []

    async def publish(self, event_type, payload):
        self.events.append((event_type, payload))
        return {"event_type": event_type, "payload": payload}


class FakeWorkflowTaskManager:
    def __init__(self):
        self.created = []

    def create_task(self, coroutine, **kwargs):
        coroutine.close()
        task = {**kwargs}
        self.created.append(task)
        return task


def test_poll_once_publishes_new_patrol_feedback_event():
    task_monitor = FakeTaskMonitorService(
        tasks=[
            {
                "task_id": 467,
                "task_type": "PATROL",
                "task_status": "RUNNING",
            }
        ]
    )
    feedback_service = FakeActionFeedbackService(
        responses=[
            {
                "result_code": "FOUND",
                "task_id": "467",
                "feedback": [
                    {
                        "client": "patrol",
                        "task_id": "467",
                        "action_name": "/ropi/control/pinky3/execute_patrol_path",
                        "action_type": "EXECUTE_PATROL_PATH",
                        "feedback_type": "PATROL_FEEDBACK",
                        "received_at": "2026-05-07T11:03:39+00:00",
                        "payload": {
                            "patrol_status": "MOVING",
                            "current_waypoint_index": 1,
                            "total_waypoints": 3,
                            "distance_remaining_m": 1.25,
                            "current_pose": {
                                "header": {"frame_id": "map"},
                                "pose": {
                                    "position": {"x": 0.5, "y": -0.2, "z": 0.0},
                                    "orientation": {
                                        "x": 0.0,
                                        "y": 0.0,
                                        "z": 0.0,
                                        "w": 1.0,
                                    },
                                },
                            },
                        },
                    }
                ],
            }
        ]
    )
    publisher = FakeTaskEventPublisher()
    runtime = ActionFeedbackEventRuntime(
        task_monitor_service=task_monitor,
        feedback_service=feedback_service,
        task_event_publisher=publisher,
    )

    response = asyncio.run(runtime.poll_once())

    assert response["result_code"] == "ACCEPTED"
    assert response["active_task_count"] == 1
    assert response["published_count"] == 1
    assert feedback_service.calls == [{"task_id": 467}]
    assert publisher.events == [
        (
            "ACTION_FEEDBACK_UPDATED",
            {
                "task_id": 467,
                "action_name": "/ropi/control/pinky3/execute_patrol_path",
                "action_type": "EXECUTE_PATROL_PATH",
                "feedback_type": "PATROL_FEEDBACK",
                "feedback_summary": "MOVING / 남은 거리 1.25m",
                "pose": {"x": 0.5, "y": -0.2, "yaw": 0.0, "frame_id": "map"},
                "current_pose": {
                    "x": 0.5,
                    "y": -0.2,
                    "yaw": 0.0,
                    "frame_id": "map",
                },
                "patrol_status": "MOVING",
                "current_waypoint_index": 1,
                "total_waypoints": 3,
                "distance_remaining_m": 1.25,
                "received_at": "2026-05-07T11:03:39+00:00",
                "payload": {
                    "patrol_status": "MOVING",
                    "current_waypoint_index": 1,
                    "total_waypoints": 3,
                    "distance_remaining_m": 1.25,
                    "current_pose": {
                        "header": {"frame_id": "map"},
                        "pose": {
                            "position": {"x": 0.5, "y": -0.2, "z": 0.0},
                            "orientation": {
                                "x": 0.0,
                                "y": 0.0,
                                "z": 0.0,
                                "w": 1.0,
                            },
                        },
                    },
                },
            },
        )
    ]


def test_poll_once_deduplicates_same_feedback_record():
    feedback_record = {
        "client": "navigation",
        "task_id": "10",
        "action_name": "/ropi/control/pinky2/navigate_to_goal",
        "feedback_type": "NAVIGATION_FEEDBACK",
        "received_at": "2026-05-07T12:00:00+00:00",
        "payload": {
            "nav_status": "MOVING",
            "distance_remaining_m": 0.4,
        },
    }
    feedback_service = FakeActionFeedbackService(
        responses=[
            {"result_code": "FOUND", "task_id": "10", "feedback": [feedback_record]},
            {"result_code": "FOUND", "task_id": "10", "feedback": [feedback_record]},
        ]
    )
    publisher = FakeTaskEventPublisher()
    runtime = ActionFeedbackEventRuntime(
        task_monitor_service=FakeTaskMonitorService(tasks=[{"task_id": 10}]),
        feedback_service=feedback_service,
        task_event_publisher=publisher,
    )

    first = asyncio.run(runtime.poll_once())
    second = asyncio.run(runtime.poll_once())

    assert first["published_count"] == 1
    assert second["published_count"] == 0
    assert len(publisher.events) == 1


def test_poll_once_skips_when_there_are_no_active_tasks():
    feedback_service = FakeActionFeedbackService()
    runtime = ActionFeedbackEventRuntime(
        task_monitor_service=FakeTaskMonitorService(tasks=[]),
        feedback_service=feedback_service,
        task_event_publisher=FakeTaskEventPublisher(),
    )

    response = asyncio.run(runtime.poll_once())

    assert response == {
        "result_code": "ACCEPTED",
        "active_task_count": 0,
        "published_count": 0,
    }
    assert feedback_service.calls == []


def test_poll_once_continues_when_feedback_transport_fails(caplog):
    runtime = ActionFeedbackEventRuntime(
        task_monitor_service=FakeTaskMonitorService(tasks=[{"task_id": 55}]),
        feedback_service=FakeActionFeedbackService(exception=RuntimeError("UDS down")),
        task_event_publisher=FakeTaskEventPublisher(),
    )

    response = asyncio.run(runtime.poll_once())

    assert response == {
        "result_code": "ACCEPTED",
        "active_task_count": 1,
        "published_count": 0,
    }
    assert "action feedback polling failed task_id=55" in caplog.text


def test_start_action_feedback_event_polling_creates_background_task_by_default(
    monkeypatch,
):
    monkeypatch.delenv("ACTION_FEEDBACK_EVENT_POLL_ENABLED", raising=False)
    manager = FakeWorkflowTaskManager()

    task = start_action_feedback_event_polling_if_enabled(
        workflow_task_manager=manager,
        task_monitor_service=FakeTaskMonitorService(tasks=[]),
        feedback_service=FakeActionFeedbackService(),
        task_event_publisher=FakeTaskEventPublisher(),
        poll_interval_sec=0.01,
    )

    assert task == {
        "name": "action_feedback_event_poll",
        "loop": None,
        "cancel_on_shutdown": True,
    }
    assert manager.created == [task]


@pytest.mark.parametrize("raw", ["false", "0", "no", "off", "disabled"])
def test_start_action_feedback_event_polling_can_be_disabled(monkeypatch, raw):
    monkeypatch.setenv("ACTION_FEEDBACK_EVENT_POLL_ENABLED", raw)

    task = start_action_feedback_event_polling_if_enabled(
        workflow_task_manager=FakeWorkflowTaskManager(),
        task_monitor_service=FakeTaskMonitorService(tasks=[]),
        feedback_service=FakeActionFeedbackService(),
        task_event_publisher=FakeTaskEventPublisher(),
    )

    assert task is None
