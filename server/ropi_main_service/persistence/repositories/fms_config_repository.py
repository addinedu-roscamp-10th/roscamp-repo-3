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
FIND_EDGE_SQL = load_sql("fms_config/find_edge.sql")
FIND_WAYPOINT_SQL = load_sql("fms_config/find_waypoint.sql")
INSERT_EDGE_SQL = load_sql("fms_config/insert_edge.sql")
INSERT_WAYPOINT_SQL = load_sql("fms_config/insert_waypoint.sql")
LIST_EDGES_SQL = load_sql("fms_config/list_edges.sql")
LIST_WAYPOINTS_SQL = load_sql("fms_config/list_waypoints.sql")
LOCK_EDGE_SQL = load_sql("fms_config/lock_edge.sql")
LOCK_WAYPOINT_SQL = load_sql("fms_config/lock_waypoint.sql")
UPDATE_EDGE_SQL = load_sql("fms_config/update_edge.sql")
UPDATE_WAYPOINT_SQL = load_sql("fms_config/update_waypoint.sql")


class FmsConfigRepository:
    def get_active_map_profile(self):
        return fetch_one(ACTIVE_MAP_PROFILE_SQL)

    async def async_get_active_map_profile(self):
        return await async_fetch_one(ACTIVE_MAP_PROFILE_SQL)

    def get_waypoints(self, *, map_id, include_disabled=True):
        return fetch_all(
            LIST_WAYPOINTS_SQL,
            (str(map_id), bool(include_disabled)),
        )

    async def async_get_waypoints(self, *, map_id, include_disabled=True):
        return await async_fetch_all(
            LIST_WAYPOINTS_SQL,
            (str(map_id), bool(include_disabled)),
        )

    def get_edges(self, *, map_id, include_disabled=True):
        return fetch_all(
            LIST_EDGES_SQL,
            (str(map_id), bool(include_disabled)),
        )

    async def async_get_edges(self, *, map_id, include_disabled=True):
        return await async_fetch_all(
            LIST_EDGES_SQL,
            (str(map_id), bool(include_disabled)),
        )

    def upsert_waypoint(
        self,
        *,
        map_id,
        waypoint_id,
        expected_updated_at,
        display_name,
        waypoint_type,
        pose_x,
        pose_y,
        pose_yaw,
        frame_id,
        snap_group,
        is_enabled,
    ):
        conn = get_connection()
        try:
            conn.begin()
            with conn.cursor() as cur:
                result = self._upsert_waypoint_with_cursor(
                    cur,
                    map_id=map_id,
                    waypoint_id=waypoint_id,
                    expected_updated_at=expected_updated_at,
                    display_name=display_name,
                    waypoint_type=waypoint_type,
                    pose_x=pose_x,
                    pose_y=pose_y,
                    pose_yaw=pose_yaw,
                    frame_id=frame_id,
                    snap_group=snap_group,
                    is_enabled=is_enabled,
                )
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def upsert_edge(
        self,
        *,
        map_id,
        edge_id,
        expected_updated_at,
        from_waypoint_id,
        to_waypoint_id,
        is_bidirectional,
        traversal_cost,
        priority,
        is_enabled,
    ):
        conn = get_connection()
        try:
            conn.begin()
            with conn.cursor() as cur:
                result = self._upsert_edge_with_cursor(
                    cur,
                    map_id=map_id,
                    edge_id=edge_id,
                    expected_updated_at=expected_updated_at,
                    from_waypoint_id=from_waypoint_id,
                    to_waypoint_id=to_waypoint_id,
                    is_bidirectional=is_bidirectional,
                    traversal_cost=traversal_cost,
                    priority=priority,
                    is_enabled=is_enabled,
                )
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def async_upsert_waypoint(
        self,
        *,
        map_id,
        waypoint_id,
        expected_updated_at,
        display_name,
        waypoint_type,
        pose_x,
        pose_y,
        pose_yaw,
        frame_id,
        snap_group,
        is_enabled,
    ):
        async with async_transaction() as cur:
            await cur.execute(LOCK_WAYPOINT_SQL, (str(waypoint_id),))
            row = await cur.fetchone()
            status = self._locked_row_status(
                row,
                map_id=map_id,
                expected_updated_at=expected_updated_at,
            )
            if status:
                return status

            if row:
                await cur.execute(
                    UPDATE_WAYPOINT_SQL,
                    self._build_update_waypoint_params(
                        map_id=map_id,
                        waypoint_id=waypoint_id,
                        display_name=display_name,
                        waypoint_type=waypoint_type,
                        pose_x=pose_x,
                        pose_y=pose_y,
                        pose_yaw=pose_yaw,
                        frame_id=frame_id,
                        snap_group=snap_group,
                        is_enabled=is_enabled,
                    ),
                )
            else:
                await cur.execute(
                    INSERT_WAYPOINT_SQL,
                    self._build_insert_waypoint_params(
                        map_id=map_id,
                        waypoint_id=waypoint_id,
                        display_name=display_name,
                        waypoint_type=waypoint_type,
                        pose_x=pose_x,
                        pose_y=pose_y,
                        pose_yaw=pose_yaw,
                        frame_id=frame_id,
                        snap_group=snap_group,
                        is_enabled=is_enabled,
                    ),
                )

            await cur.execute(FIND_WAYPOINT_SQL, (str(waypoint_id),))
            return {
                "status": "UPSERTED",
                "waypoint": await cur.fetchone(),
            }

    async def async_upsert_edge(
        self,
        *,
        map_id,
        edge_id,
        expected_updated_at,
        from_waypoint_id,
        to_waypoint_id,
        is_bidirectional,
        traversal_cost,
        priority,
        is_enabled,
    ):
        async with async_transaction() as cur:
            await cur.execute(LOCK_EDGE_SQL, (str(edge_id),))
            row = await cur.fetchone()
            status = self._locked_edge_row_status(
                row,
                map_id=map_id,
                expected_updated_at=expected_updated_at,
            )
            if status:
                return status

            if row:
                await cur.execute(
                    UPDATE_EDGE_SQL,
                    self._build_update_edge_params(
                        map_id=map_id,
                        edge_id=edge_id,
                        from_waypoint_id=from_waypoint_id,
                        to_waypoint_id=to_waypoint_id,
                        is_bidirectional=is_bidirectional,
                        traversal_cost=traversal_cost,
                        priority=priority,
                        is_enabled=is_enabled,
                    ),
                )
            else:
                await cur.execute(
                    INSERT_EDGE_SQL,
                    self._build_insert_edge_params(
                        map_id=map_id,
                        edge_id=edge_id,
                        from_waypoint_id=from_waypoint_id,
                        to_waypoint_id=to_waypoint_id,
                        is_bidirectional=is_bidirectional,
                        traversal_cost=traversal_cost,
                        priority=priority,
                        is_enabled=is_enabled,
                    ),
                )

            await cur.execute(FIND_EDGE_SQL, (str(edge_id),))
            return {
                "status": "UPSERTED",
                "edge": await cur.fetchone(),
            }

    @classmethod
    def _upsert_waypoint_with_cursor(
        cls,
        cur,
        *,
        map_id,
        waypoint_id,
        expected_updated_at,
        display_name,
        waypoint_type,
        pose_x,
        pose_y,
        pose_yaw,
        frame_id,
        snap_group,
        is_enabled,
    ):
        cur.execute(LOCK_WAYPOINT_SQL, (str(waypoint_id),))
        row = cur.fetchone()
        status = cls._locked_row_status(
            row,
            map_id=map_id,
            expected_updated_at=expected_updated_at,
        )
        if status:
            return status

        if row:
            cur.execute(
                UPDATE_WAYPOINT_SQL,
                cls._build_update_waypoint_params(
                    map_id=map_id,
                    waypoint_id=waypoint_id,
                    display_name=display_name,
                    waypoint_type=waypoint_type,
                    pose_x=pose_x,
                    pose_y=pose_y,
                    pose_yaw=pose_yaw,
                    frame_id=frame_id,
                    snap_group=snap_group,
                    is_enabled=is_enabled,
                ),
            )
        else:
            cur.execute(
                INSERT_WAYPOINT_SQL,
                cls._build_insert_waypoint_params(
                    map_id=map_id,
                    waypoint_id=waypoint_id,
                    display_name=display_name,
                    waypoint_type=waypoint_type,
                    pose_x=pose_x,
                    pose_y=pose_y,
                    pose_yaw=pose_yaw,
                    frame_id=frame_id,
                    snap_group=snap_group,
                    is_enabled=is_enabled,
                ),
            )

        cur.execute(FIND_WAYPOINT_SQL, (str(waypoint_id),))
        return {
            "status": "UPSERTED",
            "waypoint": cur.fetchone(),
        }

    @classmethod
    def _upsert_edge_with_cursor(
        cls,
        cur,
        *,
        map_id,
        edge_id,
        expected_updated_at,
        from_waypoint_id,
        to_waypoint_id,
        is_bidirectional,
        traversal_cost,
        priority,
        is_enabled,
    ):
        cur.execute(LOCK_EDGE_SQL, (str(edge_id),))
        row = cur.fetchone()
        status = cls._locked_edge_row_status(
            row,
            map_id=map_id,
            expected_updated_at=expected_updated_at,
        )
        if status:
            return status

        if row:
            cur.execute(
                UPDATE_EDGE_SQL,
                cls._build_update_edge_params(
                    map_id=map_id,
                    edge_id=edge_id,
                    from_waypoint_id=from_waypoint_id,
                    to_waypoint_id=to_waypoint_id,
                    is_bidirectional=is_bidirectional,
                    traversal_cost=traversal_cost,
                    priority=priority,
                    is_enabled=is_enabled,
                ),
            )
        else:
            cur.execute(
                INSERT_EDGE_SQL,
                cls._build_insert_edge_params(
                    map_id=map_id,
                    edge_id=edge_id,
                    from_waypoint_id=from_waypoint_id,
                    to_waypoint_id=to_waypoint_id,
                    is_bidirectional=is_bidirectional,
                    traversal_cost=traversal_cost,
                    priority=priority,
                    is_enabled=is_enabled,
                ),
            )

        cur.execute(FIND_EDGE_SQL, (str(edge_id),))
        return {
            "status": "UPSERTED",
            "edge": cur.fetchone(),
        }

    @classmethod
    def _locked_row_status(cls, row, *, map_id, expected_updated_at):
        if not row:
            if cls._normalize_timestamp(expected_updated_at) is not None:
                return {"status": "NOT_FOUND", "waypoint": None}
            return None

        if str(row.get("map_id")) != str(map_id):
            return {"status": "MAP_MISMATCH", "waypoint": row}

        if not cls._timestamp_matches(row.get("updated_at"), expected_updated_at):
            return {"status": "STALE", "waypoint": row}

        return None

    @classmethod
    def _locked_edge_row_status(cls, row, *, map_id, expected_updated_at):
        if not row:
            if cls._normalize_timestamp(expected_updated_at) is not None:
                return {"status": "NOT_FOUND", "edge": None}
            return None

        if str(row.get("map_id")) != str(map_id):
            return {"status": "MAP_MISMATCH", "edge": row}

        if not cls._timestamp_matches(row.get("updated_at"), expected_updated_at):
            return {"status": "STALE", "edge": row}

        return None

    @staticmethod
    def _build_insert_waypoint_params(
        *,
        map_id,
        waypoint_id,
        display_name,
        waypoint_type,
        pose_x,
        pose_y,
        pose_yaw,
        frame_id,
        snap_group,
        is_enabled,
    ):
        return (
            str(waypoint_id),
            str(map_id),
            str(display_name),
            str(waypoint_type),
            pose_x,
            pose_y,
            pose_yaw,
            str(frame_id),
            snap_group,
            bool(is_enabled),
        )

    @staticmethod
    def _build_update_waypoint_params(
        *,
        map_id,
        waypoint_id,
        display_name,
        waypoint_type,
        pose_x,
        pose_y,
        pose_yaw,
        frame_id,
        snap_group,
        is_enabled,
    ):
        return (
            str(display_name),
            str(waypoint_type),
            pose_x,
            pose_y,
            pose_yaw,
            str(frame_id),
            snap_group,
            bool(is_enabled),
            str(waypoint_id),
            str(map_id),
        )

    @staticmethod
    def _build_insert_edge_params(
        *,
        map_id,
        edge_id,
        from_waypoint_id,
        to_waypoint_id,
        is_bidirectional,
        traversal_cost,
        priority,
        is_enabled,
    ):
        return (
            str(edge_id),
            str(map_id),
            str(from_waypoint_id),
            str(to_waypoint_id),
            bool(is_bidirectional),
            traversal_cost,
            priority,
            bool(is_enabled),
        )

    @staticmethod
    def _build_update_edge_params(
        *,
        map_id,
        edge_id,
        from_waypoint_id,
        to_waypoint_id,
        is_bidirectional,
        traversal_cost,
        priority,
        is_enabled,
    ):
        return (
            str(from_waypoint_id),
            str(to_waypoint_id),
            bool(is_bidirectional),
            traversal_cost,
            priority,
            bool(is_enabled),
            str(edge_id),
            str(map_id),
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


__all__ = ["FmsConfigRepository"]
