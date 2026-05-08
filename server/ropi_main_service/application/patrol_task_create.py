import asyncio
import inspect

from server.ropi_main_service.persistence.repositories.task_request_repository import (
    TaskRequestRepository,
)


DeliveryRequestRepository = TaskRequestRepository
_DEFAULT_TASK_REQUEST_REPOSITORY = TaskRequestRepository


class PatrolTaskCreateService:
    ACCEPTED = "ACCEPTED"
    INVALID_REQUEST = "INVALID_REQUEST"
    REJECTED = "REJECTED"

    def __init__(
        self,
        *,
        repository=None,
        patrol_workflow_starter=None,
        patrol_request_precheck=None,
        async_patrol_request_precheck=None,
    ):
        self.repository = repository or _new_task_request_repository()
        self.patrol_workflow_starter = patrol_workflow_starter
        self.patrol_request_precheck = patrol_request_precheck
        self.async_patrol_request_precheck = async_patrol_request_precheck

    def create_patrol_task(
        self,
        request_id,
        caregiver_id,
        patrol_area_id,
        priority,
        idempotency_key,
    ):
        invalid_response = self._validate_create_patrol_task_request(
            request_id=request_id,
            caregiver_id=caregiver_id,
            patrol_area_id=patrol_area_id,
            priority=priority,
            idempotency_key=idempotency_key,
        )
        if invalid_response is not None:
            return invalid_response

        precheck_response = self._run_patrol_request_precheck(
            request_id=request_id,
            caregiver_id=caregiver_id,
            patrol_area_id=patrol_area_id,
            priority=priority,
            idempotency_key=idempotency_key,
        )
        if precheck_response is not None:
            return precheck_response

        response = self.repository.create_patrol_task(
            request_id=request_id,
            caregiver_id=caregiver_id,
            patrol_area_id=patrol_area_id,
            priority=priority,
            idempotency_key=idempotency_key,
        )
        self._start_patrol_workflow_if_needed(response=response)
        return response

    async def async_create_patrol_task(
        self,
        request_id,
        caregiver_id,
        patrol_area_id,
        priority,
        idempotency_key,
    ):
        invalid_response = self._validate_create_patrol_task_request(
            request_id=request_id,
            caregiver_id=caregiver_id,
            patrol_area_id=patrol_area_id,
            priority=priority,
            idempotency_key=idempotency_key,
        )
        if invalid_response is not None:
            return invalid_response

        precheck_response = await self._async_run_patrol_request_precheck(
            request_id=request_id,
            caregiver_id=caregiver_id,
            patrol_area_id=patrol_area_id,
            priority=priority,
            idempotency_key=idempotency_key,
        )
        if precheck_response is not None:
            return precheck_response

        async_create = getattr(self.repository, "async_create_patrol_task", None)
        if async_create is not None:
            response = await async_create(
                request_id=request_id,
                caregiver_id=caregiver_id,
                patrol_area_id=patrol_area_id,
                priority=priority,
                idempotency_key=idempotency_key,
            )
            self._start_patrol_workflow_if_needed(response=response)
            return response

        response = await asyncio.to_thread(
            self.repository.create_patrol_task,
            request_id=request_id,
            caregiver_id=caregiver_id,
            patrol_area_id=patrol_area_id,
            priority=priority,
            idempotency_key=idempotency_key,
        )
        self._start_patrol_workflow_if_needed(response=response)
        return response

    def _validate_create_patrol_task_request(
        self,
        *,
        request_id,
        caregiver_id,
        patrol_area_id,
        priority,
        idempotency_key,
    ):
        if self._is_blank(request_id):
            return self._build_patrol_task_response(
                result_code=self.INVALID_REQUEST,
                result_message="request_id가 필요합니다.",
                reason_code="REQUEST_ID_INVALID",
            )
        if self._is_blank(caregiver_id):
            return self._build_patrol_task_response(
                result_code=self.REJECTED,
                result_message="caregiver_id가 필요합니다.",
                reason_code="REQUESTER_NOT_AUTHORIZED",
            )
        if self._is_blank(patrol_area_id):
            return self._build_patrol_task_response(
                result_code=self.INVALID_REQUEST,
                result_message="patrol_area_id가 필요합니다.",
                reason_code="PATROL_AREA_ID_INVALID",
            )
        normalized_priority = str(priority or "").strip().upper()
        if normalized_priority not in {"NORMAL", "URGENT", "HIGHEST"}:
            return self._build_patrol_task_response(
                result_code=self.INVALID_REQUEST,
                result_message=f"지원하지 않는 priority입니다: {priority}",
                reason_code="PRIORITY_INVALID",
            )
        if self._is_blank(idempotency_key):
            return self._build_patrol_task_response(
                result_code=self.INVALID_REQUEST,
                result_message="idempotency_key가 필요합니다.",
                reason_code="IDEMPOTENCY_KEY_INVALID",
            )

        return None

    def _run_patrol_request_precheck(self, **kwargs):
        if self.patrol_request_precheck is None:
            return None

        return self.patrol_request_precheck(**kwargs)

    async def _async_run_patrol_request_precheck(self, **kwargs):
        if self.async_patrol_request_precheck is not None:
            return await self._call_precheck_async(
                self.async_patrol_request_precheck,
                **kwargs,
            )

        if self.patrol_request_precheck is None:
            return None

        if inspect.iscoroutinefunction(self.patrol_request_precheck):
            return await self.patrol_request_precheck(**kwargs)

        return await asyncio.to_thread(self.patrol_request_precheck, **kwargs)

    @staticmethod
    async def _call_precheck_async(precheck, **kwargs):
        result = precheck(**kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    def _start_patrol_workflow_if_needed(self, *, response):
        if response.get("result_code") != self.ACCEPTED:
            return

        if self.patrol_workflow_starter is None:
            return

        task_id = str(response.get("task_id") or "").strip()
        if not task_id:
            return

        self.patrol_workflow_starter(task_id=task_id)

    @staticmethod
    def _is_blank(value) -> bool:
        return not str(value or "").strip()

    @staticmethod
    def _build_patrol_task_response(
        *,
        result_code,
        result_message=None,
        reason_code=None,
        task_id=None,
        task_status=None,
        assigned_robot_id=None,
        patrol_area_id=None,
        patrol_area_name=None,
        patrol_area_revision=None,
    ):
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "task_id": task_id,
            "task_status": task_status,
            "assigned_robot_id": assigned_robot_id,
            "patrol_area_id": patrol_area_id,
            "patrol_area_name": patrol_area_name,
            "patrol_area_revision": patrol_area_revision,
        }


__all__ = ["PatrolTaskCreateService"]


def _new_task_request_repository():
    canonical_repository_cls = globals().get("TaskRequestRepository")
    legacy_repository_cls = globals().get("DeliveryRequestRepository")
    if canonical_repository_cls is not _DEFAULT_TASK_REQUEST_REPOSITORY:
        return canonical_repository_cls()
    if legacy_repository_cls is not _DEFAULT_TASK_REQUEST_REPOSITORY:
        return legacy_repository_cls()
    return canonical_repository_cls()
