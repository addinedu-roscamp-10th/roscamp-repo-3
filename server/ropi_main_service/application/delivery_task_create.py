import asyncio
import inspect

from server.ropi_main_service.persistence.repositories.task_request_repository import (
    TaskRequestRepository,
)


DeliveryRequestRepository = TaskRequestRepository
_DEFAULT_TASK_REQUEST_REPOSITORY = TaskRequestRepository


class DeliveryTaskCreateService:
    ACCEPTED = "ACCEPTED"
    INVALID_REQUEST = "INVALID_REQUEST"
    REJECTED = "REJECTED"

    def __init__(
        self,
        *,
        repository=None,
        delivery_workflow_starter=None,
        delivery_request_precheck=None,
        async_delivery_request_precheck=None,
    ):
        self.repository = repository or _new_task_request_repository()
        self.delivery_workflow_starter = delivery_workflow_starter
        self.delivery_request_precheck = delivery_request_precheck
        self.async_delivery_request_precheck = async_delivery_request_precheck

    def create_delivery_task(
        self,
        request_id,
        caregiver_id,
        item_id,
        quantity,
        destination_id,
        priority,
        notes=None,
        idempotency_key=None,
    ):
        invalid_response = self._validate_create_delivery_task_request(
            request_id=request_id,
            caregiver_id=caregiver_id,
            item_id=item_id,
            quantity=quantity,
            destination_id=destination_id,
            idempotency_key=idempotency_key,
        )
        if invalid_response is not None:
            return invalid_response

        precheck_response = self._run_delivery_request_precheck(
            request_id=request_id,
            caregiver_id=caregiver_id,
            item_id=item_id,
            quantity=quantity,
            destination_id=destination_id,
            priority=priority,
            notes=notes,
            idempotency_key=idempotency_key,
        )
        if precheck_response is not None:
            return precheck_response

        response = self.repository.create_delivery_task(
            request_id=request_id,
            caregiver_id=caregiver_id,
            item_id=item_id,
            quantity=quantity,
            destination_id=destination_id,
            priority=priority,
            notes=notes,
            idempotency_key=idempotency_key,
        )
        self._start_delivery_workflow_if_needed(
            response=response,
            item_id=item_id,
            quantity=quantity,
            destination_id=destination_id,
        )
        return response

    async def async_create_delivery_task(
        self,
        request_id,
        caregiver_id,
        item_id,
        quantity,
        destination_id,
        priority,
        notes=None,
        idempotency_key=None,
    ):
        invalid_response = self._validate_create_delivery_task_request(
            request_id=request_id,
            caregiver_id=caregiver_id,
            item_id=item_id,
            quantity=quantity,
            destination_id=destination_id,
            idempotency_key=idempotency_key,
        )
        if invalid_response is not None:
            return invalid_response

        precheck_response = await self._async_run_delivery_request_precheck(
            request_id=request_id,
            caregiver_id=caregiver_id,
            item_id=item_id,
            quantity=quantity,
            destination_id=destination_id,
            priority=priority,
            notes=notes,
            idempotency_key=idempotency_key,
        )
        if precheck_response is not None:
            return precheck_response

        response = await self.repository.async_create_delivery_task(
            request_id=request_id,
            caregiver_id=caregiver_id,
            item_id=item_id,
            quantity=quantity,
            destination_id=destination_id,
            priority=priority,
            notes=notes,
            idempotency_key=idempotency_key,
        )
        self._start_delivery_workflow_if_needed(
            response=response,
            item_id=item_id,
            quantity=quantity,
            destination_id=destination_id,
        )
        return response

    def _validate_create_delivery_task_request(
        self,
        *,
        request_id,
        caregiver_id,
        item_id,
        quantity,
        destination_id,
        idempotency_key,
    ):
        checks = (
            (
                self._is_blank(request_id),
                self._invalid_request("request_id가 필요합니다.", "REQUEST_ID_INVALID"),
            ),
            (
                self._is_blank(caregiver_id),
                self._rejected("caregiver_id가 필요합니다.", "REQUESTER_NOT_AUTHORIZED"),
            ),
            (
                self._is_blank(item_id),
                self._invalid_request("item_id가 필요합니다.", "ITEM_ID_INVALID"),
            ),
            (
                quantity <= 0,
                self._invalid_request("quantity는 1 이상이어야 합니다.", "QUANTITY_INVALID"),
            ),
            (
                self._is_blank(destination_id),
                self._invalid_request("destination_id가 필요합니다.", "DESTINATION_ID_INVALID"),
            ),
            (
                self._is_blank(idempotency_key),
                self._invalid_request("idempotency_key가 필요합니다.", "IDEMPOTENCY_KEY_INVALID"),
            ),
        )

        for failed, response in checks:
            if failed:
                return response

        return None

    @classmethod
    def _invalid_request(cls, message: str, reason_code: str):
        return cls._build_delivery_task_response(
            result_code=cls.INVALID_REQUEST,
            result_message=message,
            reason_code=reason_code,
        )

    @classmethod
    def _rejected(cls, message: str, reason_code: str):
        return cls._build_delivery_task_response(
            result_code=cls.REJECTED,
            result_message=message,
            reason_code=reason_code,
        )

    @staticmethod
    def _build_delivery_task_response(
        *,
        result_code,
        result_message=None,
        reason_code=None,
        task_id=None,
        task_status=None,
        assigned_robot_id=None,
    ):
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "task_id": task_id,
            "task_status": task_status,
            "assigned_robot_id": assigned_robot_id,
        }

    @staticmethod
    def _is_blank(value) -> bool:
        return not str(value or "").strip()

    def _run_delivery_request_precheck(self, **kwargs):
        if self.delivery_request_precheck is None:
            return None

        return self.delivery_request_precheck(**kwargs)

    async def _async_run_delivery_request_precheck(self, **kwargs):
        if self.async_delivery_request_precheck is not None:
            return await self._call_precheck_async(self.async_delivery_request_precheck, **kwargs)

        if self.delivery_request_precheck is None:
            return None

        if inspect.iscoroutinefunction(self.delivery_request_precheck):
            return await self.delivery_request_precheck(**kwargs)

        return await asyncio.to_thread(self.delivery_request_precheck, **kwargs)

    @staticmethod
    async def _call_precheck_async(precheck, **kwargs):
        result = precheck(**kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    def _start_delivery_workflow_if_needed(self, *, response, item_id, quantity, destination_id):
        if response.get("result_code") != self.ACCEPTED:
            return

        if self.delivery_workflow_starter is None:
            return

        task_id = str(response.get("task_id") or "").strip()
        if not task_id:
            return

        self.delivery_workflow_starter(
            task_id=task_id,
            item_id=str(item_id).strip(),
            quantity=int(quantity),
            destination_id=str(destination_id).strip(),
        )


__all__ = ["DeliveryTaskCreateService"]


def _new_task_request_repository():
    canonical_repository_cls = globals().get("TaskRequestRepository")
    legacy_repository_cls = globals().get("DeliveryRequestRepository")
    if canonical_repository_cls is not _DEFAULT_TASK_REQUEST_REPOSITORY:
        return canonical_repository_cls()
    if legacy_repository_cls is not _DEFAULT_TASK_REQUEST_REPOSITORY:
        return legacy_repository_cls()
    return canonical_repository_cls()
