import json

from server.ropi_main_service.persistence.sql_loader import load_sql


class PatrolTaskRepository:
    def create_patrol_task_records(
        self,
        cur,
        *,
        request_id,
        idempotency_key,
        caregiver_id,
        priority,
        assigned_robot_id,
        patrol_area_id,
        patrol_area_revision,
        patrol_area_name,
        map_id,
        frame_id,
        waypoint_count,
        path_snapshot_json,
        notes=None,
    ):
        task_id = self._insert_patrol_task(
            cur,
            request_id=request_id,
            idempotency_key=idempotency_key,
            caregiver_id=caregiver_id,
            priority=priority,
            assigned_robot_id=assigned_robot_id,
            map_id=map_id,
        )
        self._insert_patrol_detail(
            cur,
            task_id=task_id,
            patrol_area_id=patrol_area_id,
            patrol_area_revision=patrol_area_revision,
            frame_id=frame_id,
            waypoint_count=waypoint_count,
            path_snapshot_json=path_snapshot_json,
            notes=notes,
        )
        self._insert_initial_task_history(cur, task_id=task_id)
        self._insert_initial_task_event(
            cur,
            task_id=task_id,
            patrol_area_name=patrol_area_name,
        )
        return task_id

    async def async_create_patrol_task_records(self, cur, **kwargs):
        task_id = await self._async_insert_patrol_task(
            cur,
            request_id=kwargs["request_id"],
            idempotency_key=kwargs["idempotency_key"],
            caregiver_id=kwargs["caregiver_id"],
            priority=kwargs["priority"],
            assigned_robot_id=kwargs["assigned_robot_id"],
            map_id=kwargs["map_id"],
        )
        await self._async_insert_patrol_detail(
            cur,
            task_id=task_id,
            patrol_area_id=kwargs["patrol_area_id"],
            patrol_area_revision=kwargs["patrol_area_revision"],
            frame_id=kwargs["frame_id"],
            waypoint_count=kwargs["waypoint_count"],
            path_snapshot_json=kwargs["path_snapshot_json"],
            notes=kwargs.get("notes"),
        )
        await self._async_insert_initial_task_history(cur, task_id=task_id)
        await self._async_insert_initial_task_event(
            cur,
            task_id=task_id,
            patrol_area_name=kwargs["patrol_area_name"],
        )
        return task_id

    @staticmethod
    def _insert_patrol_task(
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
            load_sql("patrol/insert_patrol_task.sql"),
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
    async def _async_insert_patrol_task(cur, **kwargs):
        await cur.execute(
            load_sql("patrol/insert_patrol_task.sql"),
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
    def _insert_patrol_detail(
        cur,
        *,
        task_id,
        patrol_area_id,
        patrol_area_revision,
        frame_id,
        waypoint_count,
        path_snapshot_json,
        notes,
    ):
        cur.execute(
            load_sql("patrol/insert_patrol_task_detail.sql"),
            (
                task_id,
                patrol_area_id,
                patrol_area_revision,
                frame_id,
                waypoint_count,
                json.dumps(path_snapshot_json, ensure_ascii=False),
                notes,
            ),
        )

    @staticmethod
    async def _async_insert_patrol_detail(cur, **kwargs):
        await cur.execute(
            load_sql("patrol/insert_patrol_task_detail.sql"),
            (
                kwargs["task_id"],
                kwargs["patrol_area_id"],
                kwargs["patrol_area_revision"],
                kwargs["frame_id"],
                kwargs["waypoint_count"],
                json.dumps(kwargs["path_snapshot_json"], ensure_ascii=False),
                kwargs.get("notes"),
            ),
        )

    @staticmethod
    def _insert_initial_task_history(cur, *, task_id):
        cur.execute(
            load_sql("patrol/insert_initial_task_history.sql"),
            (task_id, "patrol task accepted", "control_service"),
        )

    @staticmethod
    async def _async_insert_initial_task_history(cur, *, task_id):
        await cur.execute(
            load_sql("patrol/insert_initial_task_history.sql"),
            (task_id, "patrol task accepted", "control_service"),
        )

    @staticmethod
    def _insert_initial_task_event(cur, *, task_id, patrol_area_name):
        cur.execute(
            load_sql("patrol/insert_initial_task_event.sql"),
            (task_id, f"patrol task accepted: {patrol_area_name}"),
        )

    @staticmethod
    async def _async_insert_initial_task_event(cur, *, task_id, patrol_area_name):
        await cur.execute(
            load_sql("patrol/insert_initial_task_event.sql"),
            (task_id, f"patrol task accepted: {patrol_area_name}"),
        )


__all__ = ["PatrolTaskRepository"]
