from server.ropi_main_service.persistence.async_connection import async_fetch_all, async_fetch_one
from server.ropi_main_service.persistence.connection import fetch_all, fetch_one
from server.ropi_main_service.persistence.sql_loader import load_sql


class CaregiverRepository:
    def get_dashboard_summary(self):
        return fetch_one(load_sql("caregiver/dashboard_summary.sql"))

    async def async_get_dashboard_summary(self):
        return await async_fetch_one(load_sql("caregiver/dashboard_summary.sql"))

    def get_robot_board(self):
        return fetch_all(load_sql("caregiver/robot_board.sql"))

    async def async_get_robot_board(self):
        return await async_fetch_all(load_sql("caregiver/robot_board.sql"))

    def get_timeline(self, limit=20):
        return fetch_all(load_sql("caregiver/timeline.sql"), (limit,))

    async def async_get_timeline(self, limit=20):
        return await async_fetch_all(load_sql("caregiver/timeline.sql"), (limit,))

    def get_flow_board_events(self, limit=50):
        return fetch_all(load_sql("caregiver/flow_board_events.sql"), (limit,))

    async def async_get_flow_board_events(self, limit=50):
        return await async_fetch_all(load_sql("caregiver/flow_board_events.sql"), (limit,))


__all__ = ["CaregiverRepository"]
