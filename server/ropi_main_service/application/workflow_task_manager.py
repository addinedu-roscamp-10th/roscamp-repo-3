import asyncio
import logging


logger = logging.getLogger(__name__)
_default_workflow_task_manager = None


class WorkflowTaskManager:
    def __init__(self):
        self._tasks = set()
        self._cancel_on_shutdown_tasks = set()

    @property
    def pending_count(self) -> int:
        return len(self._tasks)

    def create_task(
        self,
        coro,
        *,
        name: str | None = None,
        loop=None,
        cancel_on_shutdown: bool = True,
    ) -> asyncio.Task:
        target_loop = loop or asyncio.get_running_loop()
        task = target_loop.create_task(coro, name=name)
        return self.track(task, cancel_on_shutdown=cancel_on_shutdown)

    def track(self, task: asyncio.Task, *, cancel_on_shutdown: bool = True) -> asyncio.Task:
        self._tasks.add(task)
        if cancel_on_shutdown:
            self._cancel_on_shutdown_tasks.add(task)
        task.add_done_callback(self._discard_task)
        return task

    def _discard_task(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        self._cancel_on_shutdown_tasks.discard(task)

    async def join(self, *, timeout_sec: float | None = None) -> None:
        loop = asyncio.get_running_loop()
        deadline = None if timeout_sec is None else loop.time() + timeout_sec

        while self._tasks:
            wait_timeout = None
            if deadline is not None:
                wait_timeout = max(0.0, deadline - loop.time())
                if wait_timeout == 0.0:
                    raise TimeoutError("workflow background tasks did not finish before timeout")

            _, pending = await asyncio.wait(set(self._tasks), timeout=wait_timeout)
            await asyncio.sleep(0)

            if pending and deadline is not None and loop.time() >= deadline:
                raise TimeoutError("workflow background tasks did not finish before timeout")

    async def shutdown(self, *, timeout_sec: float = 5.0, cancel_running: bool = True) -> None:
        if cancel_running:
            for task in tuple(self._cancel_on_shutdown_tasks):
                if not task.done():
                    task.cancel()

        try:
            await self.join(timeout_sec=timeout_sec)
        except TimeoutError:
            logger.warning(
                "workflow background task shutdown timed out",
                extra={"pending_count": self.pending_count},
            )


def get_default_workflow_task_manager() -> WorkflowTaskManager:
    global _default_workflow_task_manager

    if _default_workflow_task_manager is None:
        _default_workflow_task_manager = WorkflowTaskManager()

    return _default_workflow_task_manager


__all__ = [
    "WorkflowTaskManager",
    "get_default_workflow_task_manager",
]
