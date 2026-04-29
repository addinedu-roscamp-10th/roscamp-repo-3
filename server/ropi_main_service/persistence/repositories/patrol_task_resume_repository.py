import json

from server.ropi_main_service.persistence.async_connection import (
    async_fetch_one,
    async_transaction,
)
from server.ropi_main_service.persistence.connection import fetch_one, get_connection
from server.ropi_main_service.persistence.sql_loader import load_sql


CONTROL_SERVICE_COMPONENT = "control_service"
RESUME_RESULT_CODE = "ACCEPTED"
RESUME_RESULT_MESSAGE = "순찰을 재개합니다."
RESUME_REASON_CODE = "PATROL_RESUME_REQUESTED"
TASK_STATUS_RUNNING = "RUNNING"
PHASE_FOLLOW_PATROL_PATH = "FOLLOW_PATROL_PATH"
PATROL_STATUS_MOVING = "MOVING"
WAITING_FALL_RESPONSE_PHASES = {
    "WAIT_FALL_RESPONSE",
    "WAITING_FALL_RESPONSE",
}


class PatrolTaskResumeRepository:
    def get_patrol_task_resume_target(self, task_id):
        numeric_task_id = self.parse_task_id(task_id)
        if numeric_task_id is None:
            return self.build_not_found_response(task_id=task_id)

        row = fetch_one(
            load_sql("patrol/lock_patrol_task_for_resume.sql").replace(
                "FOR UPDATE",
                "",
            ),
            (numeric_task_id,),
        )
        return self.build_resume_target_response(row, task_id=numeric_task_id)

    async def async_get_patrol_task_resume_target(self, task_id):
        numeric_task_id = self.parse_task_id(task_id)
        if numeric_task_id is None:
            return self.build_not_found_response(task_id=task_id)

        row = await async_fetch_one(
            load_sql("patrol/lock_patrol_task_for_resume.sql").replace(
                "FOR UPDATE",
                "",
            ),
            (numeric_task_id,),
        )
        return self.build_resume_target_response(row, task_id=numeric_task_id)

    def record_patrol_task_resume_result(
        self,
        *,
        task_id,
        caregiver_id,
        member_id,
        action_memo,
        resume_command_response,
    ):
        numeric_task_id = self.parse_task_id(task_id)
        if numeric_task_id is None:
            return self.build_not_found_response(task_id=task_id)

        conn = get_connection()
        try:
            conn.begin()
            with conn.cursor() as cur:
                row = self._lock_resume_target(cur, numeric_task_id)
                response = self._record_resume_result(
                    cur,
                    row=row,
                    task_id=numeric_task_id,
                    caregiver_id=caregiver_id,
                    member_id=member_id,
                    action_memo=action_memo,
                    resume_command_response=resume_command_response,
                )
                conn.commit()
                return response
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def async_record_patrol_task_resume_result(
        self,
        *,
        task_id,
        caregiver_id,
        member_id,
        action_memo,
        resume_command_response,
    ):
        numeric_task_id = self.parse_task_id(task_id)
        if numeric_task_id is None:
            return self.build_not_found_response(task_id=task_id)

        async with async_transaction() as cur:
            await cur.execute(
                load_sql("patrol/lock_patrol_task_for_resume.sql"),
                (numeric_task_id,),
            )
            row = await cur.fetchone()
            return await self._async_record_resume_result(
                cur,
                row=row,
                task_id=numeric_task_id,
                caregiver_id=caregiver_id,
                member_id=member_id,
                action_memo=action_memo,
                resume_command_response=resume_command_response,
            )

    @staticmethod
    def parse_task_id(task_id):
        try:
            value = int(str(task_id).strip())
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    @classmethod
    def build_resume_target_response(cls, row, *, task_id):
        guard_response = cls.build_resume_guard_response(row, task_id=task_id)
        if guard_response is not None:
            return guard_response

        return cls.build_patrol_resume_response(
            result_code="ACCEPTED",
            task_id=row.get("task_id"),
            task_status=row.get("task_status"),
            phase=row.get("phase"),
            assigned_robot_id=row.get("assigned_robot_id"),
            cancellable=False,
        )

    @classmethod
    def build_resume_guard_response(cls, row, *, task_id):
        if not row:
            return cls.build_not_found_response(task_id=task_id)

        if str(row.get("task_type") or "").strip().upper() != "PATROL":
            return cls.build_not_allowed_response(
                reason_code="TASK_NOT_PATROL",
                result_message="순찰 task가 아닙니다.",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                phase=row.get("phase"),
                assigned_robot_id=row.get("assigned_robot_id"),
            )

        phase = str(row.get("phase") or "").strip().upper()
        patrol_status = str(row.get("patrol_status") or "").strip().upper()
        if (
            phase not in WAITING_FALL_RESPONSE_PHASES
            and patrol_status not in WAITING_FALL_RESPONSE_PHASES
        ):
            return cls.build_not_allowed_response(
                reason_code="PATROL_NOT_WAITING_FALL_RESPONSE",
                result_message="낙상 대응 대기 상태의 순찰 task만 재개할 수 있습니다.",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                phase=row.get("phase"),
                assigned_robot_id=row.get("assigned_robot_id"),
            )

        if not str(row.get("assigned_robot_id") or "").strip():
            return cls.build_not_allowed_response(
                reason_code="PATROL_ROBOT_NOT_ASSIGNED",
                result_message="재개 명령을 보낼 순찰 로봇이 배정되지 않았습니다.",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                phase=row.get("phase"),
                assigned_robot_id=row.get("assigned_robot_id"),
            )

        return None

    @classmethod
    def build_not_found_response(cls, *, task_id):
        return cls.build_patrol_resume_response(
            result_code="NOT_FOUND",
            result_message="순찰 task를 찾을 수 없습니다.",
            reason_code="TASK_NOT_FOUND",
            task_id=task_id,
            cancellable=False,
        )

    @classmethod
    def build_not_allowed_response(
        cls,
        *,
        reason_code,
        result_message,
        task_id=None,
        task_status=None,
        phase=None,
        assigned_robot_id=None,
    ):
        return cls.build_patrol_resume_response(
            result_code="NOT_ALLOWED",
            result_message=result_message,
            reason_code=reason_code,
            task_id=task_id,
            task_status=task_status,
            phase=phase,
            assigned_robot_id=assigned_robot_id,
            cancellable=False,
        )

    @staticmethod
    def _lock_resume_target(cur, task_id):
        cur.execute(
            load_sql("patrol/lock_patrol_task_for_resume.sql"),
            (task_id,),
        )
        return cur.fetchone()

    def _record_resume_result(
        self,
        cur,
        *,
        row,
        task_id,
        caregiver_id,
        member_id,
        action_memo,
        resume_command_response,
    ):
        guard_response = self.build_resume_guard_response(row, task_id=task_id)
        if guard_response is not None:
            return guard_response

        return self._write_resume_result(
            cur,
            row=row,
            caregiver_id=caregiver_id,
            member_id=member_id,
            action_memo=action_memo,
            resume_command_response=resume_command_response,
        )

    async def _async_record_resume_result(
        self,
        cur,
        *,
        row,
        task_id,
        caregiver_id,
        member_id,
        action_memo,
        resume_command_response,
    ):
        guard_response = self.build_resume_guard_response(row, task_id=task_id)
        if guard_response is not None:
            return guard_response

        return await self._async_write_resume_result(
            cur,
            row=row,
            caregiver_id=caregiver_id,
            member_id=member_id,
            action_memo=action_memo,
            resume_command_response=resume_command_response,
        )

    def _write_resume_result(
        self,
        cur,
        *,
        row,
        caregiver_id,
        member_id,
        action_memo,
        resume_command_response,
    ):
        payload_json = self._build_payload_json(
            caregiver_id=caregiver_id,
            member_id=member_id,
            action_memo=action_memo,
            resume_command_response=resume_command_response,
        )
        cur.execute(
            load_sql("patrol/update_patrol_task_resumed.sql"),
            (RESUME_RESULT_CODE, RESUME_RESULT_MESSAGE, row["task_id"]),
        )
        cur.execute(
            load_sql("patrol/update_patrol_task_detail_resumed.sql"),
            (PATROL_STATUS_MOVING, row["task_id"]),
        )
        cur.execute(
            load_sql("patrol/insert_patrol_resume_task_history.sql"),
            (
                row["task_id"],
                row.get("task_status"),
                row.get("phase"),
                RESUME_REASON_CODE,
                RESUME_RESULT_MESSAGE,
                CONTROL_SERVICE_COMPONENT,
            ),
        )
        cur.execute(
            load_sql("patrol/insert_patrol_resume_task_event.sql"),
            self._build_event_params(row=row, payload_json=payload_json),
        )
        return self._build_accepted_response(row)

    async def _async_write_resume_result(
        self,
        cur,
        *,
        row,
        caregiver_id,
        member_id,
        action_memo,
        resume_command_response,
    ):
        payload_json = self._build_payload_json(
            caregiver_id=caregiver_id,
            member_id=member_id,
            action_memo=action_memo,
            resume_command_response=resume_command_response,
        )
        await cur.execute(
            load_sql("patrol/update_patrol_task_resumed.sql"),
            (RESUME_RESULT_CODE, RESUME_RESULT_MESSAGE, row["task_id"]),
        )
        await cur.execute(
            load_sql("patrol/update_patrol_task_detail_resumed.sql"),
            (PATROL_STATUS_MOVING, row["task_id"]),
        )
        await cur.execute(
            load_sql("patrol/insert_patrol_resume_task_history.sql"),
            (
                row["task_id"],
                row.get("task_status"),
                row.get("phase"),
                RESUME_REASON_CODE,
                RESUME_RESULT_MESSAGE,
                CONTROL_SERVICE_COMPONENT,
            ),
        )
        await cur.execute(
            load_sql("patrol/insert_patrol_resume_task_event.sql"),
            self._build_event_params(row=row, payload_json=payload_json),
        )
        return self._build_accepted_response(row)

    @staticmethod
    def _build_payload_json(
        *,
        caregiver_id,
        member_id,
        action_memo,
        resume_command_response,
    ):
        return json.dumps(
            {
                "caregiver_id": caregiver_id,
                "member_id": member_id,
                "action_memo": action_memo,
                "resume_command_response": resume_command_response,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    @staticmethod
    def _build_event_params(*, row, payload_json):
        return (
            row["task_id"],
            "PATROL_TASK_RESUMED",
            "INFO",
            row.get("assigned_robot_id"),
            RESUME_RESULT_CODE,
            RESUME_REASON_CODE,
            RESUME_RESULT_MESSAGE,
            payload_json,
        )

    @classmethod
    def _build_accepted_response(cls, row):
        return cls.build_patrol_resume_response(
            result_code=RESUME_RESULT_CODE,
            result_message=RESUME_RESULT_MESSAGE,
            reason_code=None,
            task_id=row.get("task_id"),
            task_status=TASK_STATUS_RUNNING,
            phase=PHASE_FOLLOW_PATROL_PATH,
            assigned_robot_id=row.get("assigned_robot_id"),
            cancellable=True,
        )

    @staticmethod
    def build_patrol_resume_response(
        *,
        result_code,
        result_message=None,
        reason_code=None,
        task_id=None,
        task_status=None,
        phase=None,
        assigned_robot_id=None,
        cancellable=None,
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


__all__ = ["PatrolTaskResumeRepository"]
