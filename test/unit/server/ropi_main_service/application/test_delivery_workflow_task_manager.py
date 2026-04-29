import asyncio

from server.ropi_main_service.application.delivery_workflow_task_manager import (
    DeliveryWorkflowTaskManager,
)
from server.ropi_main_service.application.workflow_task_manager import WorkflowTaskManager


def test_delivery_workflow_task_manager_is_backward_compatible_alias():
    assert DeliveryWorkflowTaskManager is WorkflowTaskManager


def test_delivery_workflow_task_manager_tracks_and_drains_tasks():
    events = []

    async def scenario():
        manager = DeliveryWorkflowTaskManager()

        async def worker():
            await asyncio.sleep(0)
            events.append("worker_done")
            return "ok"

        task = manager.create_task(worker(), name="test_delivery_workflow")

        assert manager.pending_count == 1
        assert await task == "ok"
        await manager.join(timeout_sec=1)

        assert manager.pending_count == 0

    asyncio.run(scenario())

    assert events == ["worker_done"]


def test_delivery_workflow_task_manager_shutdown_cancels_running_tasks():
    events = []

    async def scenario():
        manager = DeliveryWorkflowTaskManager()

        async def worker():
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                events.append("worker_cancelled")
                raise

        manager.create_task(worker(), name="test_delivery_workflow")
        await asyncio.sleep(0)

        await manager.shutdown(timeout_sec=1)

        assert manager.pending_count == 0

    asyncio.run(scenario())

    assert events == ["worker_cancelled"]


def test_delivery_workflow_task_manager_shutdown_drains_protected_tasks_without_cancelling():
    events = []

    async def scenario():
        manager = DeliveryWorkflowTaskManager()
        release = asyncio.Event()

        async def worker():
            await release.wait()
            events.append("worker_done")

        manager.create_task(
            worker(),
            name="test_delivery_result_record",
            cancel_on_shutdown=False,
        )
        await asyncio.sleep(0)

        shutdown_task = asyncio.create_task(manager.shutdown(timeout_sec=1))
        await asyncio.sleep(0)

        assert events == []
        release.set()
        await shutdown_task

        assert manager.pending_count == 0

    asyncio.run(scenario())

    assert events == ["worker_done"]
