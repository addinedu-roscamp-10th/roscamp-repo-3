import json

from server.ropi_main_service.application.delivery_config import (
    DEFAULT_DELIVERY_PINKY_ID,
    get_delivery_runtime_config,
)
from server.ropi_main_service.persistence.connection import fetch_all, fetch_one, get_connection
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
CANCELLABLE_DELIVERY_TASK_STATUSES = {
    "WAITING",
    "WAITING_DISPATCH",
    "READY",
    "ASSIGNED",
    "RUNNING",
}
CANCEL_FINALIZABLE_DELIVERY_TASK_STATUSES = {
    "CANCEL_REQUESTED",
}


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

    def get_delivery_task_cancel_target(self, task_id):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._build_cancel_task_response(
                result_code="REJECTED",
                result_message="task_id를 확인할 수 없습니다.",
                reason_code="TASK_ID_INVALID",
                task_id=None,
            )

        row = self._fetch_delivery_task_cancel_target(numeric_task_id)
        return self._build_cancel_target_response(row, task_id=numeric_task_id)

    async def async_get_delivery_task_cancel_target(self, task_id):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._build_cancel_task_response(
                result_code="REJECTED",
                result_message="task_id를 확인할 수 없습니다.",
                reason_code="TASK_ID_INVALID",
                task_id=None,
            )

        row = await async_fetch_one(
            load_sql("delivery/find_delivery_task_for_cancel.sql"),
            (numeric_task_id,),
        )
        return self._build_cancel_target_response(row, task_id=numeric_task_id)

    def record_delivery_task_cancel_result(self, *, task_id, cancel_response):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._build_cancel_task_response(
                result_code="REJECTED",
                result_message="task_id를 확인할 수 없습니다.",
                reason_code="TASK_ID_INVALID",
                task_id=None,
            )

        conn = get_connection()
        try:
            self._begin(conn)
            with conn.cursor() as cur:
                row = self._lock_delivery_task_cancel_target(cur, numeric_task_id)
                response = self._record_delivery_task_cancel_result(
                    cur,
                    row=row,
                    task_id=numeric_task_id,
                    cancel_response=cancel_response,
                )
                conn.commit()
                return response
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def async_record_delivery_task_cancel_result(self, *, task_id, cancel_response):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._build_cancel_task_response(
                result_code="REJECTED",
                result_message="task_id를 확인할 수 없습니다.",
                reason_code="TASK_ID_INVALID",
                task_id=None,
            )

        async with async_transaction() as cur:
            await cur.execute(
                load_sql("delivery/lock_delivery_task_for_cancel.sql"),
                (numeric_task_id,),
            )
            row = await cur.fetchone()
            return await self._async_record_delivery_task_cancel_result(
                cur,
                row=row,
                task_id=numeric_task_id,
                cancel_response=cancel_response,
            )

    def record_delivery_task_cancelled_result(self, *, task_id, workflow_response):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._build_cancelled_task_response(
                result_code="REJECTED",
                result_message="task_id를 확인할 수 없습니다.",
                reason_code="TASK_ID_INVALID",
                task_id=None,
                workflow_response=workflow_response,
            )

        conn = get_connection()
        try:
            self._begin(conn)
            with conn.cursor() as cur:
                row = self._lock_delivery_task_cancel_target(cur, numeric_task_id)
                response = self._record_delivery_task_cancelled_result(
                    cur,
                    row=row,
                    task_id=numeric_task_id,
                    workflow_response=workflow_response,
                )
                conn.commit()
                return response
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def async_record_delivery_task_cancelled_result(self, *, task_id, workflow_response):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._build_cancelled_task_response(
                result_code="REJECTED",
                result_message="task_id를 확인할 수 없습니다.",
                reason_code="TASK_ID_INVALID",
                task_id=None,
                workflow_response=workflow_response,
            )

        async with async_transaction() as cur:
            await cur.execute(
                load_sql("delivery/lock_delivery_task_for_cancel.sql"),
                (numeric_task_id,),
            )
            row = await cur.fetchone()
            return await self._async_record_delivery_task_cancelled_result(
                cur,
                row=row,
                task_id=numeric_task_id,
                workflow_response=workflow_response,
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
    def _parse_task_id(value):
        raw = str(value or "").strip()
        if not raw.isdigit():
            return None
        return int(raw)

    @staticmethod
    def _is_cancellable_task_status(task_status):
        return str(task_status or "").strip() in CANCELLABLE_DELIVERY_TASK_STATUSES

    @staticmethod
    def _build_cancel_target_response(row, *, task_id):
        if not row:
            return DeliveryRequestRepository._build_cancel_task_response(
                result_code="REJECTED",
                result_message="운반 task를 찾을 수 없습니다.",
                reason_code="TASK_NOT_FOUND",
                task_id=task_id,
            )

        if not DeliveryRequestRepository._is_cancellable_task_status(row.get("task_status")):
            return DeliveryRequestRepository._build_cancel_task_response(
                result_code="REJECTED",
                result_message="이미 종료되었거나 취소할 수 없는 운반 task입니다.",
                reason_code="TASK_NOT_CANCELLABLE",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                assigned_robot_id=row.get("assigned_robot_id"),
            )

        return DeliveryRequestRepository._build_cancel_task_response(
            result_code="ACCEPTED",
            task_id=row.get("task_id"),
            task_status=row.get("task_status"),
            assigned_robot_id=row.get("assigned_robot_id"),
        )

    def _fetch_delivery_task_cancel_target(self, task_id):
        return fetch_one(
            load_sql("delivery/find_delivery_task_for_cancel.sql"),
            (task_id,),
        )

    @staticmethod
    def _lock_delivery_task_cancel_target(cur, task_id):
        cur.execute(
            load_sql("delivery/lock_delivery_task_for_cancel.sql"),
            (task_id,),
        )
        return cur.fetchone()

    def _record_delivery_task_cancel_result(self, cur, *, row, task_id, cancel_response):
        if not row:
            return self._build_cancel_task_response(
                result_code="REJECTED",
                result_message="운반 task를 찾을 수 없습니다.",
                reason_code="TASK_NOT_FOUND",
                task_id=task_id,
            )

        if not self._is_cancellable_task_status(row.get("task_status")):
            return self._build_cancel_task_response(
                result_code="REJECTED",
                result_message="이미 종료되었거나 취소할 수 없는 운반 task입니다.",
                reason_code="TASK_NOT_CANCELLABLE",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                assigned_robot_id=row.get("assigned_robot_id"),
            )

        return self._write_cancel_result(cur, row=row, cancel_response=cancel_response)

    async def _async_record_delivery_task_cancel_result(self, cur, *, row, task_id, cancel_response):
        if not row:
            return self._build_cancel_task_response(
                result_code="REJECTED",
                result_message="운반 task를 찾을 수 없습니다.",
                reason_code="TASK_NOT_FOUND",
                task_id=task_id,
            )

        if not self._is_cancellable_task_status(row.get("task_status")):
            return self._build_cancel_task_response(
                result_code="REJECTED",
                result_message="이미 종료되었거나 취소할 수 없는 운반 task입니다.",
                reason_code="TASK_NOT_CANCELLABLE",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                assigned_robot_id=row.get("assigned_robot_id"),
            )

        return await self._async_write_cancel_result(cur, row=row, cancel_response=cancel_response)

    def _record_delivery_task_cancelled_result(self, cur, *, row, task_id, workflow_response):
        if not row:
            return self._build_cancelled_task_response(
                result_code="REJECTED",
                result_message="운반 task를 찾을 수 없습니다.",
                reason_code="TASK_NOT_FOUND",
                task_id=task_id,
                workflow_response=workflow_response,
            )

        if str(row.get("task_status") or "").strip() == "CANCELLED":
            return self._build_cancelled_task_response(
                result_code="CANCELLED",
                result_message="운반 task가 이미 취소 완료 상태입니다.",
                reason_code="ALREADY_CANCELLED",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                assigned_robot_id=row.get("assigned_robot_id"),
                workflow_response=workflow_response,
            )

        if str(row.get("task_status") or "").strip() not in CANCEL_FINALIZABLE_DELIVERY_TASK_STATUSES:
            return self._build_cancelled_task_response(
                result_code="IGNORED",
                result_message="취소 요청 상태가 아니므로 취소 완료로 확정하지 않았습니다.",
                reason_code="TASK_NOT_CANCEL_REQUESTED",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                assigned_robot_id=row.get("assigned_robot_id"),
                workflow_response=workflow_response,
            )

        return self._write_cancelled_result(cur, row=row, workflow_response=workflow_response)

    async def _async_record_delivery_task_cancelled_result(self, cur, *, row, task_id, workflow_response):
        if not row:
            return self._build_cancelled_task_response(
                result_code="REJECTED",
                result_message="운반 task를 찾을 수 없습니다.",
                reason_code="TASK_NOT_FOUND",
                task_id=task_id,
                workflow_response=workflow_response,
            )

        if str(row.get("task_status") or "").strip() == "CANCELLED":
            return self._build_cancelled_task_response(
                result_code="CANCELLED",
                result_message="운반 task가 이미 취소 완료 상태입니다.",
                reason_code="ALREADY_CANCELLED",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                assigned_robot_id=row.get("assigned_robot_id"),
                workflow_response=workflow_response,
            )

        if str(row.get("task_status") or "").strip() not in CANCEL_FINALIZABLE_DELIVERY_TASK_STATUSES:
            return self._build_cancelled_task_response(
                result_code="IGNORED",
                result_message="취소 요청 상태가 아니므로 취소 완료로 확정하지 않았습니다.",
                reason_code="TASK_NOT_CANCEL_REQUESTED",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                assigned_robot_id=row.get("assigned_robot_id"),
                workflow_response=workflow_response,
            )

        return await self._async_write_cancelled_result(cur, row=row, workflow_response=workflow_response)

    def _write_cancel_result(self, cur, *, row, cancel_response):
        result_code, result_message, reason_code = self._normalize_cancel_result(cancel_response)
        cancel_requested = bool((cancel_response or {}).get("cancel_requested"))
        task_status = row.get("task_status")
        phase = row.get("phase")

        if cancel_requested:
            cur.execute(
                load_sql("delivery/update_task_cancel_requested.sql"),
                ("USER_CANCEL_REQUESTED", result_code, result_message, row["task_id"]),
            )
            cur.execute(
                load_sql("delivery/insert_cancel_task_history.sql"),
                (
                    row["task_id"],
                    task_status,
                    phase,
                    "USER_CANCEL_REQUESTED",
                    result_message,
                    "control_service",
                ),
            )
            task_status = "CANCEL_REQUESTED"
            event_name = "DELIVERY_TASK_CANCEL_REQUESTED"
            severity = "INFO"
        else:
            event_name = "DELIVERY_TASK_CANCEL_REJECTED"
            severity = "WARNING"

        cur.execute(
            load_sql("delivery/insert_cancel_task_event.sql"),
            (
                row["task_id"],
                event_name,
                severity,
                row.get("assigned_robot_id"),
                result_code,
                reason_code,
                result_message,
                json.dumps(cancel_response or {}, ensure_ascii=False),
            ),
        )
        return self._build_cancel_task_response(
            result_code=result_code,
            result_message=result_message,
            reason_code=reason_code,
            task_id=row.get("task_id"),
            task_status=task_status,
            assigned_robot_id=row.get("assigned_robot_id"),
            cancel_requested=cancel_requested,
            ros_result=cancel_response,
        )

    def _write_cancelled_result(self, cur, *, row, workflow_response):
        result_code, result_message, reason_code = self._normalize_cancelled_workflow_result(workflow_response)
        cur.execute(
            load_sql("delivery/update_task_cancelled.sql"),
            (reason_code, result_code, result_message, row["task_id"]),
        )
        cur.execute(
            load_sql("delivery/insert_cancelled_task_history.sql"),
            (
                row["task_id"],
                row.get("task_status"),
                row.get("phase"),
                reason_code,
                result_message,
                "control_service",
            ),
        )
        cur.execute(
            load_sql("delivery/insert_cancel_task_event.sql"),
            (
                row["task_id"],
                "DELIVERY_TASK_CANCELLED",
                "INFO",
                row.get("assigned_robot_id"),
                result_code,
                reason_code,
                result_message,
                json.dumps(workflow_response or {}, ensure_ascii=False),
            ),
        )
        return self._build_cancelled_task_response(
            result_code=result_code,
            result_message=result_message,
            reason_code=reason_code,
            task_id=row.get("task_id"),
            task_status="CANCELLED",
            assigned_robot_id=row.get("assigned_robot_id"),
            workflow_response=workflow_response,
        )

    async def _async_write_cancel_result(self, cur, *, row, cancel_response):
        result_code, result_message, reason_code = self._normalize_cancel_result(cancel_response)
        cancel_requested = bool((cancel_response or {}).get("cancel_requested"))
        task_status = row.get("task_status")
        phase = row.get("phase")

        if cancel_requested:
            await cur.execute(
                load_sql("delivery/update_task_cancel_requested.sql"),
                ("USER_CANCEL_REQUESTED", result_code, result_message, row["task_id"]),
            )
            await cur.execute(
                load_sql("delivery/insert_cancel_task_history.sql"),
                (
                    row["task_id"],
                    task_status,
                    phase,
                    "USER_CANCEL_REQUESTED",
                    result_message,
                    "control_service",
                ),
            )
            task_status = "CANCEL_REQUESTED"
            event_name = "DELIVERY_TASK_CANCEL_REQUESTED"
            severity = "INFO"
        else:
            event_name = "DELIVERY_TASK_CANCEL_REJECTED"
            severity = "WARNING"

        await cur.execute(
            load_sql("delivery/insert_cancel_task_event.sql"),
            (
                row["task_id"],
                event_name,
                severity,
                row.get("assigned_robot_id"),
                result_code,
                reason_code,
                result_message,
                json.dumps(cancel_response or {}, ensure_ascii=False),
            ),
        )
        return self._build_cancel_task_response(
            result_code=result_code,
            result_message=result_message,
            reason_code=reason_code,
            task_id=row.get("task_id"),
            task_status=task_status,
            assigned_robot_id=row.get("assigned_robot_id"),
            cancel_requested=cancel_requested,
            ros_result=cancel_response,
        )

    async def _async_write_cancelled_result(self, cur, *, row, workflow_response):
        result_code, result_message, reason_code = self._normalize_cancelled_workflow_result(workflow_response)
        await cur.execute(
            load_sql("delivery/update_task_cancelled.sql"),
            (reason_code, result_code, result_message, row["task_id"]),
        )
        await cur.execute(
            load_sql("delivery/insert_cancelled_task_history.sql"),
            (
                row["task_id"],
                row.get("task_status"),
                row.get("phase"),
                reason_code,
                result_message,
                "control_service",
            ),
        )
        await cur.execute(
            load_sql("delivery/insert_cancel_task_event.sql"),
            (
                row["task_id"],
                "DELIVERY_TASK_CANCELLED",
                "INFO",
                row.get("assigned_robot_id"),
                result_code,
                reason_code,
                result_message,
                json.dumps(workflow_response or {}, ensure_ascii=False),
            ),
        )
        return self._build_cancelled_task_response(
            result_code=result_code,
            result_message=result_message,
            reason_code=reason_code,
            task_id=row.get("task_id"),
            task_status="CANCELLED",
            assigned_robot_id=row.get("assigned_robot_id"),
            workflow_response=workflow_response,
        )

    @staticmethod
    def _normalize_cancel_result(cancel_response):
        cancel_response = cancel_response or {}
        result_code = str(cancel_response.get("result_code") or "UNKNOWN").strip() or "UNKNOWN"
        result_message = cancel_response.get("result_message")
        if result_message is None:
            result_message = (
                "운반 task 취소 요청이 접수되었습니다."
                if cancel_response.get("cancel_requested")
                else "운반 task 취소 요청이 수락되지 않았습니다."
            )
        reason_code = cancel_response.get("reason_code")
        if reason_code is None:
            reason_code = (
                "USER_CANCEL_REQUESTED"
                if cancel_response.get("cancel_requested")
                else "ROS_CANCEL_NOT_ACCEPTED"
            )
        return result_code, result_message, reason_code

    @staticmethod
    def _normalize_cancelled_workflow_result(workflow_response):
        workflow_response = workflow_response or {}
        result_message = workflow_response.get("result_message") or "운반 task가 취소 완료되었습니다."
        return "CANCELLED", result_message, "ROS_ACTION_CANCELLED"

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
    def _build_cancel_task_response(
        *,
        result_code,
        result_message=None,
        reason_code=None,
        task_id=None,
        task_status=None,
        assigned_robot_id=None,
        cancel_requested=None,
        ros_result=None,
    ):
        response = DeliveryRequestRepository._build_delivery_task_response(
            result_code=result_code,
            result_message=result_message,
            reason_code=reason_code,
            task_id=task_id,
            task_status=task_status,
            assigned_robot_id=assigned_robot_id,
        )
        if cancel_requested is not None:
            response["cancel_requested"] = cancel_requested
        if ros_result is not None:
            response["ros_result"] = ros_result
        return response

    @staticmethod
    def _build_cancelled_task_response(
        *,
        result_code,
        result_message=None,
        reason_code=None,
        task_id=None,
        task_status=None,
        assigned_robot_id=None,
        workflow_response=None,
    ):
        response = DeliveryRequestRepository._build_delivery_task_response(
            result_code=result_code,
            result_message=result_message,
            reason_code=reason_code,
            task_id=task_id,
            task_status=task_status,
            assigned_robot_id=assigned_robot_id,
        )
        if workflow_response is not None:
            response["workflow_result"] = workflow_response
        return response


TaskRequestRepository = DeliveryRequestRepository

__all__ = ["DeliveryRequestRepository", "TaskRequestRepository"]
