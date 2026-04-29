import asyncio
import logging

from server.ropi_main_service.application.delivery_workflow_task_manager import (
    get_default_delivery_workflow_task_manager,
)
from server.ropi_main_service.application.patrol_orchestrator import PatrolOrchestrator
from server.ropi_main_service.application.task_request import DeliveryRequestService
from server.ropi_main_service.observability import log_event
from server.ropi_main_service.persistence.repositories.patrol_task_execution_repository import (
    PatrolTaskExecutionRepository,
)
from server.ropi_main_service.persistence.repositories.task_request_repository import (
    DeliveryRequestRepository,
)


logger = logging.getLogger(__name__)


def _normalize_workflow_response(result):
    if isinstance(result, dict):
        return result
    return {
        "result_code": "FAILED",
        "result_message": f"patrol workflow returned non-dict result: {result!r}",
        "reason_code": "WORKFLOW_RESULT_INVALID",
    }


def build_patrol_request_service(
    *,
    loop=None,
    workflow_task_manager=None,
    patrol_execution_repository=None,
    patrol_orchestrator=None,
) -> DeliveryRequestService:
    task_request_repository = DeliveryRequestRepository()
    patrol_workflow_starter = None

    if loop is not None:
        workflow_task_manager = workflow_task_manager or get_default_delivery_workflow_task_manager()
        patrol_execution_repository = patrol_execution_repository or PatrolTaskExecutionRepository()
        patrol_orchestrator = patrol_orchestrator or PatrolOrchestrator()

        async def _run_patrol_workflow(*, task_id):
            snapshot = await patrol_execution_repository.async_get_patrol_execution_snapshot(task_id)
            if snapshot is None:
                return {
                    "result_code": "FAILED",
                    "result_message": "순찰 task 실행 정보를 찾을 수 없습니다.",
                    "reason_code": "PATROL_TASK_NOT_FOUND",
                }

            return await patrol_orchestrator.async_run(
                task_id=str(task_id),
                path_snapshot_json=snapshot["path_snapshot_json"],
            )

        def _start_patrol_workflow(**kwargs):
            task_id = str(kwargs.get("task_id") or "").strip()
            background_task = workflow_task_manager.create_task(
                _run_patrol_workflow(task_id=task_id),
                name=f"patrol_workflow_{task_id}",
                loop=loop,
                cancel_on_shutdown=True,
            )

            def _handle_background_task_done(task: asyncio.Task):
                try:
                    result = _normalize_workflow_response(task.result())
                except asyncio.CancelledError:
                    result = {
                        "result_code": "FAILED",
                        "result_message": "patrol workflow background task was cancelled.",
                        "reason_code": "WORKFLOW_TASK_CANCELLED",
                    }
                except Exception as exc:
                    logger.exception("patrol workflow background task failed", extra={"task_id": task_id})
                    result = {
                        "result_code": "FAILED",
                        "result_message": f"patrol workflow background task failed: {exc}",
                        "reason_code": "WORKFLOW_UNHANDLED_EXCEPTION",
                    }

                level = logging.INFO if str(result.get("result_code") or "").upper() == "SUCCESS" else logging.WARNING
                log_event(
                    logger,
                    level,
                    "patrol_workflow_background_finished",
                    task_id=task_id,
                    result_code=result.get("result_code"),
                    result_message=result.get("result_message"),
                    reason_code=result.get("reason_code"),
                )

            background_task.add_done_callback(_handle_background_task_done)

        patrol_workflow_starter = _start_patrol_workflow

    return DeliveryRequestService(
        repository=task_request_repository,
        patrol_workflow_starter=patrol_workflow_starter,
    )


__all__ = ["build_patrol_request_service"]
