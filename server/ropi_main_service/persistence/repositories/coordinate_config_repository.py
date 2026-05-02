from server.ropi_main_service.persistence.async_connection import (
    async_fetch_all,
    async_fetch_one,
)
from server.ropi_main_service.persistence.connection import fetch_all, fetch_one
from server.ropi_main_service.persistence.sql_loader import load_sql


ACTIVE_MAP_PROFILE_SQL = load_sql("coordinate_config/get_active_map_profile.sql")
LIST_OPERATION_ZONES_SQL = load_sql("coordinate_config/list_operation_zones.sql")
LIST_GOAL_POSES_SQL = load_sql("coordinate_config/list_goal_poses.sql")
LIST_PATROL_AREAS_SQL = load_sql("coordinate_config/list_patrol_areas.sql")


class CoordinateConfigRepository:
    def get_active_map_profile(self):
        return fetch_one(ACTIVE_MAP_PROFILE_SQL)

    async def async_get_active_map_profile(self):
        return await async_fetch_one(ACTIVE_MAP_PROFILE_SQL)

    def get_operation_zones(self, *, map_id, include_disabled=True):
        return fetch_all(
            LIST_OPERATION_ZONES_SQL,
            (str(map_id), bool(include_disabled)),
        )

    async def async_get_operation_zones(self, *, map_id, include_disabled=True):
        return await async_fetch_all(
            LIST_OPERATION_ZONES_SQL,
            (str(map_id), bool(include_disabled)),
        )

    def get_goal_poses(self, *, map_id, include_disabled=True):
        return fetch_all(
            LIST_GOAL_POSES_SQL,
            (str(map_id), bool(include_disabled)),
        )

    async def async_get_goal_poses(self, *, map_id, include_disabled=True):
        return await async_fetch_all(
            LIST_GOAL_POSES_SQL,
            (str(map_id), bool(include_disabled)),
        )

    def get_patrol_areas(self, *, map_id, include_disabled=True):
        return fetch_all(
            LIST_PATROL_AREAS_SQL,
            (str(map_id), bool(include_disabled)),
        )

    async def async_get_patrol_areas(self, *, map_id, include_disabled=True):
        return await async_fetch_all(
            LIST_PATROL_AREAS_SQL,
            (str(map_id), bool(include_disabled)),
        )


__all__ = [
    "ACTIVE_MAP_PROFILE_SQL",
    "LIST_GOAL_POSES_SQL",
    "LIST_OPERATION_ZONES_SQL",
    "LIST_PATROL_AREAS_SQL",
    "CoordinateConfigRepository",
]
