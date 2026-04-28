import hashlib
import json

from server.ropi_main_service.application.delivery_config import (
    DEFAULT_DELIVERY_PINKY_ID,
    get_delivery_runtime_config,
)
from server.ropi_main_service.persistence.connection import fetch_all, get_connection


FIRST_PHASE_DELIVERY_PINKY_ID = DEFAULT_DELIVERY_PINKY_ID
DEFAULT_PICKUP_GOAL_POSE_ID = "pickup_supply"


class DeliveryRequestRepository:
    PRODUCT_SELECT_COLUMNS = """
        SELECT
            CAST(item_id AS CHAR) AS item_id,
            item_name,
            quantity,
            item_type,
            created_at,
            updated_at
        FROM item
    """

    def __init__(self, runtime_config=None):
        self.runtime_config = runtime_config or get_delivery_runtime_config()

    def get_all_products(self):
        query = f"""
            {self.PRODUCT_SELECT_COLUMNS}
            ORDER BY item_name
        """
        return fetch_all(query)

    def get_product_by_id(self, item_id, conn=None):
        numeric_item_id = self._parse_numeric_identifier(item_id)
        if numeric_item_id is None:
            return None

        return self._fetch_product("item_id = %s", (numeric_item_id,), conn=conn)

    def get_product_by_name(self, item_name, conn=None):
        return self._fetch_product("item_name = %s", (item_name,), conn=conn)

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
        request_hash = self._build_request_hash(
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
                existing_response = self._find_idempotent_response(
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

                task_id = self._insert_delivery_task(
                    cur,
                    request_id=request_id,
                    idempotency_key=idempotency_key,
                    caregiver_id=numeric_caregiver_id,
                    priority=priority,
                    destination_goal_pose_id=destination_goal_pose_id,
                )
                self._insert_delivery_detail(
                    cur,
                    task_id=task_id,
                    destination_goal_pose_id=destination_goal_pose_id,
                    notes=notes,
                )
                self._insert_delivery_item(
                    cur,
                    task_id=task_id,
                    item_id=numeric_item_id,
                    quantity=requested_quantity,
                )
                self._insert_initial_task_history(cur, task_id=task_id)
                self._insert_initial_task_event(cur, task_id=task_id)

                response = self._build_delivery_task_response(
                    result_code="ACCEPTED",
                    task_id=task_id,
                    task_status="WAITING_DISPATCH",
                    assigned_robot_id=self.runtime_config.pinky_id,
                )
                self._insert_idempotency_record(
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
                    """
                    INSERT INTO member_event (
                        member_id,
                        event_type_code,
                        event_type_name,
                        event_category,
                        severity,
                        event_name,
                        description,
                        event_at,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), NOW())
                    """,
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

    def _fetch_product(self, where_clause, params, *, conn=None):
        own_conn = False

        if conn is None:
            conn = get_connection()
            own_conn = True

        try:
            with conn.cursor() as cur:
                query = f"""
                    {self.PRODUCT_SELECT_COLUMNS}
                    WHERE {where_clause}
                    LIMIT 1
                """
                cur.execute(query, params)
                return cur.fetchone()
        finally:
            if own_conn:
                conn.close()

    def _insert_delivery_task(
        self,
        cur,
        *,
        request_id,
        idempotency_key,
        caregiver_id,
        priority,
        destination_goal_pose_id,
    ):
        cur.execute(
            """
            INSERT INTO task (
                task_type,
                request_id,
                idempotency_key,
                requester_type,
                requester_id,
                priority,
                task_status,
                phase,
                assigned_robot_id,
                map_id,
                created_at,
                updated_at
            )
            SELECT
                'DELIVERY',
                %s,
                %s,
                'CAREGIVER',
                %s,
                %s,
                'WAITING_DISPATCH',
                'REQUESTED',
                %s,
                gp.map_id,
                NOW(3),
                NOW(3)
            FROM goal_pose gp
            WHERE gp.goal_pose_id = %s
            LIMIT 1
            """,
            (
                request_id,
                idempotency_key,
                str(caregiver_id),
                priority or "NORMAL",
                self.runtime_config.pinky_id,
                destination_goal_pose_id,
            ),
        )
        return cur.lastrowid

    def _insert_delivery_detail(self, cur, *, task_id, destination_goal_pose_id, notes):
        cur.execute(
            """
            INSERT INTO delivery_task_detail (
                task_id,
                pickup_goal_pose_id,
                destination_goal_pose_id,
                pickup_arm_robot_id,
                dropoff_arm_robot_id,
                robot_slot_id,
                notes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                task_id,
                DEFAULT_PICKUP_GOAL_POSE_ID,
                destination_goal_pose_id,
                self.runtime_config.pickup_arm_robot_id,
                self.runtime_config.destination_arm_robot_id,
                self.runtime_config.robot_slot_id,
                notes,
            ),
        )

    @staticmethod
    def _insert_delivery_item(cur, *, task_id, item_id, quantity):
        cur.execute(
            """
            INSERT INTO delivery_task_item (
                task_id,
                item_id,
                requested_quantity,
                loaded_quantity,
                delivered_quantity,
                item_status,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, 0, 0, 'REQUESTED', NOW(), NOW())
            """,
            (task_id, item_id, quantity),
        )

    @staticmethod
    def _insert_initial_task_history(cur, *, task_id):
        cur.execute(
            """
            INSERT INTO task_state_history (
                task_id,
                from_status,
                to_status,
                from_phase,
                to_phase,
                reason_code,
                message,
                changed_by_component,
                changed_at
            )
            VALUES (
                %s,
                NULL,
                'WAITING_DISPATCH',
                NULL,
                'REQUESTED',
                NULL,
                %s,
                %s,
                NOW(3)
            )
            """,
            (task_id, "delivery task accepted", "control_service"),
        )

    @staticmethod
    def _insert_initial_task_event(cur, *, task_id):
        cur.execute(
            """
            INSERT INTO task_event_log (
                task_id,
                event_name,
                severity,
                component,
                result_code,
                message,
                occurred_at,
                created_at
            )
            VALUES (
                %s,
                'DELIVERY_TASK_ACCEPTED',
                'INFO',
                'control_service',
                'ACCEPTED',
                %s,
                NOW(3),
                NOW(3)
            )
            """,
            (task_id, "delivery task accepted"),
        )

    @staticmethod
    def _caregiver_exists(cur, caregiver_id) -> bool:
        cur.execute(
            """
            SELECT 1
            FROM caregiver
            WHERE caregiver_id = %s
            LIMIT 1
            """,
            (caregiver_id,),
        )
        return cur.fetchone() is not None

    @staticmethod
    def _goal_pose_exists(cur, goal_pose_id) -> bool:
        cur.execute(
            """
            SELECT 1
            FROM goal_pose
            WHERE goal_pose_id = %s
            LIMIT 1
            """,
            (goal_pose_id,),
        )
        return cur.fetchone() is not None

    @staticmethod
    def _find_idempotent_response(cur, *, requester_id, idempotency_key, request_hash):
        cur.execute(
            """
            SELECT request_hash, response_json
            FROM idempotency_record
            WHERE scope = 'DELIVERY_CREATE_TASK'
              AND requester_type = 'CAREGIVER'
              AND requester_id = %s
              AND idempotency_key = %s
            LIMIT 1
            """,
            (requester_id, idempotency_key),
        )
        row = cur.fetchone()
        if not row:
            return None

        if row.get("request_hash") != request_hash:
            return DeliveryRequestRepository._build_delivery_task_response(
                result_code="INVALID_REQUEST",
                result_message="같은 idempotency_key로 다른 요청 payload가 전달되었습니다.",
                reason_code="IDEMPOTENCY_KEY_CONFLICT",
            )

        response = row.get("response_json")
        if isinstance(response, dict):
            return response
        if response:
            return json.loads(response)
        return None

    @staticmethod
    def _insert_idempotency_record(
        cur,
        *,
        requester_id,
        idempotency_key,
        request_hash,
        response,
        task_id,
    ):
        cur.execute(
            """
            INSERT INTO idempotency_record (
                scope,
                requester_type,
                requester_id,
                idempotency_key,
                request_hash,
                response_json,
                task_id,
                expires_at,
                created_at
            )
            VALUES (
                'DELIVERY_CREATE_TASK',
                'CAREGIVER',
                %s,
                %s,
                %s,
                %s,
                %s,
                DATE_ADD(NOW(3), INTERVAL 1 DAY),
                NOW(3)
            )
            """,
            (
                requester_id,
                idempotency_key,
                request_hash,
                json.dumps(response, ensure_ascii=False),
                task_id,
            ),
        )

    @staticmethod
    def _build_request_hash(**payload) -> str:
        normalized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

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
