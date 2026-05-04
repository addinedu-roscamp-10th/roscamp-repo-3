import json

from server.ropi_main_service.application.patrol_states import (
    PATROL_STATUS_MOVING,
    PHASE_FOLLOW_PATROL_PATH,
    TASK_STATUS_CANCELLED,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_RUNNING,
)
from server.ropi_main_service.persistence.async_connection import async_transaction
from server.ropi_main_service.persistence.sql_loader import load_sql


CONTROL_SERVICE_COMPONENT = "control_service"
PATROL_EXECUTION_START_MESSAGE = "순찰 경로 실행을 시작했습니다."
TERMINAL_PATROL_TASK_STATUSES = {
    TASK_STATUS_CANCELLED,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
}


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

    async def async_record_patrol_execution_started(self, task_id):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._build_patrol_execution_started_response(
                result_code="REJECTED",
                result_message="task_id를 확인할 수 없습니다.",
                reason_code="TASK_ID_INVALID",
                task_id=None,
                task_status=None,
                phase=None,
                assigned_robot_id=None,
                cancellable=False,
            )

        async with async_transaction() as cur:
            await cur.execute(
                load_sql("patrol/lock_patrol_task_for_start.sql"),
                (numeric_task_id,),
            )
            row = await cur.fetchone()

            guard_response = self._build_start_guard(row, task_id=numeric_task_id)
            if guard_response is not None:
                return guard_response

            await cur.execute(
                load_sql("patrol/update_patrol_task_started.sql"),
                (
                    "ACCEPTED",
                    PATROL_EXECUTION_START_MESSAGE,
                    row["task_id"],
                ),
            )
            await cur.execute(
                load_sql("patrol/update_patrol_task_detail_started.sql"),
                (
                    PATROL_STATUS_MOVING,
                    0,
                    row["task_id"],
                ),
            )
            await cur.execute(
                load_sql("patrol/insert_task_result_history.sql"),
                (
                    row["task_id"],
                    row.get("task_status"),
                    TASK_STATUS_RUNNING,
                    row.get("phase"),
                    PHASE_FOLLOW_PATROL_PATH,
                    None,
                    PATROL_EXECUTION_START_MESSAGE,
                    CONTROL_SERVICE_COMPONENT,
                ),
            )
            await cur.execute(
                load_sql("patrol/insert_task_result_event.sql"),
                (
                    row["task_id"],
                    "PATROL_TASK_STARTED",
                    "INFO",
                    row.get("assigned_robot_id"),
                    "ACCEPTED",
                    None,
                    PATROL_EXECUTION_START_MESSAGE,
                    json.dumps(
                        {
                            "task_id": row["task_id"],
                            "assigned_robot_id": row.get("assigned_robot_id"),
                            "patrol_status": PATROL_STATUS_MOVING,
                        },
                        ensure_ascii=False,
                    ),
                ),
            )

        return self._build_patrol_execution_started_response(
            result_code="ACCEPTED",
            result_message=PATROL_EXECUTION_START_MESSAGE,
            reason_code=None,
            task_id=row.get("task_id"),
            task_status=TASK_STATUS_RUNNING,
            phase=PHASE_FOLLOW_PATROL_PATH,
            assigned_robot_id=row.get("assigned_robot_id"),
            cancellable=True,
        )

    def _build_start_guard(self, row, *, task_id):
        if not row:
            return self._build_patrol_execution_started_response(
                result_code="NOT_FOUND",
                result_message="순찰 task 실행 정보를 찾을 수 없습니다.",
                reason_code="PATROL_TASK_NOT_FOUND",
                task_id=task_id,
                task_status=None,
                phase=None,
                assigned_robot_id=None,
                cancellable=False,
            )

        task_status = str(row.get("task_status") or "").strip().upper()
        if task_status in TERMINAL_PATROL_TASK_STATUSES:
            return self._build_patrol_execution_started_response(
                result_code="NOT_ALLOWED",
                result_message="이미 종료된 순찰 task는 실행 시작 상태로 전환할 수 없습니다.",
                reason_code="PATROL_TASK_ALREADY_TERMINAL",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                phase=row.get("phase"),
                assigned_robot_id=row.get("assigned_robot_id"),
                cancellable=False,
            )

        return None

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

    @staticmethod
    def _build_patrol_execution_started_response(
        *,
        result_code,
        result_message,
        reason_code,
        task_id,
        task_status,
        phase,
        assigned_robot_id,
        cancellable,
    ):
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "task_id": task_id,
            "task_status": task_status,
            "phase": phase,
            "assigned_robot_id": assigned_robot_id,
            "cancellable": cancellable,
        }


__all__ = ["PatrolTaskExecutionRepository"]
