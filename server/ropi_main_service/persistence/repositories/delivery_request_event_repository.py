from server.ropi_main_service.persistence.async_connection import async_execute
from server.ropi_main_service.persistence.connection import get_connection
from server.ropi_main_service.persistence.repositories.task_request_common import (
    parse_numeric_identifier,
)
from server.ropi_main_service.persistence.repositories.task_request_lookup_repository import (
    TaskRequestLookupRepository,
)
from server.ropi_main_service.persistence.sql_loader import load_sql


class DeliveryRequestEventRepository:
    def __init__(
        self,
        *,
        lookup_repository=None,
        connection_factory=None,
        async_execute_fn=None,
    ):
        self.lookup_repository = lookup_repository or TaskRequestLookupRepository()
        self.connection_factory = connection_factory or get_connection
        self.async_execute = async_execute_fn or async_execute

    def create_delivery_request(
        self,
        item_name,
        quantity,
        destination,
        priority,
        detail,
        member_id,
    ):
        conn = self.connection_factory()
        try:
            self._begin(conn)
            with conn.cursor() as cur:
                product = self.lookup_repository.get_product_by_name(
                    item_name,
                    conn=conn,
                )

                if not product:
                    conn.rollback()
                    return False, "선택한 물품이 존재하지 않습니다."

                current_qty = int(product["quantity"])
                if int(quantity) > current_qty:
                    conn.rollback()
                    return False, f"재고가 부족합니다. 현재 재고: {current_qty}"

                cur.execute(
                    load_sql("member_event/insert_member_event.sql"),
                    self._build_member_event_params(
                        item_name=item_name,
                        quantity=quantity,
                        destination=destination,
                        priority=priority,
                        detail=detail,
                        member_id=member_id,
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
            product = await self.lookup_repository.async_get_product_by_name(item_name)

            if not product:
                return False, "선택한 물품이 존재하지 않습니다."

            current_qty = int(product["quantity"])
            if int(quantity) > current_qty:
                return False, f"재고가 부족합니다. 현재 재고: {current_qty}"

            await self.async_execute(
                load_sql("member_event/insert_member_event.sql"),
                self._build_member_event_params(
                    item_name=item_name,
                    quantity=quantity,
                    destination=destination,
                    priority=priority,
                    detail=detail,
                    member_id=member_id,
                ),
            )

            return True, "물품 요청이 접수되었습니다."
        except Exception as exc:
            return False, f"물품 요청 등록 중 오류가 발생했습니다: {exc}"

    @staticmethod
    def _build_member_event_params(
        *,
        item_name,
        quantity,
        destination,
        priority,
        detail,
        member_id,
    ):
        description = (
            f"[물품 요청] 물품종류={item_name}, 수량={quantity}, 목적지={destination}, "
            f"우선순위={priority}, 설명={detail.strip() if detail and detail.strip() else '없음'}"
        )
        return (
            parse_numeric_identifier(member_id) or 1,
            "DELIVERY_REQUESTED",
            "물품 요청",
            "CARE",
            "INFO",
            "물품 요청",
            description,
        )

    @staticmethod
    def _begin(conn):
        if hasattr(conn, "begin"):
            conn.begin()


__all__ = ["DeliveryRequestEventRepository"]
