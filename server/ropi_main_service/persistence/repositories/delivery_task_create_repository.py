from server.ropi_main_service.application.delivery_config import (
    get_delivery_runtime_config,
)
from server.ropi_main_service.persistence.async_connection import async_transaction
from server.ropi_main_service.persistence.connection import get_connection
from server.ropi_main_service.persistence.repositories.delivery_task_repository import (
    DEFAULT_PICKUP_GOAL_POSE_ID,
    DeliveryTaskRepository,
)
from server.ropi_main_service.persistence.repositories.idempotency_repository import (
    IdempotencyRepository,
)
from server.ropi_main_service.persistence.repositories.task_request_common import (
    parse_numeric_identifier,
)
from server.ropi_main_service.persistence.repositories.task_request_lookup_repository import (
    TaskRequestLookupRepository,
)


DELIVERY_CREATE_SCOPE = "DELIVERY_CREATE_TASK"


class DeliveryTaskCreateRepository:
    def __init__(
        self,
        *,
        runtime_config=None,
        delivery_task_repository=None,
        idempotency_repository=None,
        lookup_repository=None,
        connection_factory=None,
        async_transaction_factory=None,
        fetch_product_by_id=None,
        async_fetch_product_by_id=None,
        caregiver_exists=None,
        async_caregiver_exists=None,
        goal_pose_exists=None,
        async_goal_pose_exists=None,
    ):
        self.runtime_config = runtime_config or get_delivery_runtime_config()
        self.delivery_task_repository = (
            delivery_task_repository
            or DeliveryTaskRepository(runtime_config=self.runtime_config)
        )
        self.idempotency_repository = idempotency_repository or IdempotencyRepository()
        self.lookup_repository = lookup_repository or TaskRequestLookupRepository()
        self.connection_factory = connection_factory or get_connection
        self.async_transaction_factory = async_transaction_factory or async_transaction
        self.fetch_product_by_id = fetch_product_by_id or self._fetch_product_by_id
        self.async_fetch_product_by_id = (
            async_fetch_product_by_id or self._async_fetch_product_by_id
        )
        self.caregiver_exists = caregiver_exists or self._caregiver_exists
        self.async_caregiver_exists = (
            async_caregiver_exists or self._async_caregiver_exists
        )
        self.goal_pose_exists = goal_pose_exists or self._goal_pose_exists
        self.async_goal_pose_exists = (
            async_goal_pose_exists or self._async_goal_pose_exists
        )

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
        numeric_item_id = self._parse_numeric_identifier(item_id)
        numeric_caregiver_id = self._parse_numeric_identifier(caregiver_id)
        requested_quantity = int(quantity)
        destination_goal_pose_id = str(destination_id or "").strip()
        request_hash = self.idempotency_repository.build_request_hash(
            request_id=request_id,
            caregiver_id=numeric_caregiver_id,
            item_id=numeric_item_id,
            quantity=requested_quantity,
            destination_id=destination_goal_pose_id,
            priority=priority,
            notes=notes,
        )

        if numeric_item_id is None:
            return self.build_delivery_task_response(
                result_code="REJECTED",
                result_message="요청한 item_id를 현재 물품 목록에서 찾을 수 없습니다.",
                reason_code="ITEM_NOT_FOUND",
            )

        if numeric_caregiver_id is None:
            return self.build_delivery_task_response(
                result_code="REJECTED",
                result_message="caregiver_id를 확인할 수 없습니다.",
                reason_code="REQUESTER_NOT_AUTHORIZED",
            )

        conn = self.connection_factory()
        try:
            self._begin(conn)
            with conn.cursor() as cur:
                existing_response = self.idempotency_repository.find_response(
                    cur,
                    requester_id=str(numeric_caregiver_id),
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    scope=DELIVERY_CREATE_SCOPE,
                )
                if existing_response is not None:
                    conn.commit()
                    return existing_response

                product = self.fetch_product_by_id(
                    cur,
                    numeric_item_id,
                    conn=conn,
                )
                if not product:
                    conn.rollback()
                    return self.build_delivery_task_response(
                        result_code="REJECTED",
                        result_message=(
                            "요청한 item_id를 현재 물품 목록에서 찾을 수 없습니다."
                        ),
                        reason_code="ITEM_NOT_FOUND",
                    )

                current_quantity = int(product["quantity"])
                if requested_quantity > current_quantity:
                    conn.rollback()
                    return self.build_delivery_task_response(
                        result_code="REJECTED",
                        result_message=f"재고가 부족합니다. 현재 재고: {current_quantity}",
                        reason_code="ITEM_QUANTITY_INSUFFICIENT",
                    )

                if not self.caregiver_exists(cur, numeric_caregiver_id):
                    conn.rollback()
                    return self.build_delivery_task_response(
                        result_code="REJECTED",
                        result_message="요청자를 확인할 수 없습니다.",
                        reason_code="REQUESTER_NOT_AUTHORIZED",
                    )

                if not self.goal_pose_exists(cur, DEFAULT_PICKUP_GOAL_POSE_ID):
                    conn.rollback()
                    return self.build_delivery_task_response(
                        result_code="REJECTED",
                        result_message="운반 픽업 goal pose를 찾을 수 없습니다.",
                        reason_code="PICKUP_GOAL_POSE_NOT_FOUND",
                    )

                if not self.goal_pose_exists(cur, destination_goal_pose_id):
                    conn.rollback()
                    return self.build_delivery_task_response(
                        result_code="INVALID_REQUEST",
                        result_message=(
                            f"지원하지 않는 destination_id입니다: {destination_goal_pose_id}"
                        ),
                        reason_code="DESTINATION_GOAL_POSE_NOT_FOUND",
                    )

                response = self._create_accepted_delivery_task(
                    cur,
                    request_id=request_id,
                    caregiver_id=numeric_caregiver_id,
                    item_id=numeric_item_id,
                    quantity=requested_quantity,
                    destination_goal_pose_id=destination_goal_pose_id,
                    priority=priority,
                    notes=notes,
                    idempotency_key=idempotency_key,
                )
                self.idempotency_repository.insert_record(
                    cur,
                    requester_id=str(numeric_caregiver_id),
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    response=response,
                    task_id=response["task_id"],
                    scope=DELIVERY_CREATE_SCOPE,
                )
                conn.commit()
                return response
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

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
        numeric_item_id = self._parse_numeric_identifier(item_id)
        numeric_caregiver_id = self._parse_numeric_identifier(caregiver_id)
        requested_quantity = int(quantity)
        destination_goal_pose_id = str(destination_id or "").strip()
        request_hash = self.idempotency_repository.build_request_hash(
            request_id=request_id,
            caregiver_id=numeric_caregiver_id,
            item_id=numeric_item_id,
            quantity=requested_quantity,
            destination_id=destination_goal_pose_id,
            priority=priority,
            notes=notes,
        )

        if numeric_item_id is None:
            return self.build_delivery_task_response(
                result_code="REJECTED",
                result_message="요청한 item_id를 현재 물품 목록에서 찾을 수 없습니다.",
                reason_code="ITEM_NOT_FOUND",
            )

        if numeric_caregiver_id is None:
            return self.build_delivery_task_response(
                result_code="REJECTED",
                result_message="caregiver_id를 확인할 수 없습니다.",
                reason_code="REQUESTER_NOT_AUTHORIZED",
            )

        async with self.async_transaction_factory() as cur:
            existing_response = await self.idempotency_repository.async_find_response(
                cur,
                requester_id=str(numeric_caregiver_id),
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                scope=DELIVERY_CREATE_SCOPE,
            )
            if existing_response is not None:
                return existing_response

            product = await self.async_fetch_product_by_id(cur, numeric_item_id)
            if not product:
                return self.build_delivery_task_response(
                    result_code="REJECTED",
                    result_message="요청한 item_id를 현재 물품 목록에서 찾을 수 없습니다.",
                    reason_code="ITEM_NOT_FOUND",
                )

            current_quantity = int(product["quantity"])
            if requested_quantity > current_quantity:
                return self.build_delivery_task_response(
                    result_code="REJECTED",
                    result_message=f"재고가 부족합니다. 현재 재고: {current_quantity}",
                    reason_code="ITEM_QUANTITY_INSUFFICIENT",
                )

            if not await self.async_caregiver_exists(cur, numeric_caregiver_id):
                return self.build_delivery_task_response(
                    result_code="REJECTED",
                    result_message="요청자를 확인할 수 없습니다.",
                    reason_code="REQUESTER_NOT_AUTHORIZED",
                )

            if not await self.async_goal_pose_exists(cur, DEFAULT_PICKUP_GOAL_POSE_ID):
                return self.build_delivery_task_response(
                    result_code="REJECTED",
                    result_message="운반 픽업 goal pose를 찾을 수 없습니다.",
                    reason_code="PICKUP_GOAL_POSE_NOT_FOUND",
                )

            if not await self.async_goal_pose_exists(cur, destination_goal_pose_id):
                return self.build_delivery_task_response(
                    result_code="INVALID_REQUEST",
                    result_message=(
                        f"지원하지 않는 destination_id입니다: {destination_goal_pose_id}"
                    ),
                    reason_code="DESTINATION_GOAL_POSE_NOT_FOUND",
                )

            response = await self._async_create_accepted_delivery_task(
                cur,
                request_id=request_id,
                caregiver_id=numeric_caregiver_id,
                item_id=numeric_item_id,
                quantity=requested_quantity,
                destination_goal_pose_id=destination_goal_pose_id,
                priority=priority,
                notes=notes,
                idempotency_key=idempotency_key,
            )
            await self.idempotency_repository.async_insert_record(
                cur,
                requester_id=str(numeric_caregiver_id),
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                response=response,
                task_id=response["task_id"],
                scope=DELIVERY_CREATE_SCOPE,
            )
            return response

    def _create_accepted_delivery_task(
        self,
        cur,
        *,
        request_id,
        caregiver_id,
        item_id,
        quantity,
        destination_goal_pose_id,
        priority,
        notes,
        idempotency_key,
    ):
        task_id = self.delivery_task_repository.create_delivery_task_records(
            cur,
            request_id=request_id,
            idempotency_key=idempotency_key,
            caregiver_id=caregiver_id,
            priority=priority,
            destination_goal_pose_id=destination_goal_pose_id,
            notes=notes,
            item_id=item_id,
            quantity=quantity,
        )
        return self.build_delivery_task_response(
            result_code="ACCEPTED",
            task_id=task_id,
            task_status="WAITING_DISPATCH",
            assigned_robot_id=self.runtime_config.pinky_id,
        )

    async def _async_create_accepted_delivery_task(
        self,
        cur,
        *,
        request_id,
        caregiver_id,
        item_id,
        quantity,
        destination_goal_pose_id,
        priority,
        notes,
        idempotency_key,
    ):
        task_id = await self.delivery_task_repository.async_create_delivery_task_records(
            cur,
            request_id=request_id,
            idempotency_key=idempotency_key,
            caregiver_id=caregiver_id,
            priority=priority,
            destination_goal_pose_id=destination_goal_pose_id,
            notes=notes,
            item_id=item_id,
            quantity=quantity,
        )
        return self.build_delivery_task_response(
            result_code="ACCEPTED",
            task_id=task_id,
            task_status="WAITING_DISPATCH",
            assigned_robot_id=self.runtime_config.pinky_id,
        )

    def _fetch_product_by_id(self, cur, item_id, *, conn=None):
        return self.lookup_repository.fetch_product("item_id = %s", (item_id,), conn=conn)

    async def _async_fetch_product_by_id(self, cur, item_id):
        return await self.lookup_repository.async_fetch_product_by_id(cur, item_id)

    def _caregiver_exists(self, cur, caregiver_id):
        return self.lookup_repository.caregiver_exists(cur, caregiver_id)

    async def _async_caregiver_exists(self, cur, caregiver_id):
        return await self.lookup_repository.async_caregiver_exists(cur, caregiver_id)

    def _goal_pose_exists(self, cur, goal_pose_id):
        return self.lookup_repository.goal_pose_exists(
            cur,
            goal_pose_id,
            map_id=self.runtime_config.map_id,
        )

    async def _async_goal_pose_exists(self, cur, goal_pose_id):
        return await self.lookup_repository.async_goal_pose_exists(
            cur,
            goal_pose_id,
            map_id=self.runtime_config.map_id,
        )

    @staticmethod
    def _parse_numeric_identifier(value):
        return parse_numeric_identifier(value)

    @staticmethod
    def _begin(conn):
        if hasattr(conn, "begin"):
            conn.begin()

    @staticmethod
    def build_delivery_task_response(
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


__all__ = ["DELIVERY_CREATE_SCOPE", "DeliveryTaskCreateRepository"]
