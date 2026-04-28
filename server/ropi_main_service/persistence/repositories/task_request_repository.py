from server.ropi_main_service.application.delivery_config import (
    DEFAULT_DELIVERY_PINKY_ID,
    get_delivery_runtime_config,
)
from server.ropi_main_service.persistence.connection import fetch_all, get_connection
from server.ropi_main_service.persistence.repositories.delivery_task_repository import (
    DEFAULT_PICKUP_GOAL_POSE_ID,
    DeliveryTaskRepository,
)
from server.ropi_main_service.persistence.repositories.idempotency_repository import (
    IdempotencyRepository,
)
from server.ropi_main_service.persistence.async_connection import (
    async_execute,
    async_fetch_all,
    async_fetch_one,
    async_transaction,
)
from server.ropi_main_service.persistence.sql_loader import load_sql


FIRST_PHASE_DELIVERY_PINKY_ID = DEFAULT_DELIVERY_PINKY_ID


class DeliveryRequestRepository:
    def __init__(
        self,
        runtime_config=None,
        delivery_task_repository=None,
        idempotency_repository=None,
    ):
        self.runtime_config = runtime_config or get_delivery_runtime_config()
        self.delivery_task_repository = delivery_task_repository or DeliveryTaskRepository(
            runtime_config=self.runtime_config
        )
        self.idempotency_repository = idempotency_repository or IdempotencyRepository()

    def get_all_products(self):
        return fetch_all(load_sql("task_request/list_items.sql"))

    async def async_get_all_products(self):
        return await async_fetch_all(load_sql("task_request/list_items.sql"))

    def get_product_by_id(self, item_id, conn=None):
        numeric_item_id = self._parse_numeric_identifier(item_id)
        if numeric_item_id is None:
            return None

        return self._fetch_product("item_id = %s", (numeric_item_id,), conn=conn)

    def get_product_by_name(self, item_name, conn=None):
        return self._fetch_product("item_name = %s", (item_name,), conn=conn)

    async def async_get_product_by_name(self, item_name):
        return await async_fetch_one(
            load_sql("task_request/find_item_by_name.sql"),
            (item_name,),
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
            return self._build_delivery_task_response(
                result_code="REJECTED",
                result_message="요청한 item_id를 현재 물품 목록에서 찾을 수 없습니다.",
                reason_code="ITEM_NOT_FOUND",
            )

        if numeric_caregiver_id is None:
            return self._build_delivery_task_response(
                result_code="REJECTED",
                result_message="caregiver_id를 확인할 수 없습니다.",
                reason_code="REQUESTER_NOT_AUTHORIZED",
            )

        conn = get_connection()
        try:
            self._begin(conn)
            with conn.cursor() as cur:
                existing_response = self.idempotency_repository.find_response(
                    cur,
                    requester_id=str(numeric_caregiver_id),
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                )
                if existing_response is not None:
                    conn.commit()
                    return existing_response

                product = self._fetch_product("item_id = %s", (numeric_item_id,), conn=conn)
                if not product:
                    conn.rollback()
                    return self._build_delivery_task_response(
                        result_code="REJECTED",
                        result_message="요청한 item_id를 현재 물품 목록에서 찾을 수 없습니다.",
                        reason_code="ITEM_NOT_FOUND",
                    )

                current_quantity = int(product["quantity"])
                if requested_quantity > current_quantity:
                    conn.rollback()
                    return self._build_delivery_task_response(
                        result_code="REJECTED",
                        result_message=f"재고가 부족합니다. 현재 재고: {current_quantity}",
                        reason_code="ITEM_QUANTITY_INSUFFICIENT",
                    )

                if not self._caregiver_exists(cur, numeric_caregiver_id):
                    conn.rollback()
                    return self._build_delivery_task_response(
                        result_code="REJECTED",
                        result_message="요청자를 확인할 수 없습니다.",
                        reason_code="REQUESTER_NOT_AUTHORIZED",
                    )

                if not self._goal_pose_exists(cur, DEFAULT_PICKUP_GOAL_POSE_ID):
                    conn.rollback()
                    return self._build_delivery_task_response(
                        result_code="REJECTED",
                        result_message="운반 픽업 goal pose를 찾을 수 없습니다.",
                        reason_code="PICKUP_GOAL_POSE_NOT_FOUND",
                    )

                if not self._goal_pose_exists(cur, destination_goal_pose_id):
                    conn.rollback()
                    return self._build_delivery_task_response(
                        result_code="INVALID_REQUEST",
                        result_message=f"지원하지 않는 destination_id입니다: {destination_goal_pose_id}",
                        reason_code="DESTINATION_GOAL_POSE_NOT_FOUND",
                    )

                task_id = self.delivery_task_repository.create_delivery_task_records(
                    cur,
                    request_id=request_id,
                    idempotency_key=idempotency_key,
                    caregiver_id=numeric_caregiver_id,
                    priority=priority,
                    destination_goal_pose_id=destination_goal_pose_id,
                    notes=notes,
                    item_id=numeric_item_id,
                    quantity=requested_quantity,
                )

                response = self._build_delivery_task_response(
                    result_code="ACCEPTED",
                    task_id=task_id,
                    task_status="WAITING_DISPATCH",
                    assigned_robot_id=self.runtime_config.pinky_id,
                )
                self.idempotency_repository.insert_record(
                    cur,
                    requester_id=str(numeric_caregiver_id),
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    response=response,
                    task_id=task_id,
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
            return self._build_delivery_task_response(
                result_code="REJECTED",
                result_message="요청한 item_id를 현재 물품 목록에서 찾을 수 없습니다.",
                reason_code="ITEM_NOT_FOUND",
            )

        if numeric_caregiver_id is None:
            return self._build_delivery_task_response(
                result_code="REJECTED",
                result_message="caregiver_id를 확인할 수 없습니다.",
                reason_code="REQUESTER_NOT_AUTHORIZED",
            )

        async with async_transaction() as cur:
            existing_response = await self.idempotency_repository.async_find_response(
                cur,
                requester_id=str(numeric_caregiver_id),
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if existing_response is not None:
                return existing_response

            product = await self._async_fetch_product_by_id(cur, numeric_item_id)
            if not product:
                return self._build_delivery_task_response(
                    result_code="REJECTED",
                    result_message="요청한 item_id를 현재 물품 목록에서 찾을 수 없습니다.",
                    reason_code="ITEM_NOT_FOUND",
                )

            current_quantity = int(product["quantity"])
            if requested_quantity > current_quantity:
                return self._build_delivery_task_response(
                    result_code="REJECTED",
                    result_message=f"재고가 부족합니다. 현재 재고: {current_quantity}",
                    reason_code="ITEM_QUANTITY_INSUFFICIENT",
                )

            if not await self._async_caregiver_exists(cur, numeric_caregiver_id):
                return self._build_delivery_task_response(
                    result_code="REJECTED",
                    result_message="요청자를 확인할 수 없습니다.",
                    reason_code="REQUESTER_NOT_AUTHORIZED",
                )

            if not await self._async_goal_pose_exists(cur, DEFAULT_PICKUP_GOAL_POSE_ID):
                return self._build_delivery_task_response(
                    result_code="REJECTED",
                    result_message="운반 픽업 goal pose를 찾을 수 없습니다.",
                    reason_code="PICKUP_GOAL_POSE_NOT_FOUND",
                )

            if not await self._async_goal_pose_exists(cur, destination_goal_pose_id):
                return self._build_delivery_task_response(
                    result_code="INVALID_REQUEST",
                    result_message=f"지원하지 않는 destination_id입니다: {destination_goal_pose_id}",
                    reason_code="DESTINATION_GOAL_POSE_NOT_FOUND",
                )

            task_id = await self.delivery_task_repository.async_create_delivery_task_records(
                cur,
                request_id=request_id,
                idempotency_key=idempotency_key,
                caregiver_id=numeric_caregiver_id,
                priority=priority,
                destination_goal_pose_id=destination_goal_pose_id,
                notes=notes,
                item_id=numeric_item_id,
                quantity=requested_quantity,
            )

            response = self._build_delivery_task_response(
                result_code="ACCEPTED",
                task_id=task_id,
                task_status="WAITING_DISPATCH",
                assigned_robot_id=self.runtime_config.pinky_id,
            )
            await self.idempotency_repository.async_insert_record(
                cur,
                requester_id=str(numeric_caregiver_id),
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                response=response,
                task_id=task_id,
            )
            return response

    def create_delivery_request(
        self,
        item_name,
        quantity,
        destination,
        priority,
        detail,
        member_id,
    ):
        conn = get_connection()
        try:
            self._begin(conn)
            with conn.cursor() as cur:
                product = self.get_product_by_name(item_name, conn=conn)

                if not product:
                    conn.rollback()
                    return False, "선택한 물품이 존재하지 않습니다."

                current_qty = int(product["quantity"])
                if int(quantity) > current_qty:
                    conn.rollback()
                    return False, f"재고가 부족합니다. 현재 재고: {current_qty}"

                description = (
                    f"[물품 요청] 물품종류={item_name}, 수량={quantity}, 목적지={destination}, "
                    f"우선순위={priority}, 설명={detail.strip() if detail and detail.strip() else '없음'}"
                )

                cur.execute(
                    load_sql("member_event/insert_member_event.sql"),
                    (
                        self._parse_numeric_identifier(member_id) or 1,
                        "DELIVERY_REQUESTED",
                        "물품 요청",
                        "CARE",
                        "INFO",
                        "물품 요청",
                        description,
                    ),
                )

                conn.commit()
                return True, "물품 요청이 접수되었습니다."
        except Exception as exc:
            conn.rollback()
            return False, f"물품 요청 등록 중 오류가 발생했습니다: {exc}"
        finally:
            conn.close()

    async def async_create_delivery_request(
        self,
        item_name,
        quantity,
        destination,
        priority,
        detail,
        member_id,
    ):
        try:
            product = await self.async_get_product_by_name(item_name)

            if not product:
                return False, "선택한 물품이 존재하지 않습니다."

            current_qty = int(product["quantity"])
            if int(quantity) > current_qty:
                return False, f"재고가 부족합니다. 현재 재고: {current_qty}"

            description = (
                f"[물품 요청] 물품종류={item_name}, 수량={quantity}, 목적지={destination}, "
                f"우선순위={priority}, 설명={detail.strip() if detail and detail.strip() else '없음'}"
            )

            await async_execute(
                load_sql("member_event/insert_member_event.sql"),
                (
                    self._parse_numeric_identifier(member_id) or 1,
                    "DELIVERY_REQUESTED",
                    "물품 요청",
                    "CARE",
                    "INFO",
                    "물품 요청",
                    description,
                ),
            )

            return True, "물품 요청이 접수되었습니다."
        except Exception as exc:
            return False, f"물품 요청 등록 중 오류가 발생했습니다: {exc}"

    def _fetch_product(self, where_clause, params, *, conn=None):
        own_conn = False

        if conn is None:
            conn = get_connection()
            own_conn = True

        try:
            with conn.cursor() as cur:
                cur.execute(self._product_query_for(where_clause), params)
                return cur.fetchone()
        finally:
            if own_conn:
                conn.close()

    @staticmethod
    async def _async_fetch_product_by_id(cur, item_id):
        await cur.execute(
            load_sql("task_request/find_item_by_id.sql"),
            (item_id,),
        )
        return await cur.fetchone()

    @staticmethod
    def _product_query_for(where_clause):
        if where_clause == "item_id = %s":
            return load_sql("task_request/find_item_by_id.sql")
        if where_clause == "item_name = %s":
            return load_sql("task_request/find_item_by_name.sql")
        raise ValueError(f"Unsupported product lookup: {where_clause}")

    @staticmethod
    def _caregiver_exists(cur, caregiver_id) -> bool:
        cur.execute(
            load_sql("task_request/caregiver_exists.sql"),
            (caregiver_id,),
        )
        return cur.fetchone() is not None

    @staticmethod
    async def _async_caregiver_exists(cur, caregiver_id) -> bool:
        await cur.execute(
            load_sql("task_request/caregiver_exists.sql"),
            (caregiver_id,),
        )
        return await cur.fetchone() is not None

    @staticmethod
    def _goal_pose_exists(cur, goal_pose_id) -> bool:
        cur.execute(
            load_sql("task_request/goal_pose_exists.sql"),
            (goal_pose_id,),
        )
        return cur.fetchone() is not None

    @staticmethod
    async def _async_goal_pose_exists(cur, goal_pose_id) -> bool:
        await cur.execute(
            load_sql("task_request/goal_pose_exists.sql"),
            (goal_pose_id,),
        )
        return await cur.fetchone() is not None

    @staticmethod
    def _parse_numeric_identifier(value):
        raw = str(value or "").strip()
        if raw.isdigit():
            return int(raw)

        digits = "".join(ch for ch in raw if ch.isdigit())
        if not digits:
            return None
        return int(digits)

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


TaskRequestRepository = DeliveryRequestRepository

__all__ = ["DeliveryRequestRepository", "TaskRequestRepository"]
