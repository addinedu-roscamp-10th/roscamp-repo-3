import json

from server.ropi_main_service.application.delivery_config import (
    DEFAULT_DELIVERY_PINKY_ID,
    get_delivery_runtime_config,
)
from server.ropi_main_service.application.patrol_config import get_patrol_runtime_config
from server.ropi_main_service.persistence.connection import fetch_all, fetch_one, get_connection
from server.ropi_main_service.persistence.repositories.delivery_task_repository import (
    DEFAULT_PICKUP_GOAL_POSE_ID,
    DeliveryTaskRepository,
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
from server.ropi_main_service.persistence.repositories.patrol_task_repository import (
    PatrolTaskRepository,
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
        delivery_task_cancel_repository=None,
        delivery_task_result_repository=None,
        patrol_runtime_config=None,
        patrol_task_repository=None,
        idempotency_repository=None,
    ):
        self.runtime_config = runtime_config or get_delivery_runtime_config()
        self.patrol_runtime_config = patrol_runtime_config or get_patrol_runtime_config()
        self.delivery_task_repository = delivery_task_repository or DeliveryTaskRepository(
            runtime_config=self.runtime_config
        )
        self.delivery_task_cancel_repository = delivery_task_cancel_repository or DeliveryTaskCancelRepository()
        self.delivery_task_result_repository = delivery_task_result_repository or DeliveryTaskResultRepository()
        self.patrol_task_repository = patrol_task_repository or PatrolTaskRepository()
        self.idempotency_repository = idempotency_repository or IdempotencyRepository()

    def get_all_products(self):
        return fetch_all(load_sql("task_request/list_items.sql"))

    async def async_get_all_products(self):
        return await async_fetch_all(load_sql("task_request/list_items.sql"))

    def get_enabled_goal_poses(self):
        return fetch_all(load_sql("task_request/list_enabled_goal_poses.sql"))

    async def async_get_enabled_goal_poses(self):
        return await async_fetch_all(
            load_sql("task_request/list_enabled_goal_poses.sql")
        )

    def get_delivery_destinations(self):
        return fetch_all(load_sql("task_request/list_delivery_destinations.sql"))

    async def async_get_delivery_destinations(self):
        return await async_fetch_all(
            load_sql("task_request/list_delivery_destinations.sql")
        )

    def get_patrol_areas(self):
        return fetch_all(load_sql("task_request/list_patrol_areas.sql"))

    async def async_get_patrol_areas(self):
        return await async_fetch_all(load_sql("task_request/list_patrol_areas.sql"))

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

    def create_patrol_task(
        self,
        request_id,
        caregiver_id,
        patrol_area_id,
        priority,
        idempotency_key,
    ):
        numeric_caregiver_id = self._parse_numeric_identifier(caregiver_id)
        normalized_area_id = str(patrol_area_id or "").strip()
        request_hash = self.idempotency_repository.build_request_hash(
            request_id=request_id,
            caregiver_id=numeric_caregiver_id,
            patrol_area_id=normalized_area_id,
            priority=priority,
        )

        if numeric_caregiver_id is None:
            return self._build_patrol_task_response(
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
                    scope="PATROL_CREATE_TASK",
                )
                if existing_response is not None:
                    conn.commit()
                    return existing_response

                if not self._caregiver_exists(cur, numeric_caregiver_id):
                    conn.rollback()
                    return self._build_patrol_task_response(
                        result_code="REJECTED",
                        result_message="요청자를 확인할 수 없습니다.",
                        reason_code="REQUESTER_NOT_AUTHORIZED",
                    )

                area = self._fetch_patrol_area_by_id(cur, normalized_area_id)
                area_response = self._validate_patrol_area_for_create(area)
                if area_response is not None:
                    conn.rollback()
                    return area_response

                snapshot = self._build_patrol_path_snapshot(area)
                task_id = self.patrol_task_repository.create_patrol_task_records(
                    cur,
                    request_id=request_id,
                    idempotency_key=idempotency_key,
                    caregiver_id=numeric_caregiver_id,
                    priority=priority,
                    assigned_robot_id=self.patrol_runtime_config.pinky_id,
                    patrol_area_id=normalized_area_id,
                    patrol_area_revision=int(area["revision"]),
                    patrol_area_name=area["patrol_area_name"],
                    map_id=area["map_id"],
                    frame_id=snapshot["frame_id"],
                    waypoint_count=snapshot["waypoint_count"],
                    path_snapshot_json=snapshot["path_json"],
                )

                response = self._build_patrol_task_response(
                    result_code="ACCEPTED",
                    task_id=task_id,
                    task_status="WAITING_DISPATCH",
                    assigned_robot_id=self.patrol_runtime_config.pinky_id,
                    patrol_area_id=normalized_area_id,
                    patrol_area_name=area["patrol_area_name"],
                    patrol_area_revision=int(area["revision"]),
                )
                self.idempotency_repository.insert_record(
                    cur,
                    requester_id=str(numeric_caregiver_id),
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    response=response,
                    task_id=task_id,
                    scope="PATROL_CREATE_TASK",
                )
                conn.commit()
                return response
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def async_create_patrol_task(
        self,
        request_id,
        caregiver_id,
        patrol_area_id,
        priority,
        idempotency_key,
    ):
        numeric_caregiver_id = self._parse_numeric_identifier(caregiver_id)
        normalized_area_id = str(patrol_area_id or "").strip()
        request_hash = self.idempotency_repository.build_request_hash(
            request_id=request_id,
            caregiver_id=numeric_caregiver_id,
            patrol_area_id=normalized_area_id,
            priority=priority,
        )

        if numeric_caregiver_id is None:
            return self._build_patrol_task_response(
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
                scope="PATROL_CREATE_TASK",
            )
            if existing_response is not None:
                return existing_response

            if not await self._async_caregiver_exists(cur, numeric_caregiver_id):
                return self._build_patrol_task_response(
                    result_code="REJECTED",
                    result_message="요청자를 확인할 수 없습니다.",
                    reason_code="REQUESTER_NOT_AUTHORIZED",
                )

            area = await self._async_fetch_patrol_area_by_id(cur, normalized_area_id)
            area_response = self._validate_patrol_area_for_create(area)
            if area_response is not None:
                return area_response

            snapshot = self._build_patrol_path_snapshot(area)
            task_id = await self.patrol_task_repository.async_create_patrol_task_records(
                cur,
                request_id=request_id,
                idempotency_key=idempotency_key,
                caregiver_id=numeric_caregiver_id,
                priority=priority,
                assigned_robot_id=self.patrol_runtime_config.pinky_id,
                patrol_area_id=normalized_area_id,
                patrol_area_revision=int(area["revision"]),
                patrol_area_name=area["patrol_area_name"],
                map_id=area["map_id"],
                frame_id=snapshot["frame_id"],
                waypoint_count=snapshot["waypoint_count"],
                path_snapshot_json=snapshot["path_json"],
            )

            response = self._build_patrol_task_response(
                result_code="ACCEPTED",
                task_id=task_id,
                task_status="WAITING_DISPATCH",
                assigned_robot_id=self.patrol_runtime_config.pinky_id,
                patrol_area_id=normalized_area_id,
                patrol_area_name=area["patrol_area_name"],
                patrol_area_revision=int(area["revision"]),
            )
            await self.idempotency_repository.async_insert_record(
                cur,
                requester_id=str(numeric_caregiver_id),
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                response=response,
                task_id=task_id,
                scope="PATROL_CREATE_TASK",
            )
            return response

    def get_delivery_task_cancel_target(self, task_id):
        return self.delivery_task_cancel_repository.get_delivery_task_cancel_target(task_id)

    async def async_get_delivery_task_cancel_target(self, task_id):
        return await self.delivery_task_cancel_repository.async_get_delivery_task_cancel_target(task_id)

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
    def _fetch_patrol_area_by_id(cur, patrol_area_id):
        cur.execute(
            load_sql("task_request/find_patrol_area_by_id.sql"),
            (patrol_area_id,),
        )
        return cur.fetchone()

    @staticmethod
    async def _async_fetch_patrol_area_by_id(cur, patrol_area_id):
        await cur.execute(
            load_sql("task_request/find_patrol_area_by_id.sql"),
            (patrol_area_id,),
        )
        return await cur.fetchone()

    @classmethod
    def _validate_patrol_area_for_create(cls, area):
        if not area:
            return cls._build_patrol_task_response(
                result_code="REJECTED",
                result_message="요청한 patrol_area_id를 찾을 수 없습니다.",
                reason_code="PATROL_AREA_NOT_FOUND",
            )

        if not bool(area.get("is_enabled")):
            return cls._build_patrol_task_response(
                result_code="REJECTED",
                result_message="비활성화된 순찰 구역입니다.",
                reason_code="PATROL_AREA_DISABLED",
            )

        try:
            cls._build_patrol_path_snapshot(area)
        except ValueError as exc:
            return cls._build_patrol_task_response(
                result_code="REJECTED",
                result_message=str(exc),
                reason_code="PATROL_PATH_CONFIG_MISSING",
            )

        return None

    @staticmethod
    def _build_patrol_path_snapshot(area):
        raw_path = area.get("path_json")
        if isinstance(raw_path, str):
            try:
                path_json = json.loads(raw_path)
            except json.JSONDecodeError as exc:
                raise ValueError("순찰 경로 JSON을 해석할 수 없습니다.") from exc
        elif isinstance(raw_path, dict):
            path_json = raw_path
        else:
            raise ValueError("순찰 경로 설정이 없습니다.")

        poses = path_json.get("poses")
        if not isinstance(poses, list) or not poses:
            raise ValueError("순찰 경로 waypoint가 비어 있습니다.")

        header = path_json.get("header") if isinstance(path_json.get("header"), dict) else {}
        frame_id = str(header.get("frame_id") or area.get("frame_id") or "map").strip()
        return {
            "path_json": path_json,
            "frame_id": frame_id or "map",
            "waypoint_count": len(poses),
        }

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


TaskRequestRepository = DeliveryRequestRepository

__all__ = ["DeliveryRequestRepository", "TaskRequestRepository"]
