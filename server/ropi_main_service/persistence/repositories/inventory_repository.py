from server.ropi_main_service.persistence.connection import fetch_all, get_connection


class InventoryRepository:
    def get_all_products(self):
        query = """
            SELECT
                supply_id AS product_id,
                item_name,
                quantity,
                supply_type,
                created_at,
                updated_at
            FROM supply
            ORDER BY item_name
        """
        return fetch_all(query)

    def add_quantity(self, product_id, quantity):
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                query = """
                    UPDATE supply
                    SET
                        quantity = quantity + %s,
                        updated_at = NOW()
                    WHERE supply_id = %s
                """
                cur.execute(query, (quantity, product_id))
                conn.commit()
                return cur.rowcount > 0
        finally:
            conn.close()


__all__ = ["InventoryRepository"]
