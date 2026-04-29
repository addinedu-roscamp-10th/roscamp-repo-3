import asyncio

from server.ropi_main_service.application.command_execution import (
    CommandExecutionRecorder,
    CommandExecutionSpec,
)
from server.ropi_main_service.application.delivery_task_create import DeliveryTaskCreateService
from server.ropi_main_service.application.patrol_task_create import PatrolTaskCreateService
from server.ropi_main_service.ipc.uds_client import (
    RosServiceCommandError,
    UnixDomainSocketCommandClient,
)
from server.ropi_main_service.persistence.repositories.task_request_repository import DeliveryRequestRepository


class DeliveryRequestService:
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
        cancel_timeout_sec=5.0,
    ):
        self.repository = repository or DeliveryRequestRepository()
        self.delivery_workflow_starter = delivery_workflow_starter
        self.patrol_workflow_starter = patrol_workflow_starter
        self.delivery_request_precheck = delivery_request_precheck
        self.async_delivery_request_precheck = async_delivery_request_precheck
        self.command_client = command_client or UnixDomainSocketCommandClient()
        self.command_execution_recorder = command_execution_recorder or CommandExecutionRecorder()
        self.cancel_timeout_sec = float(cancel_timeout_sec)
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

    def cancel_delivery_task(self, task_id, action_name=None):
        invalid_response = self._validate_cancel_delivery_task_request(task_id=task_id)
        if invalid_response is not None:
            return invalid_response

        target_response = self.repository.get_delivery_task_cancel_target(task_id)
        if target_response.get("result_code") != self.ACCEPTED:
            return target_response

        payload = self._build_cancel_action_payload(task_id=task_id, action_name=action_name)
        spec = self._build_cancel_command_execution_spec(
            task_id=task_id,
            action_name=action_name,
            assigned_robot_id=target_response.get("assigned_robot_id"),
            payload=payload,
        )
        try:
            cancel_response = self.command_execution_recorder.record(
                spec,
                lambda: self.command_client.send_command(
                    "cancel_action",
                    payload,
                    timeout=self.cancel_timeout_sec,
                ),
            )
        except RosServiceCommandError as exc:
            cancel_response = self._rejected(
                f"ROS service cancel 요청에 실패했습니다: {exc}",
                "ROS_SERVICE_UNAVAILABLE",
            )
            cancel_response["cancel_requested"] = False

        return self.repository.record_delivery_task_cancel_result(
            task_id=task_id,
            cancel_response=cancel_response,
        )

    async def async_cancel_delivery_task(self, task_id, action_name=None):
        invalid_response = self._validate_cancel_delivery_task_request(task_id=task_id)
        if invalid_response is not None:
            return invalid_response

        async_cancel_target = getattr(self.repository, "async_get_delivery_task_cancel_target", None)
        if async_cancel_target is not None:
            target_response = await async_cancel_target(task_id)
        else:
            target_response = await asyncio.to_thread(
                self.repository.get_delivery_task_cancel_target,
                task_id,
            )
        if target_response.get("result_code") != self.ACCEPTED:
            return target_response

        payload = self._build_cancel_action_payload(task_id=task_id, action_name=action_name)
        async_send_command = getattr(self.command_client, "async_send_command", None)
        spec = self._build_cancel_command_execution_spec(
            task_id=task_id,
            action_name=action_name,
            assigned_robot_id=target_response.get("assigned_robot_id"),
            payload=payload,
        )

        try:
            if async_send_command is not None:
                async def _send_async_cancel_command():
                    return await async_send_command(
                        "cancel_action",
                        payload,
                        timeout=self.cancel_timeout_sec,
                    )

                cancel_response = await self.command_execution_recorder.async_record(
                    spec,
                    _send_async_cancel_command,
                )
            else:
                async def _send_sync_cancel_command_in_thread():
                    return await asyncio.to_thread(
                        self.command_client.send_command,
                        "cancel_action",
                        payload,
                        timeout=self.cancel_timeout_sec,
                    )

                cancel_response = await self.command_execution_recorder.async_record(
                    spec,
                    _send_sync_cancel_command_in_thread,
                )

        except RosServiceCommandError as exc:
            cancel_response = self._rejected(
                f"ROS service cancel 요청에 실패했습니다: {exc}",
                "ROS_SERVICE_UNAVAILABLE",
            )
            cancel_response["cancel_requested"] = False

        async_record_cancel_result = getattr(self.repository, "async_record_delivery_task_cancel_result", None)
        if async_record_cancel_result is not None:
            return await async_record_cancel_result(
                task_id=task_id,
                cancel_response=cancel_response,
            )

        return await asyncio.to_thread(
            self.repository.record_delivery_task_cancel_result,
            task_id=task_id,
            cancel_response=cancel_response,
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

    def _validate_cancel_delivery_task_request(self, *, task_id):
        if self._is_blank(task_id):
            return self._invalid_request("task_id가 필요합니다.", "TASK_ID_INVALID")

        return None

    @staticmethod
    def _build_cancel_action_payload(*, task_id, action_name=None):
        payload = {
            "task_id": str(task_id).strip(),
        }
        normalized_action_name = str(action_name or "").strip()
        if normalized_action_name:
            payload["action_name"] = normalized_action_name
        return payload

    @staticmethod
    def _build_cancel_command_execution_spec(*, task_id, action_name=None, assigned_robot_id=None, payload):
        normalized_action_name = str(action_name or "").strip()
        return CommandExecutionSpec(
            task_id=str(task_id).strip(),
            transport="ROS_ACTION",
            command_type="CANCEL_ACTION",
            command_phase="CANCEL",
            target_component="ros_service",
            target_robot_id=str(assigned_robot_id or "").strip() or None,
            target_endpoint=normalized_action_name or "active_action_for_task",
            request_payload=payload,
        )

    @staticmethod
    def _invalid_request(message: str, reason_code: str):
        return DeliveryTaskCreateService._invalid_request(message, reason_code)

    @staticmethod
    def _rejected(message: str, reason_code: str):
        return DeliveryTaskCreateService._rejected(message, reason_code)

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

TaskRequestService = DeliveryRequestService

__all__ = ["DeliveryRequestService", "TaskRequestService"]
