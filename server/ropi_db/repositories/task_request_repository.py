from server.ropi_db.connection import fetch_all, get_connection


FIRST_PHASE_DELIVERY_PINKY_ID = "pinky2"


class DeliveryRequestRepository:
    PRODUCT_SELECT_COLUMNS = """
        SELECT
            supply_id AS product_id,
            CAST(supply_id AS CHAR) AS item_id,
            item_name,
            quantity,
            supply_type,
            created_at,
            updated_at
        FROM supply
    """

    def get_all_products(self):
        query = f"""
            {self.PRODUCT_SELECT_COLUMNS}
            ORDER BY item_name
        """
        return fetch_all(query)

    def get_product_by_id(self, item_id, conn=None):
        numeric_supply_id = self._parse_supply_id(item_id)
        if numeric_supply_id is None:
            return None

        return self._fetch_product("supply_id = %s", (numeric_supply_id,), conn=conn)

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
        # Phase 1 delivery uses a fixed Pinky because orchestration/scheduling is not in scope yet.
        product = self.get_product_by_id(item_id)

        if not product:
            return self._build_delivery_task_response(
                result_code="REJECTED",
                result_message="요청한 item_id를 현재 물품 목록에서 찾을 수 없습니다.",
                reason_code="ITEM_NOT_FOUND",
            )

        return self._build_delivery_task_response(
            result_code="ACCEPTED",
            task_id=self._build_delivery_task_id(request_id, idempotency_key),
            task_status="WAITING_DISPATCH",
            assigned_pinky_id=FIRST_PHASE_DELIVERY_PINKY_ID,
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
            with conn.cursor() as cur:
                product = self.get_product_by_name(item_name, conn=conn)

                if not product:
                    conn.rollback()
                    return False, "선택한 물품이 존재하지 않습니다."

                product_id = product["product_id"]
                current_qty = product["quantity"]

                if quantity > current_qty:
                    conn.rollback()
                    return False, f"재고가 부족합니다. 현재 재고: {current_qty}"

                cur.execute(
                    """
                    UPDATE supply
                    SET
                        quantity = quantity - %s,
                        updated_at = NOW()
                    WHERE supply_id = %s
                    """,
                    (quantity, product_id),
                )

                description = (
                    f"[물품 요청] 물품종류={item_name}, 수량={quantity}, 목적지={destination}, "
                    f"우선순위={priority}, 설명={detail.strip() if detail and detail.strip() else '없음'}"
                )

                cur.execute(
                    """
                    INSERT INTO event (
                        event_name,
                        description,
                        event_at,
                        member_id,
                        event_type_id,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, NOW(), %s, %s, NOW(), NOW())
                    """,
                    ("물품 요청", description, str(member_id) if member_id else "MEM001", 2),
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

    @staticmethod
    def _parse_supply_id(item_id):
        raw = str(item_id or "").strip()

        if raw.lower().startswith("supply_"):
            raw = raw.split("_", 1)[1]

        if not raw.isdigit():
            return None

        return int(raw)

    @staticmethod
    def _build_delivery_task_id(request_id, idempotency_key):
        stable_suffix = str(idempotency_key or request_id).strip().replace(" ", "_")
        return f"task_delivery_{stable_suffix}"

    @staticmethod
    def _build_delivery_task_response(
        *,
        result_code,
        result_message=None,
        reason_code=None,
        task_id=None,
        task_status=None,
        assigned_pinky_id=None,
    ):
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "task_id": task_id,
            "task_status": task_status,
            "assigned_pinky_id": assigned_pinky_id,
        }


TaskRequestRepository = DeliveryRequestRepository

__all__ = ["DeliveryRequestRepository", "TaskRequestRepository"]
