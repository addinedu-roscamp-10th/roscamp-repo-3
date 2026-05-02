import json

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
FIND_GOAL_POSE_SQL = load_sql("coordinate_config/find_goal_pose.sql")
FIND_MAP_PROFILE_SQL = load_sql("coordinate_config/find_map_profile.sql")
FIND_OPERATION_ZONE_SQL = load_sql("coordinate_config/find_operation_zone.sql")
FIND_PATROL_AREA_SQL = load_sql("coordinate_config/find_patrol_area.sql")
INSERT_OPERATION_ZONE_SQL = load_sql("coordinate_config/insert_operation_zone.sql")
LIST_OPERATION_ZONES_SQL = load_sql("coordinate_config/list_operation_zones.sql")
LIST_GOAL_POSES_SQL = load_sql("coordinate_config/list_goal_poses.sql")
LIST_PATROL_AREAS_SQL = load_sql("coordinate_config/list_patrol_areas.sql")
LOCK_GOAL_POSE_SQL = load_sql("coordinate_config/lock_goal_pose.sql")
LOCK_OPERATION_ZONE_SQL = load_sql("coordinate_config/lock_operation_zone.sql")
LOCK_PATROL_AREA_SQL = load_sql("coordinate_config/lock_patrol_area.sql")
UPDATE_GOAL_POSE_SQL = load_sql("coordinate_config/update_goal_pose.sql")
UPDATE_OPERATION_ZONE_SQL = load_sql("coordinate_config/update_operation_zone.sql")
UPDATE_PATROL_AREA_PATH_SQL = load_sql(
    "coordinate_config/update_patrol_area_path.sql"
)


