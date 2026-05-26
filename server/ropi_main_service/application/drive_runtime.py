import asyncio
import json
import logging
import math
from copy import deepcopy

from server.ropi_main_service.application.drive_config import get_drive_runtime_config
from server.ropi_main_service.application.fms_runtime import FmsRuntimeService
from server.ropi_main_service.application.goal_pose_navigation import (
    DEFAULT_FRAME_ID,
    GoalPoseNavigationService,
)
from server.ropi_main_service.application.task_request import TaskRequestService
from server.ropi_main_service.application.workflow_task_manager import (
    get_default_workflow_task_manager,
)
from server.ropi_main_service.observability import log_event
from server.ropi_main_service.persistence.repositories.drive_task_execution_repository import (
    DriveTaskExecutionRepository,
)
from server.ropi_main_service.persistence.repositories.task_request_repository import (
    DeliveryRequestRepository,
    TaskRequestRepository,
)


DEFAULT_DRIVE_NAVIGATION_TIMEOUT_SEC = 120
DEFAULT_FMS_RESERVATION_LEASE_SEC = 30
WAITING_FMS_RESERVATION_PHASE = "WAITING_FMS_RESERVATION"

_DEFAULT_TASK_REQUEST_REPOSITORY = TaskRequestRepository
logger = logging.getLogger(__name__)


class DriveOrchestrator:
    def __init__(
        self,
        *,
        goal_pose_navigation_service=None,
        drive_navigation_timeout_sec=DEFAULT_DRIVE_NAVIGATION_TIMEOUT_SEC,
    ):
        self.goal_pose_navigation_service = (
            goal_pose_navigation_service or GoalPoseNavigationService()
        )
        self.drive_navigation_timeout_sec = int(drive_navigation_timeout_sec)

    async def async_run(self, *, task_id, robot_id, path_snapshot_json):
        path = self._normalize_path_snapshot(path_snapshot_json)
        for index, pose_stamped in enumerate(path["poses"], start=1):
            sequence_no = pose_stamped.get("sequence_no") or index
            response = await self._async_navigate(
                task_id=task_id,
                nav_phase=f"DRIVE_WAYPOINT_{sequence_no}",
                goal_pose={
                    "header": pose_stamped["header"],
                    "pose": pose_stamped["pose"],
                },
                timeout_sec=self.drive_navigation_timeout_sec,
                pinky_id=robot_id,
            )
            if not self._is_success(response):
                return self._failed_navigation_response(response)

        return {
            "result_code": "SUCCESS",
            "result_message": "DRIVE route completed.",
            "reason_code": None,
        }

    async def _async_navigate(self, **kwargs):
        async_navigate = getattr(
            self.goal_pose_navigation_service,
            "async_navigate",
            None,
        )
        if async_navigate is not None:
            return await async_navigate(**kwargs)
        return await asyncio.to_thread(
            self.goal_pose_navigation_service.navigate,
            **kwargs,
        )

    @classmethod
    def _normalize_path_snapshot(cls, path_snapshot_json):
        if isinstance(path_snapshot_json, str):
            raw_path = json.loads(path_snapshot_json)
        else:
            raw_path = deepcopy(path_snapshot_json)

        if not isinstance(raw_path, dict):
            raise ValueError("DRIVE route path snapshot이 비어 있습니다.")

        header = raw_path.get("header") if isinstance(raw_path.get("header"), dict) else {}
        frame_id = str(header.get("frame_id") or DEFAULT_FRAME_ID).strip() or DEFAULT_FRAME_ID
        poses = raw_path.get("poses")
        if not isinstance(poses, list) or not poses:
            raise ValueError("DRIVE route waypoint가 비어 있습니다.")

        return {
            "header": cls._normalize_header(header, frame_id=frame_id),
            "poses": [
                cls._normalize_pose_stamped(pose, frame_id=frame_id)
                for pose in poses
            ],
        }

    @classmethod
    def _normalize_pose_stamped(cls, waypoint, *, frame_id):
        if isinstance(waypoint, dict) and "pose" in waypoint:
            normalized = deepcopy(waypoint)
            header = normalized.get("header")
            if not isinstance(header, dict):
                header = {}
            normalized["header"] = cls._normalize_header(header, frame_id=frame_id)
            normalized["pose"] = cls._normalize_pose(normalized.get("pose") or {})
            return normalized

        pose = cls._waypoint_to_pose(waypoint)
        sequence_no = None
        if isinstance(waypoint, dict):
            sequence_no = waypoint.get("sequence_no")
        return {
            "sequence_no": sequence_no,
            "header": cls._normalize_header({}, frame_id=frame_id),
            "pose": pose,
        }

    @staticmethod
    def _normalize_header(header, *, frame_id):
        normalized = dict(header or {})
        normalized["frame_id"] = str(
            normalized.get("frame_id") or frame_id
        ).strip() or frame_id
        normalized.setdefault("stamp", {"sec": 0, "nanosec": 0})
        return normalized

    @classmethod
    def _normalize_pose(cls, pose):
        return {
            "position": {
                "x": float((pose.get("position") or {}).get("x", 0.0)),
                "y": float((pose.get("position") or {}).get("y", 0.0)),
                "z": float((pose.get("position") or {}).get("z", 0.0)),
            },
            "orientation": dict(
                pose.get("orientation")
                or {
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0,
                    "w": 1.0,
                }
            ),
        }

    @staticmethod
    def _waypoint_to_pose(waypoint):
        if isinstance(waypoint, dict):
            x = waypoint.get("x")
            y = waypoint.get("y")
            z = waypoint.get("z", 0.0)
            yaw = waypoint.get("yaw", waypoint.get("yaw_rad", 0.0))
        else:
            values = list(waypoint or [])
            if len(values) < 2:
                raise ValueError("DRIVE route waypoint 형식이 올바르지 않습니다.")
            x = values[0]
            y = values[1]
            z = 0.0
            yaw = values[2] if len(values) > 2 else 0.0

        yaw = float(yaw)
        return {
            "position": {
                "x": float(x),
                "y": float(y),
                "z": float(z),
            },
            "orientation": {
                "x": 0.0,
                "y": 0.0,
                "z": math.sin(yaw / 2.0),
                "w": math.cos(yaw / 2.0),
            },
        }

    @staticmethod
    def _is_success(response):
        return str((response or {}).get("result_code") or "").upper() in {
            "SUCCESS",
            "SUCCEEDED",
        }

    @staticmethod
    def _failed_navigation_response(response):
        response = response if isinstance(response, dict) else {}
        return {
            "result_code": str(response.get("result_code") or "FAILED").upper(),
            "result_message": response.get("result_message")
            or "DRIVE waypoint navigation failed.",
            "reason_code": response.get("reason_code") or "DRIVE_NAVIGATION_FAILED",
        }


