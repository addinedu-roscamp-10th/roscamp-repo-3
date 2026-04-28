import asyncio
import logging

from server.ropi_main_service.application.delivery_config import (
    get_delivery_navigation_config,
    get_delivery_runtime_config,
)
from server.ropi_main_service.application.delivery_orchestrator import DeliveryOrchestrator
from server.ropi_main_service.application.goal_pose_navigation import GoalPoseNavigationService
from server.ropi_main_service.application.goal_pose_resolvers import (
    FixedGoalPoseResolver,
    MappedGoalPoseResolver,
)
from server.ropi_main_service.application.manipulation_command import ManipulationCommandService
from server.ropi_main_service.application.runtime_readiness import RosRuntimeReadinessService
from server.ropi_main_service.application.task_request import DeliveryRequestService
from server.ropi_main_service.observability import log_event


logger = logging.getLogger(__name__)


def _build_delivery_precheck_helpers(
    *,
    pickup_goal_pose,
    destination_goal_poses,
    return_to_dock_goal_pose,
):
    def _log_precheck_failure(
        *,
        reason_code: str,
        message: str,
        destination_id: str,
        ros_detail=None,
    ) -> None:
        log_event(
            logger,
            logging.WARNING,
            "delivery_request_precheck_failed",
            reason_code=reason_code,
            message=message,
            destination_id=destination_id,
            ros_detail=ros_detail,
        )

    def _reject(message: str, reason_code: str) -> dict:
        return DeliveryRequestService._rejected(message, reason_code)

    def _invalid_request(message: str, reason_code: str) -> dict:
        return DeliveryRequestService._invalid_request(message, reason_code)

    def _run_static_precheck(destination_id: str):
        if pickup_goal_pose is None:
            _log_precheck_failure(
                reason_code="PICKUP_GOAL_POSE_NOT_CONFIGURED",
                message="운반 픽업 좌표가 설정되지 않았습니다.",
                destination_id=destination_id,
            )
            return _reject(
                "운반 픽업 좌표가 설정되지 않았습니다.",
                "PICKUP_GOAL_POSE_NOT_CONFIGURED",
            )

        if return_to_dock_goal_pose is None:
            _log_precheck_failure(
                reason_code="RETURN_TO_DOCK_GOAL_POSE_NOT_CONFIGURED",
                message="복귀 좌표가 설정되지 않았습니다.",
                destination_id=destination_id,
            )
            return _reject(
                "복귀 좌표가 설정되지 않았습니다.",
                "RETURN_TO_DOCK_GOAL_POSE_NOT_CONFIGURED",
            )

        if not destination_goal_poses:
            _log_precheck_failure(
                reason_code="DESTINATION_GOAL_POSES_NOT_CONFIGURED",
                message="운반 목적지 좌표가 설정되지 않았습니다.",
                destination_id=destination_id,
            )
            return _reject(
                "운반 목적지 좌표가 설정되지 않았습니다.",
                "DESTINATION_GOAL_POSES_NOT_CONFIGURED",
            )

        if destination_id not in destination_goal_poses:
            _log_precheck_failure(
                reason_code="DESTINATION_ID_UNKNOWN",
                message=f"지원하지 않는 destination_id입니다: {destination_id}",
                destination_id=destination_id,
            )
            return _invalid_request(
                f"지원하지 않는 destination_id입니다: {destination_id}",
                "DESTINATION_ID_UNKNOWN",
            )

        return None

    def _handle_ros_unavailable(exc: Exception, destination_id: str):
        _log_precheck_failure(
            reason_code="ROS_SERVICE_UNAVAILABLE",
            message=f"ROS service가 준비되지 않았습니다: {exc}",
            destination_id=destination_id,
        )
        return _reject(
            f"ROS service가 준비되지 않았습니다: {exc}",
            "ROS_SERVICE_UNAVAILABLE",
        )

    def _evaluate_ros_status(ros_status: dict, destination_id: str):
        if not ros_status.get("ready"):
            _log_precheck_failure(
                reason_code="ROS_RUNTIME_NOT_READY",
                message="ROS runtime이 준비되지 않았습니다.",
                destination_id=destination_id,
                ros_detail=ros_status,
            )
            return _reject(
                "ROS runtime이 준비되지 않았습니다.",
                "ROS_RUNTIME_NOT_READY",
            )

        return None

    return _run_static_precheck, _handle_ros_unavailable, _evaluate_ros_status


