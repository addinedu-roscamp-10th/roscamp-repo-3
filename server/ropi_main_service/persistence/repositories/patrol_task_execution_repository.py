import json

from server.ropi_main_service.persistence.async_connection import async_transaction
from server.ropi_main_service.persistence.sql_loader import load_sql


class PatrolTaskExecutionRepository:
    async def async_get_patrol_execution_snapshot(self, task_id):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return None

        async with async_transaction() as cur:
            await cur.execute(
                load_sql("patrol/get_patrol_execution_snapshot.sql"),
                (numeric_task_id,),
            )
            row = await cur.fetchone()

        if not row:
            return None

        snapshot = dict(row)
        snapshot["path_snapshot_json"] = self._parse_path_snapshot(
            snapshot.get("path_snapshot_json")
        )
        return snapshot

    @staticmethod
    def _parse_task_id(value):
        raw = str(value or "").strip()
        if not raw.isdigit():
            return None
        return int(raw)

    @staticmethod
    def _parse_path_snapshot(value):
        if isinstance(value, str):
            return json.loads(value)
        return value


__all__ = ["PatrolTaskExecutionRepository"]
