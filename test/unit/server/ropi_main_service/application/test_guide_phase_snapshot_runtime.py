import asyncio

from server.ropi_main_service.application.guide_phase_snapshot_runtime import (
    GuidePhaseSnapshotRuntimePoller,
    start_guide_phase_snapshot_polling_if_enabled,
)


class FakeRuntimeService:
    def __init__(self, *statuses):
        self.statuses = list(statuses)
        self.calls = []

    async def async_get_status(self, *, pinky_id=None):
        self.calls.append(pinky_id)
        if self.statuses:
            return self.statuses.pop(0)
        return {}


class FakeProcessor:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.snapshots = []

    async def async_process(self, snapshot):
        self.snapshots.append(snapshot)
        if self.responses:
            return self.responses.pop(0)
        return {"result_code": "IGNORED", "reason_code": "NO_RESPONSE"}


class FakeTaskUpdatePublisher:
    def __init__(self):
        self.published = []

    async def publish_from_response(self, response, *, source, task_type=None):
        self.published.append((response, source, task_type))


class FakeWorkflowTaskManager:
    def __init__(self):
        self.created = []

    def create_task(self, coro, *, name, loop=None, cancel_on_shutdown=True):
        coro.close()
        record = {
            "name": name,
            "loop": loop,
            "cancel_on_shutdown": cancel_on_shutdown,
        }
        self.created.append(record)
        return record


def test_poll_once_processes_latest_guide_phase_snapshot_and_publishes_update():
    runtime_service = FakeRuntimeService(
        {
            "guide_runtime": {
                "pinky_id": "pinky1",
                "connected": True,
                "stale": False,
                "last_update": {
                    "task_id": "3001",
                    "pinky_id": "pinky1",
                    "guide_phase": "WAIT_REIDENTIFY",
                    "target_track_id": 17,
                    "reason_code": "TARGET_LOST",
                    "seq": 12,
                    "occurred_at_sec": 1778123400,
                    "occurred_at_nanosec": 120000000,
                },
            }
        }
    )
    processor = FakeProcessor(
        {
            "result_code": "ACCEPTED",
            "result_message": "안내 runtime phase snapshot을 반영했습니다.",
            "task_id": 3001,
            "task_type": "GUIDE",
            "task_status": "RUNNING",
            "phase": "WAIT_REIDENTIFY",
            "assigned_robot_id": "pinky1",
            "guide_phase": "WAIT_REIDENTIFY",
            "target_track_id": 17,
        }
    )
    publisher = FakeTaskUpdatePublisher()
    poller = GuidePhaseSnapshotRuntimePoller(
        runtime_service=runtime_service,
        processor=processor,
        task_update_publisher=publisher,
        pinky_id="pinky1",
        poll_interval_sec=0.01,
    )

    response = asyncio.run(poller.poll_once())

    assert response["result_code"] == "ACCEPTED"
    assert runtime_service.calls == ["pinky1"]
    assert processor.snapshots == [
        {
            "task_id": "3001",
            "pinky_id": "pinky1",
            "guide_phase": "WAIT_REIDENTIFY",
            "target_track_id": 17,
            "reason_code": "TARGET_LOST",
            "seq": 12,
            "occurred_at": {
                "sec": 1778123400,
                "nanosec": 120000000,
            },
        }
    ]
    assert publisher.published == [
        (response, "GUIDE_PHASE_SNAPSHOT", "GUIDE")
    ]


def test_poll_once_skips_when_runtime_status_has_no_snapshot():
    runtime_service = FakeRuntimeService(
        {
            "guide_runtime": {
                "pinky_id": "pinky1",
                "connected": False,
                "stale": True,
                "last_update": None,
            }
        }
    )
    processor = FakeProcessor()
    publisher = FakeTaskUpdatePublisher()
    poller = GuidePhaseSnapshotRuntimePoller(
        runtime_service=runtime_service,
        processor=processor,
        task_update_publisher=publisher,
        pinky_id="pinky1",
    )

    response = asyncio.run(poller.poll_once())

    assert response == {
        "result_code": "IGNORED",
        "reason_code": "GUIDE_PHASE_SNAPSHOT_MISSING",
        "result_message": "guide runtime snapshot is not available.",
    }
    assert processor.snapshots == []
    assert publisher.published == []


def test_poll_once_does_not_publish_ignored_processor_response():
    runtime_service = FakeRuntimeService(
        {
            "guide_runtime": {
                "last_update": {
                    "task_id": "3001",
                    "pinky_id": "pinky1",
                    "guide_phase": "GUIDANCE_RUNNING",
                    "target_track_id": 17,
                    "seq": 4,
                }
            }
        }
    )
    processor = FakeProcessor(
        {
            "result_code": "IGNORED",
            "reason_code": "STALE_GUIDE_PHASE_SNAPSHOT",
            "task_id": "3001",
        }
    )
    publisher = FakeTaskUpdatePublisher()
    poller = GuidePhaseSnapshotRuntimePoller(
        runtime_service=runtime_service,
        processor=processor,
        task_update_publisher=publisher,
        pinky_id="pinky1",
    )

    response = asyncio.run(poller.poll_once())

    assert response["result_code"] == "IGNORED"
    assert processor.snapshots[0]["seq"] == 4
    assert publisher.published == []


def test_start_guide_phase_snapshot_polling_creates_background_task_by_default(
    monkeypatch,
):
    monkeypatch.delenv("GUIDE_PHASE_SNAPSHOT_POLL_ENABLED", raising=False)
    manager = FakeWorkflowTaskManager()

    task = start_guide_phase_snapshot_polling_if_enabled(
        workflow_task_manager=manager,
        runtime_service=FakeRuntimeService(),
        processor=FakeProcessor(),
        task_update_publisher=FakeTaskUpdatePublisher(),
        poll_interval_sec=0.01,
    )

    assert task == {
        "name": "guide_phase_snapshot_poll",
        "loop": None,
        "cancel_on_shutdown": True,
    }
    assert manager.created == [task]


def test_start_guide_phase_snapshot_polling_can_be_disabled(monkeypatch):
    monkeypatch.setenv("GUIDE_PHASE_SNAPSHOT_POLL_ENABLED", "false")
    manager = FakeWorkflowTaskManager()

    task = start_guide_phase_snapshot_polling_if_enabled(
        workflow_task_manager=manager,
        runtime_service=FakeRuntimeService(),
        processor=FakeProcessor(),
        task_update_publisher=FakeTaskUpdatePublisher(),
    )

    assert task is None
    assert manager.created == []