class CoordinateConfigRepository:
    def get_active_map_profile(self):
        return fetch_one(ACTIVE_MAP_PROFILE_SQL)

    async def async_get_active_map_profile(self):
        return await async_fetch_one(ACTIVE_MAP_PROFILE_SQL)

    def get_map_profile(self, *, map_id):
        return fetch_one(FIND_MAP_PROFILE_SQL, (str(map_id),))

    async def async_get_map_profile(self, *, map_id):
        return await async_fetch_one(FIND_MAP_PROFILE_SQL, (str(map_id),))

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

    def update_goal_pose(
        self,
        *,
        map_id,
        goal_pose_id,
        expected_updated_at,
        zone_id,
        purpose,
        pose_x,
        pose_y,
        pose_yaw,
        frame_id,
        is_enabled,
    ):
        conn = get_connection()
        try:
            conn.begin()
            with conn.cursor() as cur:
                result = self._update_goal_pose_with_cursor(
                    cur,
                    map_id=map_id,
                    goal_pose_id=goal_pose_id,
                    expected_updated_at=expected_updated_at,
                    zone_id=zone_id,
                    purpose=purpose,
                    pose_x=pose_x,
                    pose_y=pose_y,
                    pose_yaw=pose_yaw,
                    frame_id=frame_id,
                    is_enabled=is_enabled,
                )
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def async_update_goal_pose(
        self,
        *,
        map_id,
        goal_pose_id,
        expected_updated_at,
        zone_id,
        purpose,
        pose_x,
        pose_y,
        pose_yaw,
        frame_id,
        is_enabled,
    ):
        async with async_transaction() as cur:
            await cur.execute(
                LOCK_GOAL_POSE_SQL,
                (str(goal_pose_id), str(map_id)),
            )
            row = await cur.fetchone()
            if not row:
                return {"status": "NOT_FOUND", "goal_pose": None}

            if not self._timestamp_matches(
                row.get("updated_at"),
                expected_updated_at,
            ):
                return {"status": "STALE", "goal_pose": row}

            await cur.execute(
                UPDATE_GOAL_POSE_SQL,
                self._build_update_goal_pose_params(
                    map_id=map_id,
                    goal_pose_id=goal_pose_id,
                    zone_id=zone_id,
                    purpose=purpose,
                    pose_x=pose_x,
                    pose_y=pose_y,
                    pose_yaw=pose_yaw,
                    frame_id=frame_id,
                    is_enabled=is_enabled,
                ),
            )
            await cur.execute(FIND_GOAL_POSE_SQL, (str(goal_pose_id),))
            return {
                "status": "UPDATED",
                "goal_pose": await cur.fetchone(),
            }

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

    def update_patrol_area_path(
        self,
        *,
        map_id,
        patrol_area_id,
        expected_revision,
        path_json,
    ):
        conn = get_connection()
        try:
            conn.begin()
            with conn.cursor() as cur:
                result = self._update_patrol_area_path_with_cursor(
                    cur,
                    map_id=map_id,
                    patrol_area_id=patrol_area_id,
                    expected_revision=expected_revision,
                    path_json=path_json,
                )
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def async_update_patrol_area_path(
        self,
        *,
        map_id,
        patrol_area_id,
        expected_revision,
        path_json,
    ):
        async with async_transaction() as cur:
            await cur.execute(
                LOCK_PATROL_AREA_SQL,
                (str(patrol_area_id), str(map_id)),
            )
            row = await cur.fetchone()
            if not row:
                return {"status": "NOT_FOUND", "patrol_area": None}

            if int(row.get("revision") or 0) != int(expected_revision):
                return {"status": "REVISION_CONFLICT", "patrol_area": row}

            await cur.execute(
                UPDATE_PATROL_AREA_PATH_SQL,
                self._build_update_patrol_area_path_params(
                    map_id=map_id,
                    patrol_area_id=patrol_area_id,
                    path_json=path_json,
                ),
            )
            await cur.execute(FIND_PATROL_AREA_SQL, (str(patrol_area_id),))
            return {
                "status": "UPDATED",
                "patrol_area": await cur.fetchone(),
            }

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

    @classmethod
    def _update_goal_pose_with_cursor(
        cls,
        cur,
        *,
        map_id,
        goal_pose_id,
        expected_updated_at,
        zone_id,
        purpose,
        pose_x,
        pose_y,
        pose_yaw,
        frame_id,
        is_enabled,
    ):
        cur.execute(LOCK_GOAL_POSE_SQL, (str(goal_pose_id), str(map_id)))
        row = cur.fetchone()
        if not row:
            return {"status": "NOT_FOUND", "goal_pose": None}

        if not cls._timestamp_matches(row.get("updated_at"), expected_updated_at):
            return {"status": "STALE", "goal_pose": row}

        cur.execute(
            UPDATE_GOAL_POSE_SQL,
            cls._build_update_goal_pose_params(
                map_id=map_id,
                goal_pose_id=goal_pose_id,
                zone_id=zone_id,
                purpose=purpose,
                pose_x=pose_x,
                pose_y=pose_y,
                pose_yaw=pose_yaw,
                frame_id=frame_id,
                is_enabled=is_enabled,
            ),
        )
        cur.execute(FIND_GOAL_POSE_SQL, (str(goal_pose_id),))
        return {
            "status": "UPDATED",
            "goal_pose": cur.fetchone(),
        }

    @classmethod
    def _update_patrol_area_path_with_cursor(
        cls,
        cur,
        *,
        map_id,
        patrol_area_id,
        expected_revision,
        path_json,
    ):
        cur.execute(LOCK_PATROL_AREA_SQL, (str(patrol_area_id), str(map_id)))
        row = cur.fetchone()
        if not row:
            return {"status": "NOT_FOUND", "patrol_area": None}

        if int(row.get("revision") or 0) != int(expected_revision):
            return {"status": "REVISION_CONFLICT", "patrol_area": row}

        cur.execute(
            UPDATE_PATROL_AREA_PATH_SQL,
            cls._build_update_patrol_area_path_params(
                map_id=map_id,
                patrol_area_id=patrol_area_id,
                path_json=path_json,
            ),
        )
        cur.execute(FIND_PATROL_AREA_SQL, (str(patrol_area_id),))
        return {
            "status": "UPDATED",
            "patrol_area": cur.fetchone(),
        }

    @staticmethod
    def _build_update_goal_pose_params(
        *,
        map_id,
        goal_pose_id,
        zone_id,
        purpose,
        pose_x,
        pose_y,
        pose_yaw,
        frame_id,
        is_enabled,
    ):
        return (
            None if zone_id is None else str(zone_id),
            str(purpose),
            float(pose_x),
            float(pose_y),
            float(pose_yaw),
            str(frame_id),
            bool(is_enabled),
            str(goal_pose_id),
            str(map_id),
        )

    @classmethod
    def _build_update_patrol_area_path_params(
        cls,
        *,
        map_id,
        patrol_area_id,
        path_json,
    ):
        return (
            cls._json_dumps(path_json),
            str(patrol_area_id),
            str(map_id),
        )

    @staticmethod
    def _json_dumps(value):
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @classmethod
    def _timestamp_matches(cls, current_value, expected_value):
        expected = cls._normalize_timestamp(expected_value)
        if expected is None:
            return True
        return cls._normalize_timestamp(current_value) == expected

    @staticmethod
    def _normalize_timestamp(value):
        if value in (None, ""):
            return None
        if hasattr(value, "isoformat"):
            text = value.isoformat()
        else:
            text = str(value).strip()
        text = text.replace(" ", "T")
        if "." in text:
            text = text.split(".", 1)[0]
        if text.endswith("Z"):
            text = text[:-1]
        if text.endswith("+00:00"):
            text = text[:-6]
        return text


__all__ = [
    "ACTIVE_MAP_PROFILE_SQL",
    "FIND_GOAL_POSE_SQL",
    "FIND_MAP_PROFILE_SQL",
    "FIND_OPERATION_ZONE_SQL",
    "FIND_PATROL_AREA_SQL",
    "INSERT_OPERATION_ZONE_SQL",
    "LIST_GOAL_POSES_SQL",
    "LIST_OPERATION_ZONES_SQL",
    "LIST_PATROL_AREAS_SQL",
    "LOCK_GOAL_POSE_SQL",
    "LOCK_OPERATION_ZONE_SQL",
    "LOCK_PATROL_AREA_SQL",
    "UPDATE_GOAL_POSE_SQL",
    "UPDATE_OPERATION_ZONE_SQL",
    "UPDATE_PATROL_AREA_PATH_SQL",
    "CoordinateConfigRepository",
]
