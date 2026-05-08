import inspect

from server.ropi_main_service.application.delivery_config import (
    DEFAULT_DELIVERY_PINKY_ID,
    get_delivery_runtime_config,
)
from server.ropi_main_service.application.patrol_config import get_patrol_runtime_config
from server.ropi_main_service.persistence.connection import fetch_one, get_connection
from server.ropi_main_service.persistence.repositories.delivery_task_repository import (
    DeliveryTaskRepository,
)
from server.ropi_main_service.persistence.repositories.delivery_task_create_repository import (
    DeliveryTaskCreateRepository,
)
from server.ropi_main_service.persistence.repositories.delivery_task_cancel_repository import (
    DeliveryTaskCancelRepository,
)
from server.ropi_main_service.persistence.repositories.delivery_task_result_repository import (
    DeliveryTaskResultRepository,
)
from server.ropi_main_service.persistence.repositories.idempotency_repository import (
    IdempotencyRepository,
)
from server.ropi_main_service.persistence.repositories.delivery_request_event_repository import (
    DeliveryRequestEventRepository,
)
from server.ropi_main_service.persistence.repositories.patrol_task_repository import (
    PatrolTaskRepository,
)
from server.ropi_main_service.persistence.repositories.patrol_task_create_repository import (
    PatrolPathSnapshotBuilder,
    PatrolTaskCreateRepository,
)
from server.ropi_main_service.persistence.repositories.patrol_task_cancel_repository import (
    PatrolTaskCancelRepository,
)
from server.ropi_main_service.persistence.repositories.patrol_task_result_repository import (
    PatrolTaskResultRepository,
)
from server.ropi_main_service.persistence.repositories.patrol_task_resume_repository import (
    PatrolTaskResumeRepository,
)
from server.ropi_main_service.persistence.repositories.task_request_common import (
    parse_numeric_identifier,
)
from server.ropi_main_service.persistence.repositories.task_request_lookup_repository import (
    TaskRequestLookupRepository,
)
from server.ropi_main_service.persistence.async_connection import (
    async_fetch_one,
    async_transaction,
)
from server.ropi_main_service.persistence.sql_loader import load_sql


FIRST_PHASE_DELIVERY_PINKY_ID = DEFAULT_DELIVERY_PINKY_ID


