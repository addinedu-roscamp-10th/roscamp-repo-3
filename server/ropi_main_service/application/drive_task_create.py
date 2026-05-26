import asyncio

from server.ropi_main_service.application.drive_config import get_drive_runtime_config
from server.ropi_main_service.persistence.repositories.task_request_repository import (
    TaskRequestRepository,
)


_DEFAULT_TASK_REQUEST_REPOSITORY = TaskRequestRepository


class DriveTaskCreateService:
    ACCEPTED = "ACCEPTED"
    INVALID_REQUEST = "INVALID_REQUEST"
    REJECTED = "REJECTED"

    def __init__(
        self,
        *,
        repository=None,
        runtime_config=None,
        drive_workflow_starter=None,
    ):
        self.repository = repository or _new_task_request_repository()
        self.runtime_config = runtime_config or get_drive_runtime_config()
        self.drive_workflow_starter = drive_workflow_starter

    def create_drive_task(
        self,
        request_id,
        caregiver_id,
        robot_id=None,
        route_id=None,
        priority=None,
        notes=None,
        idempotency_key=None,
    ):
        invalid_response = self._validate_create_drive_task_request(
            request_id=request_id,
            caregiver_id=caregiver_id,
            robot_id=robot_id,
            route_id=route_id,
            priority=priority,
            idempotency_key=idempotency_key,
        )
        if invalid_response is not None:
            return invalid_response

        response = self.repository.create_drive_task(
            request_id=request_id,
            caregiver_id=caregiver_id,
            robot_id=robot_id,
            route_id=route_id,
            priority=priority,
            notes=notes,
            idempotency_key=idempotency_key,
        )
        self._start_drive_workflow_if_needed(response=response)
        return response

    async def async_create_drive_task(
        self,
        request_id,
        caregiver_id,
        robot_id=None,
        route_id=None,
        priority=None,
        notes=None,
        idempotency_key=None,
    ):
        invalid_response = self._validate_create_drive_task_request(
            request_id=request_id,
            caregiver_id=caregiver_id,
            robot_id=robot_id,
            route_id=route_id,
            priority=priority,
            idempotency_key=idempotency_key,
        )
        if invalid_response is not None:
            return invalid_response

        async_create = getattr(self.repository, "async_create_drive_task", None)
        if async_create is not None:
            response = await async_create(
                request_id=request_id,
                caregiver_id=caregiver_id,
                robot_id=robot_id,
                route_id=route_id,
                priority=priority,
                notes=notes,
                idempotency_key=idempotency_key,
            )
        else:
            response = await asyncio.to_thread(
                self.repository.create_drive_task,
                request_id=request_id,
                caregiver_id=caregiver_id,
                robot_id=robot_id,
                route_id=route_id,
                priority=priority,
                notes=notes,
                idempotency_key=idempotency_key,
            )

        self._start_drive_workflow_if_needed(response=response)
        return response

    def _validate_create_drive_task_request(
        self,
        *,
        request_id,
        caregiver_id,
        robot_id,
        route_id,
        priority,
        idempotency_key,
    ):
        if self._is_blank(request_id):
            return self._build_drive_task_response(
                result_code=self.INVALID_REQUEST,
                result_message="request_id가 필요합니다.",
                reason_code="REQUEST_ID_INVALID",
            )
        if self._is_blank(caregiver_id):
            return self._build_drive_task_response(
                result_code=self.REJECTED,
                result_message="caregiver_id가 필요합니다.",
                reason_code="REQUESTER_NOT_AUTHORIZED",
            )
        normalized_robot_id = str(robot_id or "").strip()
        if not self._is_auto_robot_id(normalized_robot_id):
            if (
                normalized_robot_id.startswith("/")
                or normalized_robot_id.endswith("/")
                or "/" in normalized_robot_id
            ):
                return self._build_drive_task_response(
                    result_code=self.INVALID_REQUEST,
                    result_message="robot_id는 상대 namespace여야 합니다.",
                    reason_code="DRIVE_ROBOT_ID_INVALID",
                )
            if not self.runtime_config.is_robot_allowed(normalized_robot_id):
                return self._build_drive_task_response(
                    result_code=self.REJECTED,
                    result_message="허용되지 않은 FMS 주행 로봇입니다.",
                    reason_code="DRIVE_ROBOT_NOT_ALLOWED",
                )
        if self._is_blank(route_id):
            return self._build_drive_task_response(
                result_code=self.INVALID_REQUEST,
                result_message="route_id가 필요합니다.",
                reason_code="DRIVE_ROUTE_ID_INVALID",
            )
        normalized_priority = str(priority or "").strip().upper()
        if normalized_priority not in {"LOW", "NORMAL", "HIGH", "URGENT"}:
            return self._build_drive_task_response(
                result_code=self.INVALID_REQUEST,
                result_message=f"지원하지 않는 priority입니다: {priority}",
                reason_code="PRIORITY_INVALID",
            )
        if self._is_blank(idempotency_key):
            return self._build_drive_task_response(
                result_code=self.INVALID_REQUEST,
                result_message="idempotency_key가 필요합니다.",
                reason_code="IDEMPOTENCY_KEY_INVALID",
            )

        return None

    def _start_drive_workflow_if_needed(self, *, response):
        if response.get("result_code") != self.ACCEPTED:
            return

        if self.drive_workflow_starter is None:
            return

        task_id = str(response.get("task_id") or "").strip()
        if not task_id:
            return

        self.drive_workflow_starter(task_id=task_id)

    @staticmethod
    def _is_blank(value) -> bool:
        return not str(value or "").strip()

    @classmethod
    def _is_auto_robot_id(cls, value) -> bool:
        normalized = str(value or "").strip()
        return cls._is_blank(normalized) or normalized.upper() == "AUTO"

    @staticmethod
    def _build_drive_task_response(
        *,
        result_code,
        result_message=None,
        reason_code=None,
        task_id=None,
        task_type="DRIVE",
        task_status=None,
        phase=None,
        assigned_robot_id=None,
        map_id=None,
        route_id=None,
        route_name=None,
        route_revision=None,
        waypoint_count=None,
    ):
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "task_id": task_id,
            "task_type": task_type,
            "task_status": task_status,
            "phase": phase,
            "assigned_robot_id": assigned_robot_id,
            "map_id": map_id,
            "route_id": route_id,
            "route_name": route_name,
            "route_revision": route_revision,
            "waypoint_count": waypoint_count,
        }


__all__ = ["DriveTaskCreateService"]


def _new_task_request_repository():
    canonical_repository_cls = globals().get("TaskRequestRepository")
    if canonical_repository_cls is not _DEFAULT_TASK_REQUEST_REPOSITORY:
        return canonical_repository_cls()
    return canonical_repository_cls()
