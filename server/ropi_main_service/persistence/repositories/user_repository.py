from server.ropi_main_service.persistence.async_connection import async_fetch_one
from server.ropi_main_service.persistence.connection import fetch_one
from server.ropi_main_service.persistence.sql_loader import load_sql


class UserRepository:
    def find_user_for_login(self, login_id: str, role: str):
        normalized_role = (role or "").strip().lower()

        if normalized_role == "caregiver":
            return fetch_one(load_sql("user/find_caregiver_for_login.sql"), (login_id,))

        return fetch_one(load_sql("user/find_visitor_for_login.sql"), (login_id,))

    async def async_find_user_for_login(self, login_id: str, role: str):
        normalized_role = (role or "").strip().lower()

        if normalized_role == "caregiver":
            return await async_fetch_one(
                load_sql("user/find_caregiver_for_login.sql"),
                (login_id,),
            )

        return await async_fetch_one(
            load_sql("user/find_visitor_for_login.sql"),
            (login_id,),
        )


__all__ = ["UserRepository"]
