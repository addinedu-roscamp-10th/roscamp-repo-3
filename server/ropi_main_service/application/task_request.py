import asyncio

from server.ropi_main_service.application.command_execution import (
    CommandExecutionRecorder,
)
from server.ropi_main_service.application.delivery_cancel import DeliveryCancelService
from server.ropi_main_service.application.delivery_task_create import DeliveryTaskCreateService
from server.ropi_main_service.application.fall_response_command import (
    FallResponseCommandService,
)
from server.ropi_main_service.application.patrol_resume import PatrolResumeService
from server.ropi_main_service.application.patrol_task_create import PatrolTaskCreateService
from server.ropi_main_service.ipc.uds_client import (
    UnixDomainSocketCommandClient,
)
from server.ropi_main_service.persistence.repositories.task_request_repository import (
    TaskRequestRepository,
)


DeliveryRequestRepository = TaskRequestRepository
_DEFAULT_TASK_REQUEST_REPOSITORY = TaskRequestRepository


class TaskRequestService:
    ACCEPTED = "ACCEPTED"
    INVALID_REQUEST = "INVALID_REQUEST"
    REJECTED = "REJECTED"

    def __init__(
        self,
        repository=None,
        delivery_workflow_starter=None,
        patrol_workflow_starter=None,
        delivery_request_precheck=None,
        async_delivery_request_precheck=None,
        command_client=None,
        command_execution_recorder=None,
        fall_response_command_service=None,
        delivery_cancel_service=None,
        patrol_resume_service=None,
        cancel_timeout_sec=5.0,
    ):
        self.repository = repository or _new_task_request_repository()
        self.delivery_workflow_starter = delivery_workflow_starter
        self.patrol_workflow_starter = patrol_workflow_starter
        self.delivery_request_precheck = delivery_request_precheck
        self.async_delivery_request_precheck = async_delivery_request_precheck
        self.command_client = command_client or UnixDomainSocketCommandClient()
        self.command_execution_recorder = command_execution_recorder or CommandExecutionRecorder()
        self.cancel_timeout_sec = float(cancel_timeout_sec)
        self.fall_response_command_service = (
            fall_response_command_service
            or FallResponseCommandService(
                command_client=self.command_client,
                command_execution_recorder=self.command_execution_recorder,
                timeout_sec=self.cancel_timeout_sec,
            )
        )
        self.delivery_cancel_service = (
            delivery_cancel_service
            or DeliveryCancelService(
                repository=self.repository,
                command_client=self.command_client,
                command_execution_recorder=self.command_execution_recorder,
                timeout_sec=self.cancel_timeout_sec,
            )
        )
        self.patrol_resume_service = (
            patrol_resume_service
            or PatrolResumeService(
                repository=self.repository,
                fall_response_command_service=self.fall_response_command_service,
            )
        )
        self.create_service = DeliveryTaskCreateService(
            repository=self.repository,
            delivery_workflow_starter=delivery_workflow_starter,
            delivery_request_precheck=delivery_request_precheck,
            async_delivery_request_precheck=async_delivery_request_precheck,
        )
        self.patrol_create_service = PatrolTaskCreateService(
            repository=self.repository,
            patrol_workflow_starter=patrol_workflow_starter,
        )

    def get_product_names(self):
        products = self.repository.get_all_products()
        return [product["item_name"] for product in products]

    async def async_get_product_names(self):
        products = await self.repository.async_get_all_products()
        return [product["item_name"] for product in products]

    def get_delivery_items(self):
        return self.repository.get_all_products()

    async def async_get_delivery_items(self):
        return await self.repository.async_get_all_products()

    def get_delivery_destinations(self):
        return [
            self._format_delivery_destination(row)
            for row in self.repository.get_delivery_destinations()
        ]

    async def async_get_delivery_destinations(self):
        rows = await self.repository.async_get_delivery_destinations()
        return [self._format_delivery_destination(row) for row in rows]

    def get_patrol_areas(self):
        return [
            self._format_patrol_area(row)
            for row in self.repository.get_patrol_areas()
        ]

    async def async_get_patrol_areas(self):
        rows = await self.repository.async_get_patrol_areas()
        return [self._format_patrol_area(row) for row in rows]

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
        self._sync_create_service_dependencies()
        return self.create_service.create_delivery_task(
            request_id=request_id,
            caregiver_id=caregiver_id,
            item_id=item_id,
            quantity=quantity,
            destination_id=destination_id,
            priority=priority,
            notes=notes,
            idempotency_key=idempotency_key,
        )

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
        self._sync_create_service_dependencies()
        return await self.create_service.async_create_delivery_task(
            request_id=request_id,
            caregiver_id=caregiver_id,
            item_id=item_id,
            quantity=quantity,
            destination_id=destination_id,
            priority=priority,
            notes=notes,
            idempotency_key=idempotency_key,
        )

    def create_patrol_task(
        self,
        request_id,
        caregiver_id,
        patrol_area_id,
        priority,
        idempotency_key,
    ):
        self._sync_create_service_dependencies()
        return self.patrol_create_service.create_patrol_task(
            request_id=request_id,
            caregiver_id=caregiver_id,
            patrol_area_id=patrol_area_id,
            priority=priority,
            idempotency_key=idempotency_key,
        )

    async def async_create_patrol_task(
        self,
        request_id,
        caregiver_id,
        patrol_area_id,
        priority,
        idempotency_key,
    ):
        self._sync_create_service_dependencies()
        return await self.patrol_create_service.async_create_patrol_task(
            request_id=request_id,
            caregiver_id=caregiver_id,
            patrol_area_id=patrol_area_id,
            priority=priority,
            idempotency_key=idempotency_key,
        )

    def resume_patrol_task(self, task_id, caregiver_id, member_id, action_memo):
        self._sync_resume_service_dependencies()
        return self.patrol_resume_service.resume_patrol_task(
            task_id=task_id,
            caregiver_id=caregiver_id,
            member_id=member_id,
            action_memo=action_memo,
        )

    async def async_resume_patrol_task(self, task_id, caregiver_id, member_id, action_memo):
        self._sync_resume_service_dependencies()
        return await self.patrol_resume_service.async_resume_patrol_task(
            task_id=task_id,
            caregiver_id=caregiver_id,
            member_id=member_id,
            action_memo=action_memo,
        )

    def cancel_delivery_task(self, task_id, action_name=None):
        self._sync_cancel_service_dependencies()
        return self.delivery_cancel_service.cancel_delivery_task(
            task_id=task_id,
            action_name=action_name,
        )

    async def async_cancel_delivery_task(self, task_id, action_name=None):
        self._sync_cancel_service_dependencies()
        return await self.delivery_cancel_service.async_cancel_delivery_task(
            task_id=task_id,
            action_name=action_name,
        )

    def submit_delivery_request(
        self,
        item_name,
        quantity,
        destination,
        priority,
        detail,
        member_id,
    ):
        if not item_name or item_name == "등록된 물품 없음":
            return False, "물품 종류를 선택하세요."

        if quantity <= 0:
            return False, "수량은 1 이상이어야 합니다."

        if not destination:
            return False, "목적지를 선택하세요."

        if not member_id:
            return False, "로그인 사용자 정보가 없습니다."

        return self.repository.create_delivery_request(
            item_name=item_name,
            quantity=quantity,
            destination=destination,
            priority=priority,
            detail=detail,
            member_id=member_id,
        )

    async def async_submit_delivery_request(
        self,
        item_name,
        quantity,
        destination,
        priority,
        detail,
        member_id,
    ):
        if not item_name or item_name == "등록된 물품 없음":
            return False, "물품 종류를 선택하세요."

        if quantity <= 0:
            return False, "수량은 1 이상이어야 합니다."

        if not destination:
            return False, "목적지를 선택하세요."

        if not member_id:
            return False, "로그인 사용자 정보가 없습니다."

        return await self.repository.async_create_delivery_request(
            item_name=item_name,
            quantity=quantity,
            destination=destination,
            priority=priority,
            detail=detail,
            member_id=member_id,
        )

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
        self._sync_create_service_dependencies()
        return self.create_service._validate_create_delivery_task_request(
            request_id=request_id,
            caregiver_id=caregiver_id,
            item_id=item_id,
            quantity=quantity,
            destination_id=destination_id,
            idempotency_key=idempotency_key,
        )

    def _validate_create_patrol_task_request(
        self,
        *,
        request_id,
        caregiver_id,
        patrol_area_id,
        priority,
        idempotency_key,
    ):
        self._sync_create_service_dependencies()
        return self.patrol_create_service._validate_create_patrol_task_request(
            request_id=request_id,
            caregiver_id=caregiver_id,
            patrol_area_id=patrol_area_id,
            priority=priority,
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def _format_delivery_destination(row):
        destination_name = str(
            row.get("destination_name") or row.get("destination_id") or ""
        ).strip()
        destination_id = str(row.get("destination_id") or "").strip()
        return {
            "destination_id": destination_id,
            "destination_name": destination_name,
            "display_name": destination_name or destination_id,
            "zone_id": row.get("zone_id"),
            "map_id": row.get("map_id"),
        }

    def _format_patrol_area(self, row):
        return {
            "patrol_area_id": str(row.get("patrol_area_id") or "").strip(),
            "patrol_area_name": str(row.get("patrol_area_name") or "").strip(),
            "patrol_area_revision": row.get("patrol_area_revision"),
            "waypoint_count": self._optional_int(row.get("waypoint_count")),
            "path_frame_id": self._optional_string(row.get("path_frame_id")),
            "active": True,
            "map_id": row.get("map_id"),
        }

    @staticmethod
    def _rejected(message: str, reason_code: str):
        return DeliveryTaskCreateService._rejected(message, reason_code)

    @staticmethod
    def _invalid_request(message: str, reason_code: str):
        return DeliveryTaskCreateService._invalid_request(message, reason_code)

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
        return DeliveryTaskCreateService._build_delivery_task_response(
            result_code=result_code,
            result_message=result_message,
            reason_code=reason_code,
            task_id=task_id,
            task_status=task_status,
            assigned_robot_id=assigned_robot_id,
        )

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
        return PatrolTaskCreateService._build_patrol_task_response(
            result_code=result_code,
            result_message=result_message,
            reason_code=reason_code,
            task_id=task_id,
            task_status=task_status,
            assigned_robot_id=assigned_robot_id,
            patrol_area_id=patrol_area_id,
            patrol_area_name=patrol_area_name,
            patrol_area_revision=patrol_area_revision,
        )

    @staticmethod
    def _is_blank(value) -> bool:
        return not str(value or "").strip()

    @staticmethod
    def _optional_string(value):
        normalized = str(value or "").strip()
        return normalized or None

    @staticmethod
    def _optional_int(value):
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _run_delivery_request_precheck(self, **kwargs):
        self._sync_create_service_dependencies()
        return self.create_service._run_delivery_request_precheck(**kwargs)

    async def _async_run_delivery_request_precheck(self, **kwargs):
        self._sync_create_service_dependencies()
        return await self.create_service._async_run_delivery_request_precheck(**kwargs)

    @staticmethod
    async def _call_precheck_async(precheck, **kwargs):
        return await DeliveryTaskCreateService._call_precheck_async(precheck, **kwargs)

    def _start_delivery_workflow_if_needed(self, *, response, item_id, quantity, destination_id):
        self._sync_create_service_dependencies()
        return self.create_service._start_delivery_workflow_if_needed(
            response=response,
            item_id=item_id,
            quantity=quantity,
            destination_id=destination_id,
        )

    def _start_patrol_workflow_if_needed(self, *, response):
        self._sync_create_service_dependencies()
        return self.patrol_create_service._start_patrol_workflow_if_needed(response=response)

    def _sync_create_service_dependencies(self):
        self.create_service.repository = self.repository
        self.create_service.delivery_workflow_starter = self.delivery_workflow_starter
        self.create_service.delivery_request_precheck = self.delivery_request_precheck
        self.create_service.async_delivery_request_precheck = self.async_delivery_request_precheck
        self.patrol_create_service.repository = self.repository
        self.patrol_create_service.patrol_workflow_starter = self.patrol_workflow_starter

    def _sync_cancel_service_dependencies(self):
        self.delivery_cancel_service.repository = self.repository
        self.delivery_cancel_service.command_client = self.command_client
        self.delivery_cancel_service.command_execution_recorder = self.command_execution_recorder
        self.delivery_cancel_service.timeout_sec = self.cancel_timeout_sec

    def _sync_resume_service_dependencies(self):
        self.fall_response_command_service.command_client = self.command_client
        self.fall_response_command_service.command_execution_recorder = (
            self.command_execution_recorder
        )
        self.fall_response_command_service.timeout_sec = self.cancel_timeout_sec
        self.patrol_resume_service.repository = self.repository
        self.patrol_resume_service.fall_response_command_service = (
            self.fall_response_command_service
        )


DeliveryRequestService = TaskRequestService


def _new_task_request_repository():
    canonical_repository_cls = globals().get("TaskRequestRepository")
    legacy_repository_cls = globals().get("DeliveryRequestRepository")
    if canonical_repository_cls is not _DEFAULT_TASK_REQUEST_REPOSITORY:
        return canonical_repository_cls()
    if legacy_repository_cls is not _DEFAULT_TASK_REQUEST_REPOSITORY:
        return legacy_repository_cls()
    return canonical_repository_cls()


__all__ = ["TaskRequestService", "DeliveryRequestService"]
