from server.ropi_main_service.persistence.async_connection import async_fetch_one
from server.ropi_main_service.persistence.connection import fetch_one
from server.ropi_main_service.persistence.sql_loader import load_sql


class GuideTrackingRepository:
    def __init__(self, *, fetch_one_func=None, async_fetch_one_func=None):
        self.fetch_one_func = fetch_one_func or fetch_one
        self.async_fetch_one_func = async_fetch_one_func or async_fetch_one

    def get_active_guide_task_for_robot(self, robot_id):
        target_robot_id = str(robot_id or "").strip()
        if not target_robot_id:
            return None

        return self.fetch_one_func(
            load_sql("guide/find_active_guide_task_for_robot.sql"),
            (target_robot_id,),
        )

    async def async_get_active_guide_task_for_robot(self, robot_id):
        target_robot_id = str(robot_id or "").strip()
        if not target_robot_id:
            return None

        return await self.async_fetch_one_func(
            load_sql("guide/find_active_guide_task_for_robot.sql"),
            (target_robot_id,),
        )


__all__ = ["GuideTrackingRepository"]
