from server.ropi_main_service.persistence.repositories.inventory_repository import InventoryRepository


class InventoryService:
    def __init__(self, repository=None):
        self.repository = repository or InventoryRepository()

    def get_inventory_rows(self):
        return self.repository.get_all_products()

    async def async_get_inventory_rows(self):
        return await self.repository.async_get_all_products()

    def add_inventory(self, item_name, quantity):
        if not item_name:
            return False, "물품 종류를 선택하세요."

        if quantity <= 0:
            return False, "수량은 1 이상이어야 합니다."

        products = self.repository.get_all_products()
        product = next((row for row in products if row["item_name"] == item_name), None)

        if product is None:
            return False, "선택한 물품을 찾을 수 없습니다."

        updated = self.repository.add_quantity(product["item_id"], quantity)
        if not updated:
            return False, "재고 수량을 업데이트하지 못했습니다."

        return True, "재고가 추가되었습니다."


__all__ = ["InventoryService"]
