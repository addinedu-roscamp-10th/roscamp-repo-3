from server.ropi_main_service.persistence.async_connection import (
    async_fetch_all,
    async_fetch_one,
    async_transaction,
)
from server.ropi_main_service.persistence.connection import (
    fetch_all,
    fetch_one,
    get_connection,
)
from server.ropi_main_service.persistence.sql_loader import load_sql


ACTIVE_MAP_PROFILE_SQL = load_sql("coordinate_config/get_active_map_profile.sql")
FIND_OPERATION_ZONE_SQL = load_sql("coordinate_config/find_operation_zone.sql")
INSERT_OPERATION_ZONE_SQL = load_sql("coordinate_config/insert_operation_zone.sql")
LIST_OPERATION_ZONES_SQL = load_sql("coordinate_config/list_operation_zones.sql")
LIST_GOAL_POSES_SQL = load_sql("coordinate_config/list_goal_poses.sql")
LIST_PATROL_AREAS_SQL = load_sql("coordinate_config/list_patrol_areas.sql")
LOCK_OPERATION_ZONE_SQL = load_sql("coordinate_config/lock_operation_zone.sql")
UPDATE_OPERATION_ZONE_SQL = load_sql("coordinate_config/update_operation_zone.sql")


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

    def get_operation_zone(self, *, zone_id):
        return fetch_one(FIND_OPERATION_ZONE_SQL, (str(zone_id),))

    async def async_get_operation_zone(self, *, zone_id):
        return await async_fetch_one(FIND_OPERATION_ZONE_SQL, (str(zone_id),))

    def create_operation_zone(
        self,
        *,
        map_id,
        zone_id,
        zone_name,
        zone_type,
        is_enabled=True,
    ):
        conn = get_connection()
        try:
            conn.begin()
            with conn.cursor() as cur:
                cur.execute(
                    INSERT_OPERATION_ZONE_SQL,
                    (
                        str(zone_id),
                        str(map_id),
                        str(zone_name),
                        str(zone_type),
                        bool(is_enabled),
                    ),
                )
                cur.execute(FIND_OPERATION_ZONE_SQL, (str(zone_id),))
                row = cur.fetchone()
            conn.commit()
            return row
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def async_create_operation_zone(
        self,
        *,
        map_id,
        zone_id,
        zone_name,
        zone_type,
        is_enabled=True,
    ):
        async with async_transaction() as cur:
            await cur.execute(
                INSERT_OPERATION_ZONE_SQL,
                (
                    str(zone_id),
                    str(map_id),
                    str(zone_name),
                    str(zone_type),
                    bool(is_enabled),
                ),
            )
            await cur.execute(FIND_OPERATION_ZONE_SQL, (str(zone_id),))
            return await cur.fetchone()

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

    def update_operation_zone(
        self,
        *,
        map_id,
        zone_id,
        expected_revision,
        zone_name,
        zone_type,
        is_enabled,
    ):
        conn = get_connection()
        try:
            conn.begin()
            with conn.cursor() as cur:
                result = self._update_operation_zone_with_cursor(
                    cur,
                    map_id=map_id,
                    zone_id=zone_id,
                    expected_revision=expected_revision,
                    zone_name=zone_name,
                    zone_type=zone_type,
                    is_enabled=is_enabled,
                )
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def async_update_operation_zone(
        self,
        *,
        map_id,
        zone_id,
        expected_revision,
        zone_name,
        zone_type,
        is_enabled,
    ):
        async with async_transaction() as cur:
            await cur.execute(
                LOCK_OPERATION_ZONE_SQL,
                (str(zone_id), str(map_id)),
            )
            row = await cur.fetchone()
            if not row:
                return {"status": "NOT_FOUND", "operation_zone": None}

            if int(row.get("revision") or 0) != int(expected_revision):
                return {"status": "REVISION_CONFLICT", "operation_zone": row}

            await cur.execute(
                UPDATE_OPERATION_ZONE_SQL,
                (
                    str(zone_name),
                    str(zone_type),
                    bool(is_enabled),
                    str(zone_id),
                    str(map_id),
                ),
            )
            await cur.execute(FIND_OPERATION_ZONE_SQL, (str(zone_id),))
            return {
                "status": "UPDATED",
                "operation_zone": await cur.fetchone(),
            }

    @staticmethod
    def _update_operation_zone_with_cursor(
        cur,
        *,
        map_id,
        zone_id,
        expected_revision,
        zone_name,
        zone_type,
        is_enabled,
    ):
        cur.execute(LOCK_OPERATION_ZONE_SQL, (str(zone_id), str(map_id)))
        row = cur.fetchone()
        if not row:
            return {"status": "NOT_FOUND", "operation_zone": None}

        if int(row.get("revision") or 0) != int(expected_revision):
            return {"status": "REVISION_CONFLICT", "operation_zone": row}

        cur.execute(
            UPDATE_OPERATION_ZONE_SQL,
            (
                str(zone_name),
                str(zone_type),
                bool(is_enabled),
                str(zone_id),
                str(map_id),
            ),
        )
        cur.execute(FIND_OPERATION_ZONE_SQL, (str(zone_id),))
        return {
            "status": "UPDATED",
            "operation_zone": cur.fetchone(),
        }


__all__ = [
    "ACTIVE_MAP_PROFILE_SQL",
    "FIND_OPERATION_ZONE_SQL",
    "INSERT_OPERATION_ZONE_SQL",
    "LIST_GOAL_POSES_SQL",
    "LIST_OPERATION_ZONES_SQL",
    "LIST_PATROL_AREAS_SQL",
    "LOCK_OPERATION_ZONE_SQL",
    "UPDATE_OPERATION_ZONE_SQL",
    "CoordinateConfigRepository",
]