def build_drive_request_service(
    *,
    loop=None,
    workflow_task_manager=None,
    task_request_repository=None,
    drive_execution_repository=None,
    fms_runtime_service=None,
    drive_orchestrator=None,
    task_update_publisher=None,
) -> TaskRequestService:
    get_drive_runtime_config()
    task_request_repository = task_request_repository or _new_task_request_repository()
    drive_workflow_starter = None

    if loop is not None:
        workflow_task_manager = (
            workflow_task_manager or get_default_workflow_task_manager()
        )
        drive_execution_repository = (
            drive_execution_repository or DriveTaskExecutionRepository()
        )
        fms_runtime_service = fms_runtime_service or FmsRuntimeService()
        drive_orchestrator = drive_orchestrator or DriveOrchestrator()

        async def _run_drive_workflow(*, task_id):
            snapshot = await drive_execution_repository.async_get_drive_execution_snapshot(
                task_id
            )
            if snapshot is None:
                return _failed(
                    "DRIVE task 실행 정보를 찾을 수 없습니다.",
                    reason_code="DRIVE_TASK_NOT_FOUND",
                )

            reservation_response = await _request_fms_reservation(
                fms_runtime_service=fms_runtime_service,
                snapshot=snapshot,
            )
            reservation_result = str(
                reservation_response.get("result_code") or ""
            ).upper()
            if reservation_result == "WAITING":
                waiting_response = await drive_execution_repository.async_record_drive_reservation_waiting(
                    task_id=task_id,
                    reservation_response=reservation_response,
                )
                await _publish_workflow_task_update(
                    waiting_response,
                    source="DRIVE_FMS_RESERVATION_WAITING",
                )
                return {
                    **reservation_response,
                    "terminal": False,
                }

            if reservation_result != "HELD":
                return _failed(
                    reservation_response.get("result_message")
                    or "DRIVE FMS reservation failed.",
                    reason_code=reservation_response.get("reason_code")
                    or "DRIVE_FMS_RESERVATION_FAILED",
                )

            start_response = (
                await drive_execution_repository.async_record_drive_execution_started(
                    task_id
                )
            )
            await _publish_workflow_task_update(
                start_response,
                source="DRIVE_WORKFLOW_STARTED",
            )
            if start_response.get("result_code") != "ACCEPTED":
                await _release_fms_reservation(
                    fms_runtime_service=fms_runtime_service,
                    task_id=task_id,
                    robot_id=snapshot["assigned_robot_id"],
                    reason_code="FAILED",
                )
                return start_response

            workflow_response = None
            release_reason = "FAILED"
            try:
                workflow_response = await drive_orchestrator.async_run(
                    task_id=str(task_id),
                    robot_id=snapshot["assigned_robot_id"],
                    path_snapshot_json=snapshot["path_snapshot_json"],
                )
                release_reason = _release_reason_for_workflow(workflow_response)
                return workflow_response
            except asyncio.CancelledError:
                release_reason = "CANCELLED"
                raise
            except Exception as exc:
                workflow_response = _failed(
                    f"DRIVE workflow failed: {exc}",
                    reason_code="DRIVE_WORKFLOW_UNHANDLED_EXCEPTION",
                )
                return workflow_response
            finally:
                await _release_fms_reservation(
                    fms_runtime_service=fms_runtime_service,
                    task_id=task_id,
                    robot_id=snapshot["assigned_robot_id"],
                    reason_code=release_reason,
                )

        async def _record_workflow_result(*, task_id, workflow_response):
            try:
                response = await drive_execution_repository.async_record_drive_task_workflow_result(
                    task_id=task_id,
                    workflow_response=workflow_response,
                )
                await _publish_workflow_task_update(response)
            except Exception:
                logger.exception(
                    "drive workflow result persistence failed",
                    extra={"task_id": task_id},
                )

        async def _publish_workflow_task_update(
            response,
            *,
            source="DRIVE_WORKFLOW_RESULT",
        ):
            if task_update_publisher is None:
                return
            publish_from_response = getattr(
                task_update_publisher,
                "publish_from_response",
                None,
            )
            if publish_from_response is None:
                return
            result = publish_from_response(
                response,
                source=source,
                task_type="DRIVE",
            )
            if asyncio.iscoroutine(result):
                await result

        def _start_drive_workflow(**kwargs):
            task_id = str(kwargs.get("task_id") or "").strip()
            background_task = workflow_task_manager.create_task(
                _run_drive_workflow(task_id=task_id),
                name=f"drive_workflow_{task_id}",
                loop=loop,
                cancel_on_shutdown=True,
            )

            def _handle_background_task_done(task: asyncio.Task):
                try:
                    result = _normalize_workflow_response(task.result())
                except asyncio.CancelledError:
                    result = _failed(
                        "DRIVE workflow background task was cancelled.",
                        reason_code="WORKFLOW_TASK_CANCELLED",
                    )
                except Exception as exc:
                    logger.exception(
                        "drive workflow background task failed",
                        extra={"task_id": task_id},
                    )
                    result = _failed(
                        f"DRIVE workflow background task failed: {exc}",
                        reason_code="WORKFLOW_UNHANDLED_EXCEPTION",
                    )

                if not result.get("terminal", True):
                    return

                level = logging.INFO if _is_success(result) else logging.WARNING
                log_event(
                    logger,
                    level,
                    "drive_workflow_background_finished",
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
                    name=f"drive_workflow_result_{task_id}",
                    loop=loop,
                    cancel_on_shutdown=False,
                )

            background_task.add_done_callback(_handle_background_task_done)

        drive_workflow_starter = _start_drive_workflow

    return TaskRequestService(
        repository=task_request_repository,
        drive_workflow_starter=drive_workflow_starter,
    )


