import asyncio
import logging

from server.ropi_main_service.application.workflow_task_manager import (
    get_default_workflow_task_manager,
)
from server.ropi_main_service.application.patrol_orchestrator import PatrolOrchestrator
from server.ropi_main_service.application.patrol_config import get_patrol_runtime_config
from server.ropi_main_service.application.runtime_readiness import RosRuntimeReadinessService
from server.ropi_main_service.application.task_request import TaskRequestService
from server.ropi_main_service.observability import log_event
from server.ropi_main_service.persistence.repositories.patrol_task_execution_repository import (
    PatrolTaskExecutionRepository,
)
from server.ropi_main_service.persistence.repositories.task_request_repository import (
    TaskRequestRepository,
)


DeliveryRequestService = TaskRequestService
DeliveryRequestRepository = TaskRequestRepository
_DEFAULT_TASK_REQUEST_REPOSITORY = TaskRequestRepository
logger = logging.getLogger(__name__)


def _build_patrol_request_precheck(*, runtime_config):
    def _precheck(**_kwargs):
        try:
            ros_status = RosRuntimeReadinessService(
                runtime_config=runtime_config,
                arm_ids=[],
                include_navigation=False,
                include_patrol=True,
            ).get_status()
        except Exception as exc:
            return _build_patrol_runtime_rejection(
                runtime_config=runtime_config,
                reason_code="PATROL_PATH_SERVICE_UNAVAILABLE",
                message=f"순찰 ROS service가 준비되지 않았습니다: {exc}",
            )

        if not _patrol_runtime_ready(ros_status, runtime_config=runtime_config):
            return _build_patrol_runtime_rejection(
                runtime_config=runtime_config,
                reason_code="PATROL_RUNTIME_NOT_READY",
                message="순찰 ROS runtime이 준비되지 않았습니다.",
                ros_detail=ros_status,
            )

        return None

    return _precheck


def _build_async_patrol_request_precheck(*, runtime_config):
    async def _async_precheck(**_kwargs):
        try:
            ros_status = await RosRuntimeReadinessService(
                runtime_config=runtime_config,
                arm_ids=[],
                include_navigation=False,
                include_patrol=True,
            ).async_get_status()
        except Exception as exc:
            return _build_patrol_runtime_rejection(
                runtime_config=runtime_config,
                reason_code="PATROL_PATH_SERVICE_UNAVAILABLE",
                message=f"순찰 ROS service가 준비되지 않았습니다: {exc}",
            )

        if not _patrol_runtime_ready(ros_status, runtime_config=runtime_config):
            return _build_patrol_runtime_rejection(
                runtime_config=runtime_config,
                reason_code="PATROL_RUNTIME_NOT_READY",
                message="순찰 ROS runtime이 준비되지 않았습니다.",
                ros_detail=ros_status,
            )

        return None

    return _async_precheck


def _patrol_runtime_ready(ros_status, *, runtime_config):
    if not isinstance(ros_status, dict):
        return False

    checks = ros_status.get("checks")
    if not isinstance(checks, list):
        return False

    required_endpoint = f"/ropi/control/{runtime_config.pinky_id}/execute_patrol_path"
    for check in checks:
        if not isinstance(check, dict):
            continue
        if check.get("action_name") != required_endpoint:
            continue
        return check.get("ready") is True

    return False


def _build_patrol_runtime_rejection(
    *,
    runtime_config,
    reason_code,
    message,
    ros_detail=None,
):
    log_event(
        logger,
        logging.WARNING,
        "patrol_request_precheck_failed",
        reason_code=reason_code,
        message=message,
        pinky_id=runtime_config.pinky_id,
        ros_detail=ros_detail,
    )
    return TaskRequestService._build_patrol_task_response(
        result_code="REJECTED",
        result_message=message,
        reason_code=reason_code,
        assigned_robot_id=runtime_config.pinky_id,
    )