class TaskRequestRepository:
    def __init__(
        self,
        runtime_config=None,
        delivery_task_repository=None,
        delivery_task_create_repository=None,
        delivery_task_cancel_repository=None,
        delivery_task_result_repository=None,
        patrol_runtime_config=None,
        patrol_task_repository=None,
        patrol_task_create_repository=None,
        patrol_task_cancel_repository=None,
        patrol_task_result_repository=None,
        patrol_task_resume_repository=None,
        idempotency_repository=None,
        lookup_repository=None,
        delivery_request_event_repository=None,
    ):
        self.runtime_config = runtime_config or get_delivery_runtime_config()
        self.patrol_runtime_config = patrol_runtime_config or get_patrol_runtime_config()
        self.lookup_repository = lookup_repository or TaskRequestLookupRepository()
        self.delivery_task_repository = delivery_task_repository or DeliveryTaskRepository(
            runtime_config=self.runtime_config
        )
        self.delivery_task_cancel_repository = delivery_task_cancel_repository or DeliveryTaskCancelRepository()
        self.delivery_task_result_repository = delivery_task_result_repository or DeliveryTaskResultRepository()
        self.patrol_task_repository = patrol_task_repository or PatrolTaskRepository()
        self.patrol_task_cancel_repository = patrol_task_cancel_repository or PatrolTaskCancelRepository()
        self.patrol_task_result_repository = patrol_task_result_repository or PatrolTaskResultRepository()
        self.patrol_task_resume_repository = patrol_task_resume_repository or PatrolTaskResumeRepository()
        self.idempotency_repository = idempotency_repository or IdempotencyRepository()
        self.delivery_task_create_repository = (
            delivery_task_create_repository
            or DeliveryTaskCreateRepository(
                runtime_config=self.runtime_config,
                delivery_task_repository=self.delivery_task_repository,
                idempotency_repository=self.idempotency_repository,
                connection_factory=lambda: get_connection(),
                async_transaction_factory=lambda: async_transaction(),
                fetch_product_by_id=(
                    lambda cur, item_id, conn=None: self._fetch_product(
                        "item_id = %s",
                        (item_id,),
                        conn=conn,
                    )
                ),
                async_fetch_product_by_id=self._async_fetch_product_by_id,
                caregiver_exists=self._caregiver_exists,
                async_caregiver_exists=self._async_caregiver_exists,
                goal_pose_exists=self._goal_pose_exists,
                async_goal_pose_exists=self._async_goal_pose_exists,
            )
        )
        self.patrol_task_create_repository = (
            patrol_task_create_repository
            or PatrolTaskCreateRepository(
                runtime_config=self.patrol_runtime_config,
                patrol_task_repository=self.patrol_task_repository,
                idempotency_repository=self.idempotency_repository,
                connection_factory=lambda: get_connection(),
                async_transaction_factory=lambda: async_transaction(),
                caregiver_exists=self._caregiver_exists,
                async_caregiver_exists=self._async_caregiver_exists,
                fetch_patrol_area_by_id=self._fetch_patrol_area_by_id,
                async_fetch_patrol_area_by_id=self._async_fetch_patrol_area_by_id,
            )
        )
        self.delivery_request_event_repository = (
            delivery_request_event_repository
            or DeliveryRequestEventRepository(
                lookup_repository=self.lookup_repository,
            )
        )

    def get_all_products(self):
        return self.lookup_repository.get_all_products()

    async def async_get_all_products(self):
        return await self.lookup_repository.async_get_all_products()

    def get_enabled_goal_poses(self):
        return self._call_lookup_with_optional_map_id(
            self.lookup_repository.get_enabled_goal_poses,
            self.runtime_config.map_id,
        )

    async def async_get_enabled_goal_poses(self):
        return await self._async_call_lookup_with_optional_map_id(
            self.lookup_repository.async_get_enabled_goal_poses,
            self.runtime_config.map_id,
        )

    def get_delivery_destinations(self):
        return self._call_lookup_with_optional_map_id(
            self.lookup_repository.get_delivery_destinations,
            self.runtime_config.map_id,
        )

    async def async_get_delivery_destinations(self):
        return await self._async_call_lookup_with_optional_map_id(
            self.lookup_repository.async_get_delivery_destinations,
            self.runtime_config.map_id,
        )

    def get_patrol_areas(self):
        return self._call_lookup_with_optional_map_id(
            self.lookup_repository.get_patrol_areas,
            self.patrol_runtime_config.map_id,
        )

    async def async_get_patrol_areas(self):
        return await self._async_call_lookup_with_optional_map_id(
            self.lookup_repository.async_get_patrol_areas,
            self.patrol_runtime_config.map_id,
        )

    def get_product_by_id(self, item_id, conn=None):
        numeric_item_id = self._parse_numeric_identifier(item_id)
        if numeric_item_id is None:
            return None

        return self._fetch_product("item_id = %s", (numeric_item_id,), conn=conn)

    def get_product_by_name(self, item_name, conn=None):
        return self._fetch_product("item_name = %s", (item_name,), conn=conn)

    async def async_get_product_by_name(self, item_name):
        return await self.lookup_repository.async_get_product_by_name(item_name)

    @staticmethod
    def _accepts_map_id(method):
        parameters = inspect.signature(method).parameters
        return "map_id" in parameters or any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )

    @classmethod
    def _call_lookup_with_optional_map_id(cls, method, map_id):
        if cls._accepts_map_id(method):
            return method(map_id=map_id)
        return method()

    @classmethod
    async def _async_call_lookup_with_optional_map_id(cls, method, map_id):
        if cls._accepts_map_id(method):
            return await method(map_id=map_id)
        return await method()

    def create_delivery_task(
        self,
        request_id,
        caregiver_id,
        item_id,
        quantity,
        destination_id,
        priority,
        notes,
        idempotency_key,
    ):
        self._sync_delivery_task_create_repository_dependencies()
        return self.delivery_task_create_repository.create_delivery_task(
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
        notes,
        idempotency_key,
    ):
        self._sync_delivery_task_create_repository_dependencies()
        return await self.delivery_task_create_repository.async_create_delivery_task(
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
        self._sync_patrol_task_create_repository_dependencies()
        return self.patrol_task_create_repository.create_patrol_task(
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
        self._sync_patrol_task_create_repository_dependencies()
        return await self.patrol_task_create_repository.async_create_patrol_task(
            request_id=request_id,
            caregiver_id=caregiver_id,
            patrol_area_id=patrol_area_id,
            priority=priority,
            idempotency_key=idempotency_key,
        )

    def get_delivery_task_cancel_target(self, task_id):
        return self.delivery_task_cancel_repository.get_delivery_task_cancel_target(task_id)

    async def async_get_delivery_task_cancel_target(self, task_id):
        return await self.delivery_task_cancel_repository.async_get_delivery_task_cancel_target(task_id)

    def get_task_cancel_target(self, task_id):
        numeric_task_id = self._parse_numeric_identifier(task_id)
        if numeric_task_id is None:
            return self._build_task_cancel_target_response(
                result_code="REJECTED",
                result_message="task_id를 확인할 수 없습니다.",
                reason_code="TASK_ID_INVALID",
                task_id=None,
            )

        row = fetch_one(
            load_sql("task_request/find_task_cancel_target.sql"),
            (numeric_task_id,),
        )
        return self._format_task_cancel_target(row, task_id=numeric_task_id)

    async def async_get_task_cancel_target(self, task_id):
        numeric_task_id = self._parse_numeric_identifier(task_id)
        if numeric_task_id is None:
            return self._build_task_cancel_target_response(
                result_code="REJECTED",
                result_message="task_id를 확인할 수 없습니다.",
                reason_code="TASK_ID_INVALID",
                task_id=None,
            )

        row = await async_fetch_one(
            load_sql("task_request/find_task_cancel_target.sql"),
            (numeric_task_id,),
        )
        return self._format_task_cancel_target(row, task_id=numeric_task_id)

    def record_delivery_task_cancel_result(self, *, task_id, cancel_response):
        return self.delivery_task_cancel_repository.record_delivery_task_cancel_result(
            task_id=task_id,
            cancel_response=cancel_response,
        )

    async def async_record_delivery_task_cancel_result(self, *, task_id, cancel_response):
        return await self.delivery_task_cancel_repository.async_record_delivery_task_cancel_result(
            task_id=task_id,
            cancel_response=cancel_response,
        )

    def get_patrol_task_cancel_target(self, task_id):
        return self.patrol_task_cancel_repository.get_patrol_task_cancel_target(task_id)

    async def async_get_patrol_task_cancel_target(self, task_id):
        return await self.patrol_task_cancel_repository.async_get_patrol_task_cancel_target(task_id)

    def record_patrol_task_cancel_result(
        self,
        *,
        task_id,
        caregiver_id,
        reason,
        cancel_response,
    ):
        return self.patrol_task_cancel_repository.record_patrol_task_cancel_result(
            task_id=task_id,
            caregiver_id=caregiver_id,
            reason=reason,
            cancel_response=cancel_response,
        )

    async def async_record_patrol_task_cancel_result(
        self,
        *,
        task_id,
        caregiver_id,
        reason,
        cancel_response,
    ):
        return await self.patrol_task_cancel_repository.async_record_patrol_task_cancel_result(
            task_id=task_id,
            caregiver_id=caregiver_id,
            reason=reason,
            cancel_response=cancel_response,
        )

    def get_patrol_task_resume_target(self, task_id):
        return self.patrol_task_resume_repository.get_patrol_task_resume_target(task_id)

    async def async_get_patrol_task_resume_target(self, task_id):
        return await self.patrol_task_resume_repository.async_get_patrol_task_resume_target(task_id)

    def record_patrol_task_resume_result(
        self,
        *,
        task_id,
        caregiver_id,
        member_id,
        action_memo,
        resume_command_response,
    ):
        return self.patrol_task_resume_repository.record_patrol_task_resume_result(
            task_id=task_id,
            caregiver_id=caregiver_id,
            member_id=member_id,
            action_memo=action_memo,
            resume_command_response=resume_command_response,
        )

    async def async_record_patrol_task_resume_result(
        self,
        *,
        task_id,
        caregiver_id,
        member_id,
        action_memo,
        resume_command_response,
    ):
        return await self.patrol_task_resume_repository.async_record_patrol_task_resume_result(
            task_id=task_id,
            caregiver_id=caregiver_id,
            member_id=member_id,
            action_memo=action_memo,
            resume_command_response=resume_command_response,
        )

    def record_delivery_task_cancelled_result(self, *, task_id, workflow_response):
        return self.delivery_task_cancel_repository.record_delivery_task_cancelled_result(
            task_id=task_id,
            workflow_response=workflow_response,
        )

    async def async_record_delivery_task_cancelled_result(self, *, task_id, workflow_response):
        return await self.delivery_task_cancel_repository.async_record_delivery_task_cancelled_result(
            task_id=task_id,
            workflow_response=workflow_response,
        )

    def record_delivery_task_workflow_result(self, *, task_id, workflow_response):
        return self.delivery_task_result_repository.record_delivery_task_workflow_result(
            task_id=task_id,
            workflow_response=workflow_response,
        )

    async def async_record_delivery_task_workflow_result(self, *, task_id, workflow_response):
        return await self.delivery_task_result_repository.async_record_delivery_task_workflow_result(
            task_id=task_id,
            workflow_response=workflow_response,
        )

    async def async_record_patrol_task_workflow_result(self, *, task_id, workflow_response):
        return await self.patrol_task_result_repository.async_record_patrol_task_workflow_result(
            task_id=task_id,
            workflow_response=workflow_response,
        )

    def _sync_delivery_task_create_repository_dependencies(self):
        self.delivery_task_create_repository.runtime_config = self.runtime_config
        self.delivery_task_create_repository.delivery_task_repository = (
            self.delivery_task_repository
        )
        self.delivery_task_create_repository.idempotency_repository = (
            self.idempotency_repository
        )
        self.delivery_task_create_repository.connection_factory = lambda: get_connection()
        self.delivery_task_create_repository.async_transaction_factory = (
            lambda: async_transaction()
        )
        self.delivery_task_create_repository.fetch_product_by_id = (
            lambda cur, item_id, conn=None: self._fetch_product(
                "item_id = %s",
                (item_id,),
                conn=conn,
            )
        )
        self.delivery_task_create_repository.async_fetch_product_by_id = (
            self._async_fetch_product_by_id
        )
        self.delivery_task_create_repository.caregiver_exists = self._caregiver_exists
        self.delivery_task_create_repository.async_caregiver_exists = (
            self._async_caregiver_exists
        )
        self.delivery_task_create_repository.goal_pose_exists = self._goal_pose_exists
        self.delivery_task_create_repository.async_goal_pose_exists = (
            self._async_goal_pose_exists
        )

    def _sync_patrol_task_create_repository_dependencies(self):
        self.patrol_task_create_repository.runtime_config = self.patrol_runtime_config
        self.patrol_task_create_repository.patrol_task_repository = self.patrol_task_repository
        self.patrol_task_create_repository.idempotency_repository = self.idempotency_repository
        self.patrol_task_create_repository.connection_factory = lambda: get_connection()
        self.patrol_task_create_repository.async_transaction_factory = (
            lambda: async_transaction()
        )
        self.patrol_task_create_repository.caregiver_exists = self._caregiver_exists
        self.patrol_task_create_repository.async_caregiver_exists = (
            self._async_caregiver_exists
        )
        self.patrol_task_create_repository.fetch_patrol_area_by_id = (
            self._fetch_patrol_area_by_id
        )
        self.patrol_task_create_repository.async_fetch_patrol_area_by_id = (
            self._async_fetch_patrol_area_by_id
        )

    def create_delivery_request(
        self,
        item_name,
        quantity,
        destination,
        priority,
        detail,
        member_id,
    ):
        return self.delivery_request_event_repository.create_delivery_request(
            item_name=item_name,
            quantity=quantity,
            destination=destination,
            priority=priority,
            detail=detail,
            member_id=member_id,
        )

    async def async_create_delivery_request(
        self,
        item_name,
        quantity,
        destination,
        priority,
        detail,
        member_id,
    ):
        return await self.delivery_request_event_repository.async_create_delivery_request(
            item_name=item_name,
            quantity=quantity,
            destination=destination,
            priority=priority,
            detail=detail,
            member_id=member_id,
        )

    def _fetch_product(self, where_clause, params, *, conn=None):
        return self.lookup_repository.fetch_product(where_clause, params, conn=conn)

    async def _async_fetch_product_by_id(self, cur, item_id):
        return await self.lookup_repository.async_fetch_product_by_id(cur, item_id)

    def _product_query_for(self, where_clause):
        return self.lookup_repository.product_query_for(where_clause)

    def _caregiver_exists(self, cur, caregiver_id) -> bool:
        return self.lookup_repository.caregiver_exists(cur, caregiver_id)

    async def _async_caregiver_exists(self, cur, caregiver_id) -> bool:
        return await self.lookup_repository.async_caregiver_exists(cur, caregiver_id)

    def _goal_pose_exists(self, cur, goal_pose_id, *, map_id=None) -> bool:
        return self.lookup_repository.goal_pose_exists(
            cur,
            goal_pose_id,
            map_id=map_id or self.runtime_config.map_id,
        )

    async def _async_goal_pose_exists(self, cur, goal_pose_id, *, map_id=None) -> bool:
        return await self.lookup_repository.async_goal_pose_exists(
            cur,
            goal_pose_id,
            map_id=map_id or self.runtime_config.map_id,
        )

    def _fetch_patrol_area_by_id(self, cur, patrol_area_id):
        return self.lookup_repository.fetch_patrol_area_by_id(
            cur,
            patrol_area_id,
            map_id=self.patrol_runtime_config.map_id,
        )

    async def _async_fetch_patrol_area_by_id(self, cur, patrol_area_id):
        return await self.lookup_repository.async_fetch_patrol_area_by_id(
            cur,
            patrol_area_id,
            map_id=self.patrol_runtime_config.map_id,
        )

    @classmethod
    def _validate_patrol_area_for_create(cls, area):
        return PatrolTaskCreateRepository.validate_patrol_area_for_create(area)

    @staticmethod
    def _build_patrol_path_snapshot(area):
        return PatrolPathSnapshotBuilder.build(area)

    @classmethod
    def _format_task_cancel_target(cls, row, *, task_id):
        if not row:
            return cls._build_task_cancel_target_response(
                result_code="REJECTED",
                result_message="task를 찾을 수 없습니다.",
                reason_code="TASK_NOT_FOUND",
                task_id=task_id,
            )

        return cls._build_task_cancel_target_response(
            result_code="ACCEPTED",
            task_id=row.get("task_id"),
            task_type=row.get("task_type"),
            task_status=row.get("task_status"),
            phase=row.get("phase"),
            assigned_robot_id=row.get("assigned_robot_id"),
        )

    @staticmethod
    def _build_task_cancel_target_response(
        *,
        result_code,
        result_message=None,
        reason_code=None,
        task_id=None,
        task_type=None,
        task_status=None,
        phase=None,
        assigned_robot_id=None,
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
        }

    @staticmethod
    def _parse_numeric_identifier(value):
        return parse_numeric_identifier(value)

    @staticmethod
    def _begin(conn):
        if hasattr(conn, "begin"):
            conn.begin()

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


DeliveryRequestRepository = TaskRequestRepository

__all__ = ["TaskRequestRepository", "DeliveryRequestRepository"]
