from server.ropi_main_service.persistence.async_connection import async_execute, async_fetch_all
from server.ropi_main_service.persistence.connection import fetch_all, get_connection
from server.ropi_main_service.persistence.sql_loader import load_sql


class InventoryRepository:
    def get_all_products(self):
        return fetch_all(load_sql("inventory/list_items.sql"))

    async def async_get_all_products(self):
        return await async_fetch_all(load_sql("inventory/list_items.sql"))

    async def async_add_quantity(self, item_id, quantity):
        rowcount = await async_execute(
            load_sql("inventory/add_quantity.sql"),
            (quantity, item_id),
        )
        return rowcount > 0

    async def async_set_quantity(self, item_id, quantity):
        rowcount = await async_execute(
            load_sql("inventory/set_quantity.sql"),
            (quantity, item_id),
        )
        return rowcount > 0

    def add_quantity(self, item_id, quantity):
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(load_sql("inventory/add_quantity.sql"), (quantity, item_id))
                conn.commit()
                return cur.rowcount > 0
        finally:
            conn.close()

    def set_quantity(self, item_id, quantity):
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(load_sql("inventory/set_quantity.sql"), (quantity, item_id))
                conn.commit()
                return cur.rowcount > 0
        finally:
            conn.close()


__all__ = ["InventoryRepository"]
