import json

from server.ropi_main_service.persistence.sql_loader import load_sql


class DriveTaskRepository:
    def create_drive_task_records(
        self,
        cur,
        *,
        request_id,
        idempotency_key,
        caregiver_id,
        priority,
        assigned_robot_id,
        route_id,
        route_revision,
        route_name,
        map_id,
        frame_id,
        waypoint_count,
        path_snapshot_json,
        notes=None,
    ):
        task_id = self._insert_drive_task(
            cur,
            request_id=request_id,
            idempotency_key=idempotency_key,
            caregiver_id=caregiver_id,
            priority=priority,
            assigned_robot_id=assigned_robot_id,
            map_id=map_id,
        )
        self._insert_drive_detail(
            cur,
            task_id=task_id,
            route_id=route_id,
            route_revision=route_revision,
            frame_id=frame_id,
            waypoint_count=waypoint_count,
            path_snapshot_json=path_snapshot_json,
            notes=notes,
        )
        self._insert_initial_task_history(cur, task_id=task_id)
        self._insert_initial_task_event(
            cur,
            task_id=task_id,
            route_name=route_name,
        )
        return task_id

    async def async_create_drive_task_records(self, cur, **kwargs):
        task_id = await self._async_insert_drive_task(
            cur,
            request_id=kwargs["request_id"],
            idempotency_key=kwargs["idempotency_key"],
            caregiver_id=kwargs["caregiver_id"],
            priority=kwargs["priority"],
            assigned_robot_id=kwargs["assigned_robot_id"],
            map_id=kwargs["map_id"],
        )
        await self._async_insert_drive_detail(
            cur,
            task_id=task_id,
            route_id=kwargs["route_id"],
            route_revision=kwargs["route_revision"],
            frame_id=kwargs["frame_id"],
            waypoint_count=kwargs["waypoint_count"],
            path_snapshot_json=kwargs["path_snapshot_json"],
            notes=kwargs.get("notes"),
        )
        await self._async_insert_initial_task_history(cur, task_id=task_id)
        await self._async_insert_initial_task_event(
            cur,
            task_id=task_id,
            route_name=kwargs["route_name"],
        )
        return task_id

    @staticmethod
    def _insert_drive_task(
        cur,
        *,
        request_id,
        idempotency_key,
        caregiver_id,
        priority,
        assigned_robot_id,
        map_id,
    ):
        cur.execute(
            load_sql("drive/insert_drive_task.sql"),
            (
                request_id,
                idempotency_key,
                str(caregiver_id),
                priority or "NORMAL",
                assigned_robot_id,
                map_id,
            ),
        )
        return cur.lastrowid

    @staticmethod
    async def _async_insert_drive_task(cur, **kwargs):
        await cur.execute(
            load_sql("drive/insert_drive_task.sql"),
            (
                kwargs["request_id"],
                kwargs["idempotency_key"],
                str(kwargs["caregiver_id"]),
                kwargs["priority"] or "NORMAL",
                kwargs["assigned_robot_id"],
                kwargs["map_id"],
            ),
        )
        return cur.lastrowid

    @staticmethod
    def _insert_drive_detail(
        cur,
        *,
        task_id,
        route_id,
        route_revision,
        frame_id,
        waypoint_count,
        path_snapshot_json,
        notes,
    ):
        cur.execute(
            load_sql("drive/insert_drive_task_detail.sql"),
            (
                task_id,
                route_id,
                route_revision,
                frame_id,
                waypoint_count,
                json.dumps(path_snapshot_json, ensure_ascii=False),
                notes,
            ),
        )

    @staticmethod
    async def _async_insert_drive_detail(cur, **kwargs):
        await cur.execute(
            load_sql("drive/insert_drive_task_detail.sql"),
            (
                kwargs["task_id"],
                kwargs["route_id"],
                kwargs["route_revision"],
                kwargs["frame_id"],
                kwargs["waypoint_count"],
                json.dumps(kwargs["path_snapshot_json"], ensure_ascii=False),
                kwargs.get("notes"),
            ),
        )

    @staticmethod
    def _insert_initial_task_history(cur, *, task_id):
        cur.execute(
            load_sql("drive/insert_initial_task_history.sql"),
            (task_id, "drive task accepted", "control_service"),
        )

    @staticmethod
    async def _async_insert_initial_task_history(cur, *, task_id):
        await cur.execute(
            load_sql("drive/insert_initial_task_history.sql"),
            (task_id, "drive task accepted", "control_service"),
        )

    @staticmethod
    def _insert_initial_task_event(cur, *, task_id, route_name):
        cur.execute(
            load_sql("drive/insert_initial_task_event.sql"),
            (task_id, f"drive task accepted: {route_name}"),
        )

    @staticmethod
    async def _async_insert_initial_task_event(cur, *, task_id, route_name):
        await cur.execute(
            load_sql("drive/insert_initial_task_event.sql"),
            (task_id, f"drive task accepted: {route_name}"),
        )


__all__ = ["DriveTaskRepository"]
