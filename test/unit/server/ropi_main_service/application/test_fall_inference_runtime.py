import asyncio

from server.ropi_main_service.application.fall_inference_runtime import (
    start_fall_inference_stream_if_enabled,
)


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


class FakeClient:
    def __init__(self):
        self.handlers = []

    async def run_forever(self, handler):
        self.handlers.append(handler)


class FakeProcessor:
    async def async_process_batch(self, batch):
        return {"processed_count": 0}


def test_start_fall_inference_stream_returns_none_when_disabled(monkeypatch):
    monkeypatch.delenv("AI_FALL_STREAM_ENABLED", raising=False)
    manager = FakeWorkflowTaskManager()

    async def scenario():
        return start_fall_inference_stream_if_enabled(
            workflow_task_manager=manager,
            client=FakeClient(),
            processor=FakeProcessor(),
        )

    task = asyncio.run(scenario())

    assert task is None
    assert manager.created == []


def test_start_fall_inference_stream_creates_background_task_when_enabled(monkeypatch):
    monkeypatch.setenv("AI_FALL_STREAM_ENABLED", "true")
    manager = FakeWorkflowTaskManager()

    async def scenario():
        return start_fall_inference_stream_if_enabled(
            workflow_task_manager=manager,
            client=FakeClient(),
            processor=FakeProcessor(),
        )

    task = asyncio.run(scenario())

    assert task == {
        "name": "fall_inference_stream",
        "loop": None,
        "cancel_on_shutdown": True,
    }
    assert manager.created == [task]
