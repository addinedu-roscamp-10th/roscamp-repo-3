import json

from server.ropi_main_service.persistence.async_connection import async_transaction
from server.ropi_main_service.persistence.connection import get_connection
from server.ropi_main_service.persistence.sql_loader import load_sql


CONTROL_SERVICE_COMPONENT = "control_service"
GUIDE_COMMAND_ACCEPTED = "GUIDE_COMMAND_ACCEPTED"
GUIDE_COMMAND_REJECTED = "GUIDE_COMMAND_REJECTED"
TERMINAL_GUIDE_STATUSES = {"COMPLETED", "CANCELLED", "FAILED"}
ALLOWED_CONTROL_GUIDE_COMMAND_TYPES = {"WAIT_TARGET_TRACKING", "START_GUIDANCE"}
UNSUPPORTED_GUIDE_COMMAND_MESSAGE = "지원하지 않는 안내 제어 명령입니다."


class GuideTaskLifecycleRepository:
    def __init__(
        self,
        *,
        connection_factory=None,
        async_transaction_factory=None,
    ):
        self.connection_factory = connection_factory or get_connection
        self.async_transaction_factory = async_transaction_factory or async_transaction

    def record_command_result(
        self,
        *,
        task_id,
        pinky_id,
        command_type,
        target_track_id="",
        wait_timeout_sec=0,
        finish_reason="",
        command_response=None,
    ):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._invalid_task_id_response()

        conn = self.connection_factory()
        try:
            self._begin(conn)
            with conn.cursor() as cur:
                cur.execute(
                    load_sql("guide/lock_guide_task_for_lifecycle.sql"),
                    (numeric_task_id,),
                )
                row = cur.fetchone()
                response = self._record_command_result_in_transaction(
                    cur,
                    row=row,
                    task_id=numeric_task_id,
                    pinky_id=pinky_id,
                    command_type=command_type,
                    target_track_id=target_track_id,
                    wait_timeout_sec=wait_timeout_sec,
                    finish_reason=finish_reason,
                    command_response=command_response,
                )
                conn.commit()
                return response
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def async_record_command_result(
        self,
        *,
        task_id,
        pinky_id,
        command_type,
        target_track_id="",
        wait_timeout_sec=0,
        finish_reason="",
        command_response=None,
    ):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._invalid_task_id_response()

        async with self.async_transaction_factory() as cur:
            await cur.execute(
                load_sql("guide/lock_guide_task_for_lifecycle.sql"),
                (numeric_task_id,),
            )
            row = await cur.fetchone()
            return await self._async_record_command_result_in_transaction(
                cur,
                row=row,
                task_id=numeric_task_id,
                pinky_id=pinky_id,
                command_type=command_type,
                target_track_id=target_track_id,
                wait_timeout_sec=wait_timeout_sec,
                finish_reason=finish_reason,
                command_response=command_response,
            )

    def _record_command_result_in_transaction(self, cur, **kwargs):
        row = kwargs["row"]
        guard = self._guard(row, task_id=kwargs["task_id"])
        if guard is not None:
            return guard

        plan = self._build_write_plan(**kwargs)
        if plan["accepted"]:
            cur.execute(
                load_sql("guide/update_guide_task_lifecycle.sql"),
                plan["update_task_params"],
            )
            cur.execute(
                load_sql("guide/update_guide_task_detail_lifecycle.sql"),
                plan["update_detail_params"],
            )
            if plan["state_changed"]:
                cur.execute(
                    load_sql("guide/insert_guide_task_lifecycle_history.sql"),
                    plan["history_params"],
                )
        else:
            cur.execute(
                load_sql("guide/update_guide_task_latest_result.sql"),
                plan["update_latest_result_params"],
            )

        cur.execute(
            load_sql("guide/insert_guide_task_lifecycle_event.sql"),
            plan["event_params"],
        )
        return self._build_response(row=row, plan=plan)

    async def _async_record_command_result_in_transaction(self, cur, **kwargs):
        row = kwargs["row"]
        guard = self._guard(row, task_id=kwargs["task_id"])
        if guard is not None:
            return guard

        plan = self._build_write_plan(**kwargs)
        if plan["accepted"]:
            await cur.execute(
                load_sql("guide/update_guide_task_lifecycle.sql"),
                plan["update_task_params"],
            )
            await cur.execute(
                load_sql("guide/update_guide_task_detail_lifecycle.sql"),
                plan["update_detail_params"],
            )
            if plan["state_changed"]:
                await cur.execute(
                    load_sql("guide/insert_guide_task_lifecycle_history.sql"),
                    plan["history_params"],
                )
        else:
            await cur.execute(
                load_sql("guide/update_guide_task_latest_result.sql"),
                plan["update_latest_result_params"],
            )

        await cur.execute(
            load_sql("guide/insert_guide_task_lifecycle_event.sql"),
            plan["event_params"],
        )
        return self._build_response(row=row, plan=plan)

    def _build_write_plan(
        self,
        *,
        row,
        task_id,
        pinky_id,
        command_type,
        target_track_id="",
        wait_timeout_sec=0,
        finish_reason="",
        command_response=None,
    ):
        command_response = self._normalize_command_response(command_response)
        command_type = self._normalize_token(command_type)
        target_track_id = self._normalize_target_track_id(target_track_id)
        finish_reason = self._normalize_token(finish_reason)
        command_supported = command_type in ALLOWED_CONTROL_GUIDE_COMMAND_TYPES
        accepted = bool(command_response.get("accepted")) and command_supported
        current_status = str(row.get("task_status") or "").strip()
        current_phase = str(row.get("phase") or "").strip() or None
        if command_supported:
            message = self._extract_message(command_response, accepted=accepted)
            rejected_reason_code = self._rejected_reason_code(command_response)
        else:
            message = UNSUPPORTED_GUIDE_COMMAND_MESSAGE
            rejected_reason_code = "COMMAND_TYPE_INVALID"

        if accepted:
            result_code = "ACCEPTED"
            reason_code = self._accepted_reason_code(
                command_type=command_type,
                finish_reason=finish_reason,
            )
            task_status, phase, guide_phase, is_terminal = self._accepted_target_state(
                command_type=command_type,
                finish_reason=finish_reason,
            )
            event_name = GUIDE_COMMAND_ACCEPTED
            severity = "INFO"
        else:
            result_code = "REJECTED"
            reason_code = rejected_reason_code
            task_status = current_status
            phase = current_phase
            guide_phase = row.get("guide_phase")
            is_terminal = False
            event_name = GUIDE_COMMAND_REJECTED
            severity = "WARNING"

        next_target_track_id = self._next_target_track_id(
            row=row,
            command_type=command_type,
            target_track_id=target_track_id,
            accepted=accepted,
        )
        state_changed = (
            accepted
            and (
                current_status != task_status
                or current_phase != phase
                or row.get("guide_phase") != guide_phase
            )
        )
        payload = {
            "command_type": command_type,
            "target_track_id": target_track_id,
            "wait_timeout_sec": wait_timeout_sec,
            "finish_reason": finish_reason,
            "command_response": command_response,
        }
        return {
            "accepted": accepted,
            "result_code": result_code,
            "result_message": message,
            "reason_code": reason_code,
            "task_status": task_status,
            "phase": phase,
            "guide_phase": guide_phase,
            "target_track_id": next_target_track_id,
            "state_changed": state_changed,
            "update_task_params": (
                task_status,
                phase,
                reason_code,
                result_code,
                message,
                bool(task_status == "RUNNING"),
                bool(is_terminal),
                task_id,
            ),
            "update_detail_params": (
                guide_phase,
                next_target_track_id,
                task_id,
            ),
            "update_latest_result_params": (
                reason_code,
                result_code,
                message,
                task_id,
            ),
            "history_params": (
                task_id,
                current_status,
                task_status,
                current_phase,
                phase,
                reason_code,
                message,
                CONTROL_SERVICE_COMPONENT,
            ),
            "event_params": (
                task_id,
                event_name,
                severity,
                str(pinky_id or row.get("assigned_robot_id") or "").strip() or None,
                result_code,
                reason_code,
                message,
                json.dumps(payload, ensure_ascii=False),
            ),
        }

    @classmethod
    def _accepted_target_state(cls, *, command_type, finish_reason):
        if command_type == "WAIT_TARGET_TRACKING":
            return "RUNNING", "WAIT_TARGET_TRACKING", "WAIT_TARGET_TRACKING", False
        if command_type == "START_GUIDANCE":
            return "RUNNING", "GUIDANCE_RUNNING", "GUIDANCE_RUNNING", False
        return "RUNNING", command_type or "GUIDE_COMMAND_ACCEPTED", command_type or "RUNNING", False

    @staticmethod
    def _accepted_reason_code(*, command_type, finish_reason):
        return "GUIDE_COMMAND_ACCEPTED"

    @staticmethod
    def _rejected_reason_code(command_response):
        reason_code = str((command_response or {}).get("reason_code") or "").strip()
        return reason_code or "GUIDE_COMMAND_REJECTED"

    @staticmethod
    def _extract_message(command_response, *, accepted):
        result_message = str((command_response or {}).get("result_message") or "").strip()
        if result_message:
            return result_message
        message = str((command_response or {}).get("message") or "").strip()
        if message:
            return message
        if accepted:
            return "안내 제어 명령이 수락되었습니다."
        return "안내 제어 명령이 거부되었습니다."

    @staticmethod
    def _normalize_command_response(command_response):
        if isinstance(command_response, dict):
            return command_response
        if command_response is None:
            return {}
        return {"response": command_response}

    @staticmethod
    def _next_target_track_id(*, row, command_type, target_track_id, accepted):
        if not accepted:
            return row.get("target_track_id")
        if command_type == "START_GUIDANCE":
            if target_track_id is not None and target_track_id >= 0:
                return target_track_id
            return row.get("target_track_id")
        if command_type == "WAIT_TARGET_TRACKING":
            return None
        if target_track_id is not None and target_track_id >= 0:
            return target_track_id
        return row.get("target_track_id")

    @classmethod
    def _guard(cls, row, *, task_id):
        if not row:
            return cls._response(
                result_code="REJECTED",
                result_message="안내 task를 찾을 수 없습니다.",
                reason_code="TASK_NOT_FOUND",
                task_id=task_id,
            )
        if str(row.get("task_type") or "").strip() != "GUIDE":
            return cls._response(
                result_code="REJECTED",
                result_message="안내 task가 아닙니다.",
                reason_code="TASK_TYPE_MISMATCH",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                phase=row.get("phase"),
                assigned_robot_id=row.get("assigned_robot_id"),
            )
        if str(row.get("task_status") or "").strip() in TERMINAL_GUIDE_STATUSES:
            return cls._response(
                result_code="REJECTED",
                result_message="이미 종료된 안내 task입니다.",
                reason_code="TASK_ALREADY_FINISHED",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                phase=row.get("phase"),
                assigned_robot_id=row.get("assigned_robot_id"),
                guide_phase=row.get("guide_phase"),
            )
        return None

    @classmethod
    def _build_response(cls, *, row, plan):
        return cls._response(
            result_code=plan["result_code"],
            result_message=plan["result_message"],
            reason_code=plan["reason_code"],
            task_id=row.get("task_id"),
            task_status=plan["task_status"],
            phase=plan["phase"],
            assigned_robot_id=row.get("assigned_robot_id"),
            guide_phase=plan["guide_phase"],
            target_track_id=plan["target_track_id"],
            accepted=plan["accepted"],
        )

    @classmethod
    def _invalid_task_id_response(cls):
        return cls._response(
            result_code="REJECTED",
            result_message="task_id를 확인할 수 없습니다.",
            reason_code="TASK_ID_INVALID",
        )

    @staticmethod
    def _parse_task_id(value):
        raw = str(value or "").strip()
        if not raw.isdigit():
            return None
        return int(raw)

    @staticmethod
    def _normalize_token(value):
        return str(value or "").strip().upper()

    @staticmethod
    def _normalize_target_track_id(value):
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _begin(conn):
        if hasattr(conn, "begin"):
            conn.begin()

    @staticmethod
    def _response(
        *,
        result_code,
        result_message=None,
        reason_code=None,
        task_id=None,
        task_status=None,
        phase=None,
        assigned_robot_id=None,
        guide_phase=None,
        target_track_id=None,
        accepted=None,
    ):
        response = {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "task_id": task_id,
            "task_type": "GUIDE",
            "task_status": task_status,
            "phase": phase,
            "assigned_robot_id": assigned_robot_id,
            "guide_phase": guide_phase,
            "target_track_id": target_track_id,
        }
        if accepted is not None:
            response["accepted"] = accepted
        return response


__all__ = ["GuideTaskLifecycleRepository"]
