from server.ropi_main_service.persistence.connection import fetch_all, get_connection


class InventoryRepository:
    def get_all_products(self):
        query = """
            SELECT
                CAST(item_id AS CHAR) AS item_id,
                item_name,
                quantity,
                item_type,
                created_at,
                updated_at
            FROM item
            ORDER BY item_name
        """
        return fetch_all(query)

    def add_quantity(self, item_id, quantity):
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                query = """
                    UPDATE item
                    SET
                        quantity = quantity + %s,
                        updated_at = NOW()
                    WHERE item_id = %s
                """
                cur.execute(query, (quantity, item_id))
                conn.commit()
                return cur.rowcount > 0
        finally:
            conn.close()


__all__ = ["InventoryRepository"]
