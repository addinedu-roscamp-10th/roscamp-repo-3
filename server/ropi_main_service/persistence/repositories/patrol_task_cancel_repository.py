import json

from server.ropi_main_service.persistence.async_connection import (
    async_fetch_one,
    async_transaction,
)
from server.ropi_main_service.persistence.connection import fetch_one, get_connection
from server.ropi_main_service.persistence.sql_loader import load_sql


CONTROL_SERVICE_COMPONENT = "control_service"
TASK_STATUS_CANCEL_REQUESTED = "CANCEL_REQUESTED"
REASON_USER_CANCEL_REQUESTED = "USER_CANCEL_REQUESTED"
CANCELLABLE_PATROL_TASK_STATUSES = {
    "WAITING",
    "WAITING_DISPATCH",
    "READY",
    "ASSIGNED",
    "RUNNING",
}


class PatrolTaskCancelRepository:
    def get_patrol_task_cancel_target(self, task_id):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._build_invalid_task_id_response()

        row = fetch_one(
            load_sql("patrol/find_patrol_task_for_cancel.sql"),
            (numeric_task_id,),
        )
        return self._build_cancel_target_response(row, task_id=numeric_task_id)

    async def async_get_patrol_task_cancel_target(self, task_id):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._build_invalid_task_id_response()

        row = await async_fetch_one(
            load_sql("patrol/find_patrol_task_for_cancel.sql"),
            (numeric_task_id,),
        )
        return self._build_cancel_target_response(row, task_id=numeric_task_id)

    def record_patrol_task_cancel_result(
        self,
        *,
        task_id,
        caregiver_id,
        reason,
        cancel_response,
    ):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._build_invalid_task_id_response()

        conn = get_connection()
        try:
            self._begin(conn)
            with conn.cursor() as cur:
                cur.execute(
                    load_sql("patrol/lock_patrol_task_for_cancel.sql"),
                    (numeric_task_id,),
                )
                row = cur.fetchone()
                response = self._record_patrol_task_cancel_result(
                    cur,
                    row=row,
                    task_id=numeric_task_id,
                    caregiver_id=caregiver_id,
                    reason=reason,
                    cancel_response=cancel_response,
                )
                conn.commit()
                return response
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def async_record_patrol_task_cancel_result(
        self,
        *,
        task_id,
        caregiver_id,
        reason,
        cancel_response,
    ):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._build_invalid_task_id_response()

        async with async_transaction() as cur:
            await cur.execute(
                load_sql("patrol/lock_patrol_task_for_cancel.sql"),
                (numeric_task_id,),
            )
            row = await cur.fetchone()
            return await self._async_record_patrol_task_cancel_result(
                cur,
                row=row,
                task_id=numeric_task_id,
                caregiver_id=caregiver_id,
                reason=reason,
                cancel_response=cancel_response,
            )

    def _record_patrol_task_cancel_result(
        self,
        cur,
        *,
        row,
        task_id,
        caregiver_id,
        reason,
        cancel_response,
    ):
        guard_response = self._build_cancel_result_guard(row, task_id=task_id)
        if guard_response is not None:
            return guard_response

        plan = self._build_cancel_write_plan(
            row=row,
            caregiver_id=caregiver_id,
            reason=reason,
            cancel_response=cancel_response,
        )
        if plan["cancel_requested"]:
            cur.execute(
                load_sql("delivery/update_task_cancel_requested.sql"),
                plan["update_task_params"],
            )
            cur.execute(
                load_sql("patrol/update_patrol_task_detail_cancel_requested.sql"),
                plan["update_detail_params"],
            )
            cur.execute(
                load_sql("patrol/insert_task_result_history.sql"),
                plan["history_params"],
            )

        cur.execute(
            load_sql("patrol/insert_task_result_event.sql"),
            plan["event_params"],
        )
        return self._build_patrol_cancel_response(
            row=row,
            plan=plan,
            cancel_response=cancel_response,
        )

    async def _async_record_patrol_task_cancel_result(
        self,
        cur,
        *,
        row,
        task_id,
        caregiver_id,
        reason,
        cancel_response,
    ):
        guard_response = self._build_cancel_result_guard(row, task_id=task_id)
        if guard_response is not None:
            return guard_response

        plan = self._build_cancel_write_plan(
            row=row,
            caregiver_id=caregiver_id,
            reason=reason,
            cancel_response=cancel_response,
        )
        if plan["cancel_requested"]:
            await cur.execute(
                load_sql("delivery/update_task_cancel_requested.sql"),
                plan["update_task_params"],
            )
            await cur.execute(
                load_sql("patrol/update_patrol_task_detail_cancel_requested.sql"),
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
        return self._build_patrol_cancel_response(
            row=row,
            plan=plan,
            cancel_response=cancel_response,
        )

    def _build_cancel_result_guard(self, row, *, task_id):
        if not row:
            return self._build_response(
                result_code="REJECTED",
                result_message="순찰 task를 찾을 수 없습니다.",
                reason_code="TASK_NOT_FOUND",
                task_id=task_id,
            )

        if not self._is_cancellable_status(row.get("task_status")):
            return self._build_response(
                result_code="REJECTED",
                result_message="이미 종료되었거나 취소할 수 없는 순찰 task입니다.",
                reason_code="TASK_NOT_CANCELLABLE",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                assigned_robot_id=row.get("assigned_robot_id"),
                cancellable=False,
            )

        return None

    def _build_cancel_target_response(self, row, *, task_id):
        if not row:
            return self._build_response(
                result_code="REJECTED",
                result_message="순찰 task를 찾을 수 없습니다.",
                reason_code="TASK_NOT_FOUND",
                task_id=task_id,
            )

        if not self._is_cancellable_status(row.get("task_status")):
            return self._build_response(
                result_code="REJECTED",
                result_message="이미 종료되었거나 취소할 수 없는 순찰 task입니다.",
                reason_code="TASK_NOT_CANCELLABLE",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                assigned_robot_id=row.get("assigned_robot_id"),
                cancellable=False,
            )

        return self._build_response(
            result_code="ACCEPTED",
            task_id=row.get("task_id"),
            task_status=row.get("task_status"),
            assigned_robot_id=row.get("assigned_robot_id"),
            cancellable=True,
        )

    def _build_cancel_write_plan(
        self,
        *,
        row,
        caregiver_id,
        reason,
        cancel_response,
    ):
        result_code, result_message, reason_code = self._normalize_cancel_result(
            cancel_response
        )
        cancel_requested = bool((cancel_response or {}).get("cancel_requested"))
        task_status = row.get("task_status")
        phase = row.get("phase")
        event_name = "PATROL_TASK_CANCEL_REJECTED"
        severity = "WARNING"

        if cancel_requested:
            task_status = TASK_STATUS_CANCEL_REQUESTED
            phase = TASK_STATUS_CANCEL_REQUESTED
            event_name = "PATROL_TASK_CANCEL_REQUESTED"
            severity = "INFO"
            reason_code = REASON_USER_CANCEL_REQUESTED

        payload = {
            "caregiver_id": caregiver_id,
            "reason": reason,
            "cancel_response": cancel_response or {},
        }
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "task_status": task_status,
            "phase": phase,
            "cancel_requested": cancel_requested,
            "update_task_params": (
                reason_code,
                result_code,
                result_message,
                row["task_id"],
            ),
            "update_detail_params": (
                TASK_STATUS_CANCEL_REQUESTED,
                row["task_id"],
            ),
            "history_params": (
                row["task_id"],
                row.get("task_status"),
                TASK_STATUS_CANCEL_REQUESTED,
                row.get("phase"),
                TASK_STATUS_CANCEL_REQUESTED,
                reason_code,
                result_message,
                CONTROL_SERVICE_COMPONENT,
            ),
            "event_params": (
                row["task_id"],
                event_name,
                severity,
                row.get("assigned_robot_id"),
                result_code,
                reason_code,
                result_message,
                json.dumps(payload, ensure_ascii=False),
            ),
        }

    @staticmethod
    def _normalize_cancel_result(cancel_response):
        cancel_response = cancel_response or {}
        cancel_requested = bool(cancel_response.get("cancel_requested"))
        result_code = str(cancel_response.get("result_code") or "UNKNOWN").strip() or "UNKNOWN"
        if cancel_requested:
            result_code = TASK_STATUS_CANCEL_REQUESTED
        result_message = cancel_response.get("result_message")
        if result_message is None:
            result_message = (
                "순찰 중단 요청이 접수되었습니다."
                if cancel_requested
                else "순찰 중단 요청이 수락되지 않았습니다."
            )
        reason_code = cancel_response.get("reason_code")
        if reason_code is None:
            reason_code = (
                REASON_USER_CANCEL_REQUESTED
                if cancel_requested
                else "ROS_CANCEL_NOT_ACCEPTED"
            )
        return result_code, result_message, reason_code

    @classmethod
    def _build_patrol_cancel_response(cls, *, row, plan, cancel_response):
        response = cls._build_response(
            result_code=plan["result_code"],
            result_message=plan["result_message"],
            reason_code=plan["reason_code"],
            task_id=row.get("task_id"),
            task_status=plan["task_status"],
            phase=plan["phase"],
            assigned_robot_id=row.get("assigned_robot_id"),
            cancellable=False if plan["cancel_requested"] else True,
            cancel_requested=plan["cancel_requested"],
        )
        response["ros_result"] = cancel_response
        return response

    @classmethod
    def _build_invalid_task_id_response(cls):
        return cls._build_response(
            result_code="REJECTED",
            result_message="task_id를 확인할 수 없습니다.",
            reason_code="TASK_ID_INVALID",
            task_id=None,
            cancellable=False,
        )

    @staticmethod
    def _parse_task_id(value):
        raw = str(value or "").strip()
        if not raw.isdigit():
            return None
        return int(raw)

    @staticmethod
    def _is_cancellable_status(task_status):
        return str(task_status or "").strip() in CANCELLABLE_PATROL_TASK_STATUSES

    @staticmethod
    def _begin(conn):
        if hasattr(conn, "begin"):
            conn.begin()

    @staticmethod
    def _build_response(
        *,
        result_code,
        result_message=None,
        reason_code=None,
        task_id=None,
        task_status=None,
        phase=None,
        assigned_robot_id=None,
        cancellable=None,
        cancel_requested=None,
    ):
        response = {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "task_id": task_id,
            "task_type": "PATROL",
            "task_status": task_status,
            "phase": phase,
            "assigned_robot_id": assigned_robot_id,
        }
        if cancellable is not None:
            response["cancellable"] = cancellable
        if cancel_requested is not None:
            response["cancel_requested"] = cancel_requested
        return response


__all__ = ["PatrolTaskCancelRepository"]