def _build_delivery_request_precheck(
    *,
    pickup_goal_pose,
    destination_goal_poses,
    return_to_dock_goal_pose,
    runtime_config,
):
    _run_static_precheck, _handle_ros_unavailable, _evaluate_ros_status = _build_delivery_precheck_helpers(
        pickup_goal_pose=pickup_goal_pose,
        destination_goal_poses=destination_goal_poses,
        return_to_dock_goal_pose=return_to_dock_goal_pose,
    )

    def _precheck(**kwargs):
        destination_id = str(kwargs.get("destination_id") or "").strip()
        static_response = _run_static_precheck(destination_id)
        if static_response is not None:
            return static_response

        try:
            ros_status = RosRuntimeReadinessService(runtime_config=runtime_config).get_status()
        except Exception as exc:
            return _handle_ros_unavailable(exc, destination_id)

        return _evaluate_ros_status(ros_status, destination_id)

    return _precheck


def _build_async_delivery_request_precheck(
    *,
    pickup_goal_pose,
    destination_goal_poses,
    return_to_dock_goal_pose,
    runtime_config,
):
    _run_static_precheck, _handle_ros_unavailable, _evaluate_ros_status = _build_delivery_precheck_helpers(
        pickup_goal_pose=pickup_goal_pose,
        destination_goal_poses=destination_goal_poses,
        return_to_dock_goal_pose=return_to_dock_goal_pose,
    )

    async def _async_precheck(**kwargs):
        destination_id = str(kwargs.get("destination_id") or "").strip()
        static_response = _run_static_precheck(destination_id)
        if static_response is not None:
            return static_response

        try:
            ros_status = await RosRuntimeReadinessService(runtime_config=runtime_config).async_get_status()
        except Exception as exc:
            return _handle_ros_unavailable(exc, destination_id)

        return _evaluate_ros_status(ros_status, destination_id)

    return _async_precheck


def build_delivery_request_service(*, loop=None) -> DeliveryRequestService:
    runtime_config = get_delivery_runtime_config()
    navigation_config = get_delivery_navigation_config()
    pickup_goal_pose = navigation_config["pickup_goal_pose"]
    destination_goal_poses = navigation_config["destination_goal_poses"]
    return_to_dock_goal_pose = navigation_config["return_to_dock_goal_pose"]
    delivery_workflow_starter = None
    delivery_request_precheck = None
    async_delivery_request_precheck = None

    if loop is not None:
        delivery_request_precheck = _build_delivery_request_precheck(
            pickup_goal_pose=pickup_goal_pose,
            destination_goal_poses=destination_goal_poses,
            return_to_dock_goal_pose=return_to_dock_goal_pose,
            runtime_config=runtime_config,
        )
        async_delivery_request_precheck = _build_async_delivery_request_precheck(
            pickup_goal_pose=pickup_goal_pose,
            destination_goal_poses=destination_goal_poses,
            return_to_dock_goal_pose=return_to_dock_goal_pose,
            runtime_config=runtime_config,
        )

    if pickup_goal_pose is not None and destination_goal_poses and loop is not None:
        goal_pose_navigation_service = GoalPoseNavigationService(runtime_config=runtime_config)
        manipulation_command_service = ManipulationCommandService(runtime_config=runtime_config)
        orchestrator = DeliveryOrchestrator(
            goal_pose_navigation_service=goal_pose_navigation_service,
            manipulation_command_service=manipulation_command_service,
            pickup_goal_pose_resolver=FixedGoalPoseResolver(pickup_goal_pose),
            destination_goal_pose_resolver=MappedGoalPoseResolver(destination_goal_poses),
            return_to_dock_goal_pose_resolver=FixedGoalPoseResolver(return_to_dock_goal_pose),
            runtime_config=runtime_config,
        )

        def _start_delivery_workflow(**kwargs):
            async_run = getattr(orchestrator, "async_run", None)
            if async_run is not None:
                background_task = loop.create_task(async_run(**kwargs))
            else:
                background_task = loop.create_task(asyncio.to_thread(orchestrator.run, **kwargs))

            def _handle_background_task_done(task: asyncio.Task):
                try:
                    result = task.result()
                except Exception:
                    logger.exception("delivery workflow background task failed", extra={"task_id": kwargs.get("task_id")})
                    return

                level = logging.INFO if str(result.get("result_code") or "").upper() == "SUCCESS" else logging.WARNING
                log_event(
                    logger,
                    level,
                    "delivery_workflow_background_finished",
                    task_id=kwargs.get("task_id"),
                    result_code=result.get("result_code"),
                    result_message=result.get("result_message"),
                    reason_code=result.get("reason_code"),
                )

            background_task.add_done_callback(_handle_background_task_done)

        delivery_workflow_starter = _start_delivery_workflow

    return DeliveryRequestService(
        delivery_workflow_starter=delivery_workflow_starter,
        delivery_request_precheck=delivery_request_precheck,
        async_delivery_request_precheck=async_delivery_request_precheck,
    )


__all__ = ["build_delivery_request_service"]