def _normalize_workflow_response(result):
    if isinstance(result, dict):
        return result
    return {
        "result_code": "FAILED",
        "result_message": f"patrol workflow returned non-dict result: {result!r}",
        "reason_code": "WORKFLOW_RESULT_INVALID",
    }


def _is_successful_patrol_result(result):
    return str((result or {}).get("result_code") or "").upper() in {
        "SUCCEEDED",
        "SUCCESS",
    }


def build_patrol_request_service(
    *,
    loop=None,
    workflow_task_manager=None,
    patrol_execution_repository=None,
    patrol_orchestrator=None,
    task_request_repository=None,
) -> TaskRequestService:
    runtime_config = get_patrol_runtime_config()
    task_request_repository = task_request_repository or _new_task_request_repository()
    patrol_workflow_starter = None
    patrol_request_precheck = None
    async_patrol_request_precheck = None

    if loop is not None:
        patrol_request_precheck = _build_patrol_request_precheck(
            runtime_config=runtime_config,
        )
        async_patrol_request_precheck = _build_async_patrol_request_precheck(
            runtime_config=runtime_config,
        )
        workflow_task_manager = workflow_task_manager or get_default_workflow_task_manager()
        patrol_execution_repository = patrol_execution_repository or PatrolTaskExecutionRepository()
        patrol_orchestrator = patrol_orchestrator or PatrolOrchestrator(
            runtime_config=runtime_config,
        )

        async def _run_patrol_workflow(*, task_id):
            snapshot = await patrol_execution_repository.async_get_patrol_execution_snapshot(task_id)
            if snapshot is None:
                return {
                    "result_code": "FAILED",
                    "result_message": "순찰 task 실행 정보를 찾을 수 없습니다.",
                    "reason_code": "PATROL_TASK_NOT_FOUND",
                }

            start_response = await patrol_execution_repository.async_record_patrol_execution_started(
                task_id
            )
            if start_response.get("result_code") != "ACCEPTED":
                return start_response

            return await patrol_orchestrator.async_run(
                task_id=str(task_id),
                path_snapshot_json=snapshot["path_snapshot_json"],
            )

        async def _record_workflow_result(*, task_id, workflow_response):
            try:
                await task_request_repository.async_record_patrol_task_workflow_result(
                    task_id=task_id,
                    workflow_response=workflow_response,
                )
            except Exception:
                logger.exception(
                    "patrol workflow result persistence failed",
                    extra={"task_id": task_id},
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

                level = logging.INFO if _is_successful_patrol_result(result) else logging.WARNING
                log_event(
                    logger,
                    level,
                    "patrol_workflow_background_finished",
                    task_id=task_id,
                    result_code=result.get("result_code"),
                    result_message=result.get("result_message"),
                    reason_code=result.get("reason_code"),
                )
                workflow_task_manager.create_task(
                    _record_workflow_result(
                        task_id=task_id,
                        workflow_response=result,
                    ),
                    name=f"patrol_workflow_result_{task_id}",
                    loop=loop,
                    cancel_on_shutdown=False,
                )

            background_task.add_done_callback(_handle_background_task_done)

        patrol_workflow_starter = _start_patrol_workflow

    return TaskRequestService(
        repository=task_request_repository,
        patrol_workflow_starter=patrol_workflow_starter,
        patrol_request_precheck=patrol_request_precheck,
        async_patrol_request_precheck=async_patrol_request_precheck,
    )


__all__ = ["build_patrol_request_service"]


def _new_task_request_repository():
    canonical_repository_cls = globals().get("TaskRequestRepository")
    legacy_repository_cls = globals().get("DeliveryRequestRepository")
    if canonical_repository_cls is not _DEFAULT_TASK_REQUEST_REPOSITORY:
        return canonical_repository_cls()
    if legacy_repository_cls is not _DEFAULT_TASK_REQUEST_REPOSITORY:
        return legacy_repository_cls()
    return canonical_repository_cls()
