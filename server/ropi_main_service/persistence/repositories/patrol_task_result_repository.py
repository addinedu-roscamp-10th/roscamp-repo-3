import json

from server.ropi_main_service.application.patrol_states import (
    TASK_STATUS_ASSIGNED,
    TASK_STATUS_CANCEL_REQUESTED,
    TASK_STATUS_CANCELLED,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_READY,
    TASK_STATUS_RUNNING,
    TASK_STATUS_WAITING,
    TASK_STATUS_WAITING_DISPATCH,
)
from server.ropi_main_service.persistence.async_connection import async_transaction
from server.ropi_main_service.persistence.sql_loader import load_sql


CONTROL_SERVICE_COMPONENT = "control_service"
PATROL_WORKFLOW_FAILED_REASON = "PATROL_WORKFLOW_FAILED"
PATROL_WORKFLOW_CANCELLED_REASON = "PATROL_WORKFLOW_CANCELLED"
TERMINAL_PATROL_TASK_STATUSES = {
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_CANCELLED,
}
RESULT_FINALIZABLE_PATROL_TASK_STATUSES = {
    TASK_STATUS_WAITING,
    TASK_STATUS_WAITING_DISPATCH,
    TASK_STATUS_READY,
    TASK_STATUS_ASSIGNED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_CANCEL_REQUESTED,
}


