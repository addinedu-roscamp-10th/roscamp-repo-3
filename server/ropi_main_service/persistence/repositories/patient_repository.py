from server.ropi_main_service.persistence.async_connection import async_fetch_all, async_fetch_one
from server.ropi_main_service.persistence.connection import fetch_all, fetch_one
from server.ropi_main_service.persistence.sql_loader import load_sql


class PatientRepository:
    def find_member_by_name_and_room(self, name: str, room_no: str):
        return fetch_one(
            load_sql("patient/find_member_by_name_and_room.sql"),
            (name, room_no),
        )

    async def async_find_member_by_name_and_room(self, name: str, room_no: str):
        return await async_fetch_one(
            load_sql("patient/find_member_by_name_and_room.sql"),
            (name, room_no),
        )

    def get_recent_events(self, member_id: str, limit: int = 20):
        return fetch_all(
            load_sql("patient/recent_member_events.sql"),
            (member_id, limit),
        )

    async def async_get_recent_events(self, member_id: str, limit: int = 20):
        return await async_fetch_all(
            load_sql("patient/recent_member_events.sql"),
            (member_id, limit),
        )

    def get_preference(self, member_id: str):
        return fetch_one(load_sql("patient/member_preference.sql"), (member_id,))

    async def async_get_preference(self, member_id: str):
        return await async_fetch_one(
            load_sql("patient/member_preference.sql"),
            (member_id,),
        )

    def get_prescriptions(self, member_id: str):
        return fetch_all(load_sql("patient/prescriptions.sql"), (member_id,))

    async def async_get_prescriptions(self, member_id: str):
        return await async_fetch_all(
            load_sql("patient/prescriptions.sql"),
            (member_id,),
        )


__all__ = ["PatientRepository"]
