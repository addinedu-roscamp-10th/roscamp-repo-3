import json

from server.ropi_main_service.persistence.async_connection import (
    async_fetch_one,
    async_transaction,
)
from server.ropi_main_service.persistence.connection import fetch_one, get_connection
from server.ropi_main_service.persistence.sql_loader import load_sql


CONTROL_SERVICE_COMPONENT = "control_service"
TASK_STATUS_CANCEL_REQUESTED = "CANCEL_REQUESTED"
TASK_STATUS_CANCELLED = "CANCELLED"
REASON_USER_CANCEL_REQUESTED = "USER_CANCEL_REQUESTED"
REASON_ROS_ACTION_CANCELLED = "ROS_ACTION_CANCELLED"
CANCELLABLE_DELIVERY_TASK_STATUSES = {
    "WAITING",
    "WAITING_DISPATCH",
    "READY",
    "ASSIGNED",
    "RUNNING",
}
CANCEL_FINALIZABLE_DELIVERY_TASK_STATUSES = {
    TASK_STATUS_CANCEL_REQUESTED,
}


class DeliveryTaskCancelRepository:
    def get_delivery_task_cancel_target(self, task_id):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._build_invalid_task_id_cancel_response()

        row = self._fetch_delivery_task_cancel_target(numeric_task_id)
        return self._build_cancel_target_response(row, task_id=numeric_task_id)

    async def async_get_delivery_task_cancel_target(self, task_id):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._build_invalid_task_id_cancel_response()

        row = await async_fetch_one(
            load_sql("delivery/find_delivery_task_for_cancel.sql"),
            (numeric_task_id,),
        )
        return self._build_cancel_target_response(row, task_id=numeric_task_id)

    def record_delivery_task_cancel_result(self, *, task_id, cancel_response):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._build_invalid_task_id_cancel_response()

        conn = get_connection()
        try:
            self._begin(conn)
            with conn.cursor() as cur:
                row = self._lock_delivery_task_cancel_target(cur, numeric_task_id)
                response = self._record_delivery_task_cancel_result(
                    cur,
                    row=row,
                    task_id=numeric_task_id,
                    cancel_response=cancel_response,
                )
                conn.commit()
                return response
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def async_record_delivery_task_cancel_result(self, *, task_id, cancel_response):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._build_invalid_task_id_cancel_response()

        async with async_transaction() as cur:
            await cur.execute(
                load_sql("delivery/lock_delivery_task_for_cancel.sql"),
                (numeric_task_id,),
            )
            row = await cur.fetchone()
            return await self._async_record_delivery_task_cancel_result(
                cur,
                row=row,
                task_id=numeric_task_id,
                cancel_response=cancel_response,
            )

    def record_delivery_task_cancelled_result(self, *, task_id, workflow_response):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._build_invalid_task_id_cancelled_response(workflow_response)

        conn = get_connection()
        try:
            self._begin(conn)
            with conn.cursor() as cur:
                row = self._lock_delivery_task_cancel_target(cur, numeric_task_id)
                response = self._record_delivery_task_cancelled_result(
                    cur,
                    row=row,
                    task_id=numeric_task_id,
                    workflow_response=workflow_response,
                )
                conn.commit()
                return response
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def async_record_delivery_task_cancelled_result(self, *, task_id, workflow_response):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._build_invalid_task_id_cancelled_response(workflow_response)

        async with async_transaction() as cur:
            await cur.execute(
                load_sql("delivery/lock_delivery_task_for_cancel.sql"),
                (numeric_task_id,),
            )
            row = await cur.fetchone()
            return await self._async_record_delivery_task_cancelled_result(
                cur,
                row=row,
                task_id=numeric_task_id,
                workflow_response=workflow_response,
            )

    @classmethod
    def _build_invalid_task_id_cancel_response(cls):
        return cls._build_cancel_task_response(
            result_code="REJECTED",
            result_message="task_id를 확인할 수 없습니다.",
            reason_code="TASK_ID_INVALID",
            task_id=None,
        )

    @classmethod
    def _build_invalid_task_id_cancelled_response(cls, workflow_response):
        return cls._build_cancelled_task_response(
            result_code="REJECTED",
            result_message="task_id를 확인할 수 없습니다.",
            reason_code="TASK_ID_INVALID",
            task_id=None,
            workflow_response=workflow_response,
        )

    @staticmethod
    def _parse_task_id(value):
        raw = str(value or "").strip()
        if not raw.isdigit():
            return None
        return int(raw)

    @staticmethod
    def _is_cancellable_task_status(task_status):
        return str(task_status or "").strip() in CANCELLABLE_DELIVERY_TASK_STATUSES

    @classmethod
    def _build_cancel_target_response(cls, row, *, task_id):
        if not row:
            return cls._build_cancel_task_response(
                result_code="REJECTED",
                result_message="운반 task를 찾을 수 없습니다.",
                reason_code="TASK_NOT_FOUND",
                task_id=task_id,
            )

        if not cls._is_cancellable_task_status(row.get("task_status")):
            return cls._build_cancel_task_response(
                result_code="REJECTED",
                result_message="이미 종료되었거나 취소할 수 없는 운반 task입니다.",
                reason_code="TASK_NOT_CANCELLABLE",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                assigned_robot_id=row.get("assigned_robot_id"),
            )

        return cls._build_cancel_task_response(
            result_code="ACCEPTED",
            task_id=row.get("task_id"),
            task_status=row.get("task_status"),
            assigned_robot_id=row.get("assigned_robot_id"),
        )

    @staticmethod
    def _fetch_delivery_task_cancel_target(task_id):
        return fetch_one(
            load_sql("delivery/find_delivery_task_for_cancel.sql"),
            (task_id,),
        )

    @staticmethod
    def _lock_delivery_task_cancel_target(cur, task_id):
        cur.execute(
            load_sql("delivery/lock_delivery_task_for_cancel.sql"),
            (task_id,),
        )
        return cur.fetchone()

    def _record_delivery_task_cancel_result(self, cur, *, row, task_id, cancel_response):
        guard_response = self._build_cancel_result_guard(row, task_id=task_id)
        if guard_response is not None:
            return guard_response

        return self._write_cancel_result(cur, row=row, cancel_response=cancel_response)

    async def _async_record_delivery_task_cancel_result(self, cur, *, row, task_id, cancel_response):
        guard_response = self._build_cancel_result_guard(row, task_id=task_id)
        if guard_response is not None:
            return guard_response

        return await self._async_write_cancel_result(cur, row=row, cancel_response=cancel_response)

    def _record_delivery_task_cancelled_result(self, cur, *, row, task_id, workflow_response):
        guard_response = self._build_cancelled_result_guard(
            row,
            task_id=task_id,
            workflow_response=workflow_response,
        )
        if guard_response is not None:
            return guard_response

        return self._write_cancelled_result(cur, row=row, workflow_response=workflow_response)

    async def _async_record_delivery_task_cancelled_result(self, cur, *, row, task_id, workflow_response):
        guard_response = self._build_cancelled_result_guard(
            row,
            task_id=task_id,
            workflow_response=workflow_response,
        )
        if guard_response is not None:
            return guard_response

        return await self._async_write_cancelled_result(cur, row=row, workflow_response=workflow_response)

    def _build_cancel_result_guard(self, row, *, task_id):
        if not row:
            return self._build_cancel_task_response(
                result_code="REJECTED",
                result_message="운반 task를 찾을 수 없습니다.",
                reason_code="TASK_NOT_FOUND",
                task_id=task_id,
            )

        if not self._is_cancellable_task_status(row.get("task_status")):
            return self._build_cancel_task_response(
                result_code="REJECTED",
                result_message="이미 종료되었거나 취소할 수 없는 운반 task입니다.",
                reason_code="TASK_NOT_CANCELLABLE",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                assigned_robot_id=row.get("assigned_robot_id"),
            )

        return None

    def _build_cancelled_result_guard(self, row, *, task_id, workflow_response):
        if not row:
            return self._build_cancelled_task_response(
                result_code="REJECTED",
                result_message="운반 task를 찾을 수 없습니다.",
                reason_code="TASK_NOT_FOUND",
                task_id=task_id,
                workflow_response=workflow_response,
            )

        if str(row.get("task_status") or "").strip() == TASK_STATUS_CANCELLED:
            return self._build_cancelled_task_response(
                result_code=TASK_STATUS_CANCELLED,
                result_message="운반 task가 이미 취소 완료 상태입니다.",
                reason_code="ALREADY_CANCELLED",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                assigned_robot_id=row.get("assigned_robot_id"),
                workflow_response=workflow_response,
            )

        if str(row.get("task_status") or "").strip() not in CANCEL_FINALIZABLE_DELIVERY_TASK_STATUSES:
            return self._build_cancelled_task_response(
                result_code="IGNORED",
                result_message="취소 요청 상태가 아니므로 취소 완료로 확정하지 않았습니다.",
                reason_code="TASK_NOT_CANCEL_REQUESTED",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                assigned_robot_id=row.get("assigned_robot_id"),
                workflow_response=workflow_response,
            )

        return None

    def _write_cancel_result(self, cur, *, row, cancel_response):
        plan = self._build_cancel_result_write_plan(row=row, cancel_response=cancel_response)
        if plan["cancel_requested"]:
            cur.execute(
                load_sql("delivery/update_task_cancel_requested.sql"),
                plan["update_params"],
            )
            cur.execute(
                load_sql("delivery/insert_cancel_task_history.sql"),
                plan["history_params"],
            )

        cur.execute(
            load_sql("delivery/insert_cancel_task_event.sql"),
            plan["event_params"],
        )
        return self._build_cancel_task_response(
            result_code=plan["result_code"],
            result_message=plan["result_message"],
            reason_code=plan["reason_code"],
            task_id=row.get("task_id"),
            task_status=plan["task_status"],
            assigned_robot_id=row.get("assigned_robot_id"),
            cancel_requested=plan["cancel_requested"],
            ros_result=cancel_response,
        )

    def _write_cancelled_result(self, cur, *, row, workflow_response):
        plan = self._build_cancelled_result_write_plan(row=row, workflow_response=workflow_response)
        cur.execute(
            load_sql("delivery/update_task_cancelled.sql"),
            plan["update_params"],
        )
        cur.execute(
            load_sql("delivery/insert_cancelled_task_history.sql"),
            plan["history_params"],
        )
        cur.execute(
            load_sql("delivery/insert_cancel_task_event.sql"),
            plan["event_params"],
        )
        return self._build_cancelled_task_response(
            result_code=plan["result_code"],
            result_message=plan["result_message"],
            reason_code=plan["reason_code"],
            task_id=row.get("task_id"),
            task_status=plan["task_status"],
            assigned_robot_id=row.get("assigned_robot_id"),
            workflow_response=workflow_response,
        )

    async def _async_write_cancel_result(self, cur, *, row, cancel_response):
        plan = self._build_cancel_result_write_plan(row=row, cancel_response=cancel_response)
        if plan["cancel_requested"]:
            await cur.execute(
                load_sql("delivery/update_task_cancel_requested.sql"),
                plan["update_params"],
            )
            await cur.execute(
                load_sql("delivery/insert_cancel_task_history.sql"),
                plan["history_params"],
            )

        await cur.execute(
            load_sql("delivery/insert_cancel_task_event.sql"),
            plan["event_params"],
        )
        return self._build_cancel_task_response(
            result_code=plan["result_code"],
            result_message=plan["result_message"],
            reason_code=plan["reason_code"],
            task_id=row.get("task_id"),
            task_status=plan["task_status"],
            assigned_robot_id=row.get("assigned_robot_id"),
            cancel_requested=plan["cancel_requested"],
            ros_result=cancel_response,
        )

    async def _async_write_cancelled_result(self, cur, *, row, workflow_response):
        plan = self._build_cancelled_result_write_plan(row=row, workflow_response=workflow_response)
        await cur.execute(
            load_sql("delivery/update_task_cancelled.sql"),
            plan["update_params"],
        )
        await cur.execute(
            load_sql("delivery/insert_cancelled_task_history.sql"),
            plan["history_params"],
        )
        await cur.execute(
            load_sql("delivery/insert_cancel_task_event.sql"),
            plan["event_params"],
        )
        return self._build_cancelled_task_response(
            result_code=plan["result_code"],
            result_message=plan["result_message"],
            reason_code=plan["reason_code"],
            task_id=row.get("task_id"),
            task_status=plan["task_status"],
            assigned_robot_id=row.get("assigned_robot_id"),
            workflow_response=workflow_response,
        )

    def _build_cancel_result_write_plan(self, *, row, cancel_response):
        result_code, result_message, reason_code = self._normalize_cancel_result(cancel_response)
        cancel_requested = bool((cancel_response or {}).get("cancel_requested"))
        task_status = row.get("task_status")
        event_name = "DELIVERY_TASK_CANCEL_REJECTED"
        severity = "WARNING"
        update_params = None
        history_params = None

        if cancel_requested:
            task_status = TASK_STATUS_CANCEL_REQUESTED
            event_name = "DELIVERY_TASK_CANCEL_REQUESTED"
            severity = "INFO"
            update_params = (
                REASON_USER_CANCEL_REQUESTED,
                result_code,
                result_message,
                row["task_id"],
            )
            history_params = (
                row["task_id"],
                row.get("task_status"),
                row.get("phase"),
                REASON_USER_CANCEL_REQUESTED,
                result_message,
                CONTROL_SERVICE_COMPONENT,
            )

        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "task_status": task_status,
            "cancel_requested": cancel_requested,
            "update_params": update_params,
            "history_params": history_params,
            "event_params": self._build_task_event_params(
                row=row,
                event_name=event_name,
                severity=severity,
                result_code=result_code,
                reason_code=reason_code,
                result_message=result_message,
                payload=cancel_response,
            ),
        }

    def _build_cancelled_result_write_plan(self, *, row, workflow_response):
        result_code, result_message, reason_code = self._normalize_cancelled_workflow_result(workflow_response)
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "task_status": TASK_STATUS_CANCELLED,
            "update_params": (
                reason_code,
                result_code,
                result_message,
                row["task_id"],
            ),
            "history_params": (
                row["task_id"],
                row.get("task_status"),
                row.get("phase"),
                reason_code,
                result_message,
                CONTROL_SERVICE_COMPONENT,
            ),
            "event_params": self._build_task_event_params(
                row=row,
                event_name="DELIVERY_TASK_CANCELLED",
                severity="INFO",
                result_code=result_code,
                reason_code=reason_code,
                result_message=result_message,
                payload=workflow_response,
            ),
        }

    @staticmethod
    def _build_task_event_params(
        *,
        row,
        event_name,
        severity,
        result_code,
        reason_code,
        result_message,
        payload,
    ):
        return (
            row["task_id"],
            event_name,
            severity,
            row.get("assigned_robot_id"),
            result_code,
            reason_code,
            result_message,
            json.dumps(payload or {}, ensure_ascii=False),
        )

    @staticmethod
    def _normalize_cancel_result(cancel_response):
        cancel_response = cancel_response or {}
        result_code = str(cancel_response.get("result_code") or "UNKNOWN").strip() or "UNKNOWN"
        result_message = cancel_response.get("result_message")
        if result_message is None:
            result_message = (
                "운반 task 취소 요청이 접수되었습니다."
                if cancel_response.get("cancel_requested")
                else "운반 task 취소 요청이 수락되지 않았습니다."
            )
        reason_code = cancel_response.get("reason_code")
        if reason_code is None:
            reason_code = (
                REASON_USER_CANCEL_REQUESTED
                if cancel_response.get("cancel_requested")
                else "ROS_CANCEL_NOT_ACCEPTED"
            )
        return result_code, result_message, reason_code

    @staticmethod
    def _normalize_cancelled_workflow_result(workflow_response):
        workflow_response = workflow_response or {}
        result_message = workflow_response.get("result_message") or "운반 task가 취소 완료되었습니다."
        return TASK_STATUS_CANCELLED, result_message, REASON_ROS_ACTION_CANCELLED

    @staticmethod
    def _begin(conn):
        if hasattr(conn, "begin"):
            conn.begin()

    @staticmethod
    def _build_delivery_task_response(
        *,
        result_code,
        result_message=None,
        reason_code=None,
        task_id=None,
        task_status=None,
        assigned_robot_id=None,
    ):
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "task_id": task_id,
            "task_status": task_status,
            "assigned_robot_id": assigned_robot_id,
        }

    @classmethod
    def _build_cancel_task_response(
        cls,
        *,
        result_code,
        result_message=None,
        reason_code=None,
        task_id=None,
        task_status=None,
        assigned_robot_id=None,
        cancel_requested=None,
        ros_result=None,
    ):
        response = cls._build_delivery_task_response(
            result_code=result_code,
            result_message=result_message,
            reason_code=reason_code,
            task_id=task_id,
            task_status=task_status,
            assigned_robot_id=assigned_robot_id,
        )
        if cancel_requested is not None:
            response["cancel_requested"] = cancel_requested
        if ros_result is not None:
            response["ros_result"] = ros_result
        return response

    @classmethod
    def _build_cancelled_task_response(
        cls,
        *,
        result_code,
        result_message=None,
        reason_code=None,
        task_id=None,
        task_status=None,
        assigned_robot_id=None,
        workflow_response=None,
    ):
        response = cls._build_delivery_task_response(
            result_code=result_code,
            result_message=result_message,
            reason_code=reason_code,
            task_id=task_id,
            task_status=task_status,
            assigned_robot_id=assigned_robot_id,
        )
        if workflow_response is not None:
            response["workflow_result"] = workflow_response
        return response


__all__ = ["DeliveryTaskCancelRepository"]