class PatrolTaskResultRepository:
    async def async_record_patrol_task_workflow_result(self, *, task_id, workflow_response):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._build_patrol_task_result_response(
                result_code="REJECTED",
                result_message="task_id를 확인할 수 없습니다.",
                reason_code="TASK_ID_INVALID",
                task_id=None,
                task_status=None,
                assigned_robot_id=None,
                workflow_response=workflow_response,
            )

        async with async_transaction() as cur:
            await cur.execute(
                load_sql("patrol/lock_patrol_task_for_result.sql"),
                (numeric_task_id,),
            )
            row = await cur.fetchone()
            return await self._async_record_patrol_task_workflow_result(
                cur,
                row=row,
                task_id=numeric_task_id,
                workflow_response=workflow_response,
            )

    @staticmethod
    def _parse_task_id(value):
        raw = str(value or "").strip()
        if not raw.isdigit():
            return None
        return int(raw)

    async def _async_record_patrol_task_workflow_result(self, cur, *, row, task_id, workflow_response):
        guard_response = self._build_result_guard(
            row,
            task_id=task_id,
            workflow_response=workflow_response,
        )
        if guard_response is not None:
            return guard_response

        return await self._async_write_workflow_result(
            cur,
            row=row,
            workflow_response=workflow_response,
        )

    def _build_result_guard(self, row, *, task_id, workflow_response):
        if not row:
            return self._build_patrol_task_result_response(
                result_code="REJECTED",
                result_message="순찰 task를 찾을 수 없습니다.",
                reason_code="TASK_NOT_FOUND",
                task_id=task_id,
                task_status=None,
                assigned_robot_id=None,
                workflow_response=workflow_response,
            )

        task_status = str(row.get("task_status") or "").strip()
        if task_status in TERMINAL_PATROL_TASK_STATUSES:
            return self._build_patrol_task_result_response(
                result_code="IGNORED",
                result_message="이미 종료된 순찰 task입니다.",
                reason_code="TASK_ALREADY_TERMINAL",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                assigned_robot_id=row.get("assigned_robot_id"),
                workflow_response=workflow_response,
            )

        if task_status not in RESULT_FINALIZABLE_PATROL_TASK_STATUSES:
            return self._build_patrol_task_result_response(
                result_code="IGNORED",
                result_message="완료 결과를 반영할 수 없는 순찰 task 상태입니다.",
                reason_code="TASK_NOT_FINALIZABLE",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                assigned_robot_id=row.get("assigned_robot_id"),
                workflow_response=workflow_response,
            )

        return None

    async def _async_write_workflow_result(self, cur, *, row, workflow_response):
        plan = self._build_workflow_result_write_plan(
            row=row,
            workflow_response=workflow_response,
        )
        await cur.execute(
            load_sql("patrol/update_task_workflow_result.sql"),
            plan["update_task_params"],
        )
        await cur.execute(
            load_sql("patrol/update_patrol_task_detail_result.sql"),
            plan["update_detail_params"],
        )
        await cur.execute(
            load_sql("patrol/insert_task_result_history.sql"),
            plan["history_params"],
        )
        await cur.execute(
            load_sql("patrol/insert_task_result_event.sql"),
            plan["event_params"],
        )
        return self._build_patrol_task_result_response(
            result_code=plan["result_code"],
            result_message=plan["result_message"],
            reason_code=plan["reason_code"],
            task_id=row.get("task_id"),
            task_status=plan["task_status"],
            assigned_robot_id=row.get("assigned_robot_id"),
            workflow_response=workflow_response,
        )

    def _build_workflow_result_write_plan(self, *, row, workflow_response):
        normalized = self._normalize_workflow_result(workflow_response)
        current_waypoint_index = self._current_waypoint_index_for_result(
            row=row,
            workflow_response=workflow_response,
        )
        return {
            **normalized,
            "update_task_params": (
                normalized["task_status"],
                normalized["phase"],
                normalized["reason_code"],
                normalized["result_code"],
                normalized["result_message"],
                row["task_id"],
            ),
            "update_detail_params": (
                normalized["patrol_status"],
                current_waypoint_index,
                row["task_id"],
            ),
            "history_params": (
                row["task_id"],
                row.get("task_status"),
                normalized["task_status"],
                row.get("phase"),
                normalized["phase"],
                normalized["reason_code"],
                normalized["result_message"],
                CONTROL_SERVICE_COMPONENT,
            ),
            "event_params": (
                row["task_id"],
                normalized["event_name"],
                normalized["severity"],
                row.get("assigned_robot_id"),
                normalized["result_code"],
                normalized["reason_code"],
                normalized["result_message"],
                json.dumps(workflow_response or {}, ensure_ascii=False),
            ),
        }

    @staticmethod
    def _normalize_workflow_result(workflow_response):
        workflow_response = workflow_response if isinstance(workflow_response, dict) else {}
        result_code = str(workflow_response.get("result_code") or "FAILED").strip().upper() or "FAILED"
        result_message = workflow_response.get("result_message")
        reason_code = workflow_response.get("reason_code")

        if result_code in {"SUCCEEDED", "SUCCESS"}:
            return {
                "task_status": TASK_STATUS_COMPLETED,
                "phase": TASK_STATUS_COMPLETED,
                "patrol_status": TASK_STATUS_COMPLETED,
                "event_name": "PATROL_TASK_COMPLETED",
                "severity": "INFO",
                "result_code": "SUCCEEDED",
                "reason_code": reason_code,
                "result_message": result_message or "순찰 task가 완료되었습니다.",
            }

        if result_code in {"CANCELED", "CANCELLED"}:
            return {
                "task_status": TASK_STATUS_CANCELLED,
                "phase": TASK_STATUS_CANCELLED,
                "patrol_status": TASK_STATUS_CANCELLED,
                "event_name": "PATROL_TASK_CANCELLED",
                "severity": "WARNING",
                "result_code": result_code,
                "reason_code": reason_code or PATROL_WORKFLOW_CANCELLED_REASON,
                "result_message": result_message or "순찰 task가 취소되었습니다.",
            }

        return {
            "task_status": TASK_STATUS_FAILED,
            "phase": TASK_STATUS_FAILED,
            "patrol_status": TASK_STATUS_FAILED,
            "event_name": "PATROL_TASK_FAILED",
            "severity": "ERROR",
            "result_code": result_code,
            "reason_code": reason_code or PATROL_WORKFLOW_FAILED_REASON,
            "result_message": result_message or "순찰 task가 실패했습니다.",
        }

    @classmethod
    def _current_waypoint_index_for_result(cls, *, row, workflow_response):
        workflow_response = workflow_response if isinstance(workflow_response, dict) else {}
        completed_count = cls._optional_int(workflow_response.get("completed_waypoint_count"))
        if completed_count is None:
            return row.get("current_waypoint_index")

        index = max(completed_count - 1, 0)
        waypoint_count = cls._optional_int(row.get("waypoint_count"))
        if waypoint_count is not None and waypoint_count > 0:
            index = min(index, waypoint_count - 1)
        return index

    @staticmethod
    def _optional_int(value):
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _build_patrol_task_result_response(
        *,
        result_code,
        result_message=None,
        reason_code=None,
        task_id=None,
        task_status=None,
        assigned_robot_id=None,
        workflow_response=None,
    ):
        response = {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "task_id": task_id,
            "task_status": task_status,
            "assigned_robot_id": assigned_robot_id,
        }
        if workflow_response is not None:
            response["workflow_result"] = workflow_response
        return response


__all__ = ["PatrolTaskResultRepository"]
