from server.ropi_db.connection import fetch_one


class UserRepository:
    def find_user_for_login(self, login_id: str, role: str):
        normalized_role = (role or "").strip().lower()

        if normalized_role == "caregiver":
            query = """
                SELECT
                    CAST(caregiver_id AS CHAR) AS user_id,
                    password AS user_password,
                    caregiver_name AS user_name
                FROM caregiver
                WHERE caregiver_id = %s
                LIMIT 1
            """
            return fetch_one(query, (login_id,))

        query = """
            SELECT
                visitor_id AS user_id,
                password AS user_password,
                visitor_name AS user_name
            FROM visitor
            WHERE visitor_id = %s
            LIMIT 1
        """
        return fetch_one(query, (login_id,))


__all__ = ["UserRepository"]
