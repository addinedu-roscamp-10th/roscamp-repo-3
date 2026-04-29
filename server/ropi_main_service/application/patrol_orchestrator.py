import asyncio
import inspect
import logging
import time

from server.ropi_main_service.application.patrol_config import get_patrol_runtime_config
from server.ropi_main_service.application.patrol_path_execution import PatrolPathExecutionService
from server.ropi_main_service.observability import log_event


logger = logging.getLogger(__name__)


class PatrolOrchestrator:
    def __init__(
        self,
        *,
        patrol_path_execution_service=None,
        runtime_config=None,
        patrol_timeout_sec=None,
    ):
        self.runtime_config = runtime_config or get_patrol_runtime_config()
        self.patrol_path_execution_service = patrol_path_execution_service or PatrolPathExecutionService(
            runtime_config=self.runtime_config,
        )
        self.patrol_timeout_sec = (
            self.runtime_config.patrol_timeout_sec
            if patrol_timeout_sec is None
            else patrol_timeout_sec
        )

    def run(self, *, task_id, path_snapshot_json):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.async_run(
                    task_id=task_id,
                    path_snapshot_json=path_snapshot_json,
                )
            )
        raise RuntimeError("PatrolOrchestrator.run() cannot be called from a running event loop; use async_run().")

    async def async_run(self, *, task_id, path_snapshot_json):
        started_at = time.monotonic()
        log_event(logger, logging.INFO, "patrol_workflow_started", task_id=task_id)
        response = await self._async_execute(
            task_id=task_id,
            path_snapshot_json=path_snapshot_json,
            timeout_sec=self.patrol_timeout_sec,
        )
        level = logging.INFO if self._is_success(response) else logging.WARNING
        log_event(
            logger,
            level,
            "patrol_workflow_finished",
            task_id=task_id,
            result_code=(response or {}).get("result_code"),
            result_message=(response or {}).get("result_message"),
            reason_code=(response or {}).get("reason_code"),
            elapsed_ms=round((time.monotonic() - started_at) * 1000, 2),
        )
        return response

    async def _async_execute(self, **kwargs):
        async_execute = getattr(self.patrol_path_execution_service, "async_execute", None)
        if async_execute is not None:
            return await self._await_if_needed(async_execute(**kwargs))
        return await asyncio.to_thread(self.patrol_path_execution_service.execute, **kwargs)

    @staticmethod
    def _is_success(response):
        return str((response or {}).get("result_code") or "").upper() == "SUCCESS"

    @staticmethod
    async def _await_if_needed(value):
        if inspect.isawaitable(value):
            return await value
        return value


__all__ = ["PatrolOrchestrator"]
