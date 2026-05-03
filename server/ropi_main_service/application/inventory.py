from server.ropi_main_service.persistence.repositories.inventory_repository import InventoryRepository


LOW_STOCK_THRESHOLD = 10


class InventoryService:
    def __init__(self, repository=None):
        self.repository = repository or InventoryRepository()

    def get_inventory_rows(self):
        return self.repository.get_all_products()

    async def async_get_inventory_rows(self):
        return await self.repository.async_get_all_products()

    def get_inventory_bundle(self):
        return self._format_inventory_bundle(self.repository.get_all_products())

    async def async_get_inventory_bundle(self):
        rows = await self.repository.async_get_all_products()
        return self._format_inventory_bundle(rows)

    def add_item_quantity(self, item_id, quantity_delta):
        item_id = self._normalize_item_id(item_id)
        quantity_delta = self._to_int(quantity_delta)

        if not item_id:
            return self._mutation_error("ITEM_ID_INVALID", "item_id가 필요합니다.")
        if quantity_delta is None or quantity_delta <= 0:
            return self._mutation_error(
                "QUANTITY_INVALID",
                "추가 수량은 1 이상이어야 합니다.",
                item_id=item_id,
            )

        updated = self.repository.add_quantity(item_id, quantity_delta)
        if not updated:
            return self._mutation_error(
                "ITEM_NOT_FOUND",
                "선택한 물품을 찾을 수 없습니다.",
                item_id=item_id,
            )

        return {
            "result_code": "UPDATED",
            "result_message": "재고가 추가되었습니다.",
            "item_id": item_id,
            "quantity_delta": quantity_delta,
        }

    async def async_add_item_quantity(self, item_id, quantity_delta):
        item_id = self._normalize_item_id(item_id)
        quantity_delta = self._to_int(quantity_delta)

        if not item_id:
            return self._mutation_error("ITEM_ID_INVALID", "item_id가 필요합니다.")
        if quantity_delta is None or quantity_delta <= 0:
            return self._mutation_error(
                "QUANTITY_INVALID",
                "추가 수량은 1 이상이어야 합니다.",
                item_id=item_id,
            )

        updated = await self.repository.async_add_quantity(item_id, quantity_delta)
        if not updated:
            return self._mutation_error(
                "ITEM_NOT_FOUND",
                "선택한 물품을 찾을 수 없습니다.",
                item_id=item_id,
            )

        return {
            "result_code": "UPDATED",
            "result_message": "재고가 추가되었습니다.",
            "item_id": item_id,
            "quantity_delta": quantity_delta,
        }

    def set_item_quantity(self, item_id, quantity):
        item_id = self._normalize_item_id(item_id)
        quantity = self._to_int(quantity)

        if not item_id:
            return self._mutation_error("ITEM_ID_INVALID", "item_id가 필요합니다.")
        if quantity is None or quantity < 0:
            return self._mutation_error(
                "QUANTITY_INVALID",
                "수정 수량은 0 이상이어야 합니다.",
                item_id=item_id,
            )

        updated = self.repository.set_quantity(item_id, quantity)
        if not updated:
            return self._mutation_error(
                "ITEM_NOT_FOUND",
                "선택한 물품을 찾을 수 없습니다.",
                item_id=item_id,
            )

        return {
            "result_code": "UPDATED",
            "result_message": "재고 수량이 수정되었습니다.",
            "item_id": item_id,
            "quantity": quantity,
        }

    async def async_set_item_quantity(self, item_id, quantity):
        item_id = self._normalize_item_id(item_id)
        quantity = self._to_int(quantity)

        if not item_id:
            return self._mutation_error("ITEM_ID_INVALID", "item_id가 필요합니다.")
        if quantity is None or quantity < 0:
            return self._mutation_error(
                "QUANTITY_INVALID",
                "수정 수량은 0 이상이어야 합니다.",
                item_id=item_id,
            )

        updated = await self.repository.async_set_quantity(item_id, quantity)
        if not updated:
            return self._mutation_error(
                "ITEM_NOT_FOUND",
                "선택한 물품을 찾을 수 없습니다.",
                item_id=item_id,
            )

        return {
            "result_code": "UPDATED",
            "result_message": "재고 수량이 수정되었습니다.",
            "item_id": item_id,
            "quantity": quantity,
        }

    def add_inventory(self, item_name, quantity):
        if not item_name:
            return False, "물품 종류를 선택하세요."

        if quantity <= 0:
            return False, "수량은 1 이상이어야 합니다."

        products = self.repository.get_all_products()
        product = next((row for row in products if row["item_name"] == item_name), None)

        if product is None:
            return False, "선택한 물품을 찾을 수 없습니다."

        result = self.add_item_quantity(product["item_id"], quantity)
        if result.get("result_code") != "UPDATED":
            return False, "재고 수량을 업데이트하지 못했습니다."

        return True, "재고가 추가되었습니다."

    async def async_add_inventory(self, item_name, quantity):
        if not item_name:
            return False, "물품 종류를 선택하세요."

        if quantity <= 0:
            return False, "수량은 1 이상이어야 합니다."

        products = await self.repository.async_get_all_products()
        product = next((row for row in products if row["item_name"] == item_name), None)

        if product is None:
            return False, "선택한 물품을 찾을 수 없습니다."

        result = await self.async_add_item_quantity(product["item_id"], quantity)
        if result.get("result_code") != "UPDATED":
            return False, "재고 수량을 업데이트하지 못했습니다."

        return True, "재고가 추가되었습니다."

    @classmethod
    def _format_inventory_bundle(cls, rows):
        items = [cls._format_item(row) for row in rows or [] if isinstance(row, dict)]
        low_stock_items = [
            item for item in items if item["quantity"] <= LOW_STOCK_THRESHOLD
        ]
        updated_values = [
            item["updated_at"] for item in items if item.get("updated_at")
        ]

        return {
            "summary": {
                "total_item_count": len(items),
                "total_quantity": sum(item["quantity"] for item in items),
                "low_stock_item_count": len(low_stock_items),
                "empty_item_count": sum(1 for item in items if item["quantity"] <= 0),
                "low_stock_threshold": LOW_STOCK_THRESHOLD,
                "last_updated_at": max(updated_values) if updated_values else None,
            },
            "items": items,
            "low_stock_items": low_stock_items,
        }

    @classmethod
    def _format_item(cls, row):
        item_type = row.get("item_type") or row.get("category") or ""
        return {
            "item_id": cls._normalize_item_id(row.get("item_id")),
            "item_type": str(item_type).strip(),
            "item_name": str(row.get("item_name") or "").strip(),
            "quantity": cls._to_int(row.get("quantity")) or 0,
            "updated_at": cls._isoformat(row.get("updated_at")),
        }

    @staticmethod
    def _mutation_error(reason_code, result_message, *, item_id=None):
        result_code = (
            "NOT_FOUND" if reason_code == "ITEM_NOT_FOUND" else "INVALID_REQUEST"
        )
        return {
            "result_code": result_code,
            "reason_code": reason_code,
            "result_message": result_message,
            "item_id": item_id,
        }

    @staticmethod
    def _normalize_item_id(item_id):
        return str(item_id or "").strip()

    @staticmethod
    def _to_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _isoformat(value):
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)


__all__ = ["InventoryService", "LOW_STOCK_THRESHOLD"]
