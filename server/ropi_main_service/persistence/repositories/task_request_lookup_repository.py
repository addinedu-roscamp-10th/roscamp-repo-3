from server.ropi_main_service.persistence.async_connection import (
    async_fetch_all,
    async_fetch_one,
)
from server.ropi_main_service.persistence.connection import fetch_all, get_connection
from server.ropi_main_service.persistence.sql_loader import load_sql


class TaskRequestLookupRepository:
    def __init__(self, *, delivery_map_id=None, patrol_map_id=None):
        from server.ropi_main_service.application.delivery_config import (
            DEFAULT_DELIVERY_MAP_ID,
        )
        from server.ropi_main_service.application.patrol_config import (
            DEFAULT_PATROL_MAP_ID,
        )

        self.delivery_map_id = str(delivery_map_id or DEFAULT_DELIVERY_MAP_ID).strip()
        self.patrol_map_id = str(patrol_map_id or DEFAULT_PATROL_MAP_ID).strip()

    def get_all_products(self):
        return fetch_all(load_sql("task_request/list_items.sql"))

    async def async_get_all_products(self):
        return await async_fetch_all(load_sql("task_request/list_items.sql"))

    def get_enabled_goal_poses(self, *, map_id=None):
        return fetch_all(
            load_sql("task_request/list_enabled_goal_poses.sql"),
            (str(map_id or self.delivery_map_id),),
        )

    async def async_get_enabled_goal_poses(self, *, map_id=None):
        return await async_fetch_all(
            load_sql("task_request/list_enabled_goal_poses.sql"),
            (str(map_id or self.delivery_map_id),),
        )

    def get_delivery_destinations(self, *, map_id=None):
        return fetch_all(
            load_sql("task_request/list_delivery_destinations.sql"),
            (str(map_id or self.delivery_map_id),),
        )

    async def async_get_delivery_destinations(self, *, map_id=None):
        return await async_fetch_all(
            load_sql("task_request/list_delivery_destinations.sql"),
            (str(map_id or self.delivery_map_id),),
        )

    def get_patrol_areas(self, *, map_id=None):
        return fetch_all(
            load_sql("task_request/list_patrol_areas.sql"),
            (str(map_id or self.patrol_map_id),),
        )

    async def async_get_patrol_areas(self, *, map_id=None):
        return await async_fetch_all(
            load_sql("task_request/list_patrol_areas.sql"),
            (str(map_id or self.patrol_map_id),),
        )

    def get_product_by_id(self, item_id, conn=None):
        return self.fetch_product("item_id = %s", (item_id,), conn=conn)

    def get_product_by_name(self, item_name, conn=None):
        return self.fetch_product("item_name = %s", (item_name,), conn=conn)

    async def async_get_product_by_name(self, item_name):
        return await async_fetch_one(
            load_sql("task_request/find_item_by_name.sql"),
            (item_name,),
        )

    def fetch_product(self, where_clause, params, *, conn=None):
        own_conn = False

        if conn is None:
            conn = get_connection()
            own_conn = True

        try:
            with conn.cursor() as cur:
                cur.execute(self.product_query_for(where_clause), params)
                return cur.fetchone()
        finally:
            if own_conn:
                conn.close()

    @staticmethod
    def product_query_for(where_clause):
        if where_clause == "item_id = %s":
            return load_sql("task_request/find_item_by_id.sql")
        if where_clause == "item_name = %s":
            return load_sql("task_request/find_item_by_name.sql")
        raise ValueError(f"Unsupported product lookup: {where_clause}")

    @staticmethod
    def caregiver_exists(cur, caregiver_id) -> bool:
        cur.execute(
            load_sql("task_request/caregiver_exists.sql"),
            (caregiver_id,),
        )
        return cur.fetchone() is not None

    @staticmethod
    async def async_caregiver_exists(cur, caregiver_id) -> bool:
        await cur.execute(
            load_sql("task_request/caregiver_exists.sql"),
            (caregiver_id,),
        )
        return await cur.fetchone() is not None

    def goal_pose_exists(self, cur, goal_pose_id, *, map_id=None) -> bool:
        cur.execute(
            load_sql("task_request/goal_pose_exists.sql"),
            (goal_pose_id, str(map_id or self.delivery_map_id)),
        )
        return cur.fetchone() is not None

    async def async_goal_pose_exists(self, cur, goal_pose_id, *, map_id=None) -> bool:
        await cur.execute(
            load_sql("task_request/goal_pose_exists.sql"),
            (goal_pose_id, str(map_id or self.delivery_map_id)),
        )
        return await cur.fetchone() is not None

    def fetch_patrol_area_by_id(self, cur, patrol_area_id, *, map_id=None):
        cur.execute(
            load_sql("task_request/find_patrol_area_by_id.sql"),
            (patrol_area_id, str(map_id or self.patrol_map_id)),
        )
        return cur.fetchone()

    async def async_fetch_patrol_area_by_id(self, cur, patrol_area_id, *, map_id=None):
        await cur.execute(
            load_sql("task_request/find_patrol_area_by_id.sql"),
            (patrol_area_id, str(map_id or self.patrol_map_id)),
        )
        return await cur.fetchone()

    @staticmethod
    async def async_fetch_product_by_id(cur, item_id):
        await cur.execute(
            load_sql("task_request/find_item_by_id.sql"),
            (item_id,),
        )
        return await cur.fetchone()


__all__ = ["TaskRequestLookupRepository"]