async def _request_fms_reservation(*, fms_runtime_service, snapshot):
    kwargs = {
        "task_id": int(snapshot["task_id"]),
        "robot_id": snapshot["assigned_robot_id"],
        "map_id": snapshot["map_id"],
        "resources": snapshot.get("reservation_resources") or [],
        "lease_sec": DEFAULT_FMS_RESERVATION_LEASE_SEC,
    }
    async_request = getattr(fms_runtime_service, "async_request_reservation", None)
    if async_request is not None:
        return await async_request(**kwargs)
    return await asyncio.to_thread(fms_runtime_service.request_reservation, **kwargs)


async def _release_fms_reservation(
    *,
    fms_runtime_service,
    task_id,
    robot_id,
    reason_code,
):
    kwargs = {
        "task_id": int(task_id),
        "robot_id": robot_id,
        "reason_code": reason_code,
    }
    async_release = getattr(fms_runtime_service, "async_release_reservation", None)
    if async_release is not None:
        return await async_release(**kwargs)
    return await asyncio.to_thread(fms_runtime_service.release_reservation, **kwargs)


def _release_reason_for_workflow(workflow_response):
    result_code = str((workflow_response or {}).get("result_code") or "").upper()
    if result_code in {"SUCCESS", "SUCCEEDED"}:
        return "COMPLETED"
    if result_code in {"CANCELED", "CANCELLED"}:
        return "CANCELLED"
    return "FAILED"


def _normalize_workflow_response(response):
    if not isinstance(response, dict):
        return _failed(
            "DRIVE workflow returned an invalid response.",
            reason_code="DRIVE_WORKFLOW_RESPONSE_INVALID",
        )
    return response


def _failed(result_message, *, reason_code):
    return {
        "result_code": "FAILED",
        "result_message": result_message,
        "reason_code": reason_code,
    }


def _is_success(response):
    return str((response or {}).get("result_code") or "").upper() in {
        "SUCCESS",
        "SUCCEEDED",
    }


def _new_task_request_repository():
    canonical_repository_cls = globals().get("TaskRequestRepository")
    legacy_repository_cls = globals().get("DeliveryRequestRepository")
    if canonical_repository_cls is not _DEFAULT_TASK_REQUEST_REPOSITORY:
        return canonical_repository_cls()
    if legacy_repository_cls is not DeliveryRequestRepository:
        return legacy_repository_cls()
    return _DEFAULT_TASK_REQUEST_REPOSITORY()


__all__ = [
    "DriveOrchestrator",
    "build_drive_request_service",
]
