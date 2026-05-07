import json

from server.ropi_main_service.persistence.connection import get_connection
from server.ropi_main_service.persistence.sql_loader import load_sql


CONTROL_SERVICE_COMPONENT = "control_service"
GUIDE_PHASE_SNAPSHOT_EVENT = "GUIDE_PHASE_SNAPSHOT"
TERMINAL_GUIDE_STATUSES = {"COMPLETED", "CANCELLED", "FAILED"}
ALLOWED_GUIDE_PHASES = {
    "WAIT_TARGET_TRACKING",
    "READY_TO_START_GUIDANCE",
    "GUIDANCE_RUNNING",
    "WAIT_REIDENTIFY",
    "GUIDANCE_FINISHED",
    "GUIDANCE_CANCELLED",
    "GUIDANCE_FAILED",
}


class GuidePhaseSnapshotRepository:
    def __init__(self, *, connection_factory=None):
        self.connection_factory = connection_factory or get_connection

    def record_phase_snapshot(
        self,
        *,
        task_id,
        pinky_id,
        guide_phase,
        target_track_id=-1,
        reason_code="",
        seq=0,
        occurred_at=None,
    ):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._response(
                result_code="REJECTED",
                result_message="task_id를 확인할 수 없습니다.",
                reason_code="TASK_ID_INVALID",
            )

        conn = self.connection_factory()
        try:
            self._begin(conn)
            with conn.cursor() as cur:
                cur.execute(
                    load_sql("guide/lock_guide_task_for_lifecycle.sql"),
                    (numeric_task_id,),
                )
                row = cur.fetchone()
                guard = self._guard(row, task_id=numeric_task_id)
                if guard is not None:
                    conn.commit()
                    return guard

                plan = self._build_write_plan(
                    row=row,
                    task_id=numeric_task_id,
                    pinky_id=pinky_id,
                    guide_phase=guide_phase,
                    target_track_id=target_track_id,
                    reason_code=reason_code,
                    seq=seq,
                    occurred_at=occurred_at,
                )
                if plan["result_code"] != "ACCEPTED":
                    conn.commit()
                    return self._build_response(row=row, plan=plan)

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
                cur.execute(
                    load_sql("guide/insert_guide_task_lifecycle_event.sql"),
                    plan["event_params"],
                )
                conn.commit()
                return self._build_response(row=row, plan=plan)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _build_write_plan(
        self,
        *,
        row,
        task_id,
        pinky_id,
        guide_phase,
        target_track_id,
        reason_code,
        seq,
        occurred_at,
    ):
        guide_phase = self._normalize_token(guide_phase)
        if guide_phase not in ALLOWED_GUIDE_PHASES:
            return {
                "result_code": "REJECTED",
                "result_message": "지원하지 않는 안내 phase snapshot입니다.",
                "reason_code": "GUIDE_PHASE_INVALID",
                "task_status": row.get("task_status"),
                "phase": row.get("phase"),
                "guide_phase": row.get("guide_phase"),
                "target_track_id": row.get("target_track_id"),
                "state_changed": False,
            }

        target_track_id = self._normalize_target_track_id(target_track_id)
        task_status, phase, is_terminal = self._target_state(guide_phase)
        next_target_track_id = self._next_target_track_id(
            row=row,
            guide_phase=guide_phase,
            target_track_id=target_track_id,
        )
        resolved_reason_code = self._resolved_reason_code(
            guide_phase=guide_phase,
            reason_code=reason_code,
        )
        message = self._message_for_phase(guide_phase)
        current_status = str(row.get("task_status") or "").strip()
        current_phase = str(row.get("phase") or "").strip() or None
        state_changed = (
            current_status != task_status
            or current_phase != phase
            or row.get("guide_phase") != guide_phase
            or row.get("target_track_id") != next_target_track_id
        )
        payload = {
            "guide_phase": guide_phase,
            "target_track_id": target_track_id,
            "reason_code": self._normalize_token(reason_code),
            "seq": self._normalize_seq(seq),
            "occurred_at": occurred_at,
        }
        return {
            "result_code": "ACCEPTED",
            "result_message": message,
            "reason_code": resolved_reason_code,
            "task_status": task_status,
            "phase": phase,
            "guide_phase": guide_phase,
            "target_track_id": next_target_track_id,
            "state_changed": state_changed,
            "update_task_params": (
                task_status,
                phase,
                resolved_reason_code,
                "ACCEPTED",
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
            "history_params": (
                task_id,
                current_status,
                task_status,
                current_phase,
                phase,
                resolved_reason_code,
                message,
                CONTROL_SERVICE_COMPONENT,
            ),
            "event_params": (
                task_id,
                GUIDE_PHASE_SNAPSHOT_EVENT,
                "INFO" if guide_phase != "GUIDANCE_FAILED" else "WARNING",
                str(pinky_id or row.get("assigned_robot_id") or "").strip() or None,
                "ACCEPTED",
                resolved_reason_code,
                message,
                json.dumps(payload, ensure_ascii=False),
            ),
        }

    @staticmethod
    def _target_state(guide_phase):
        if guide_phase == "GUIDANCE_FINISHED":
            return "COMPLETED", "GUIDANCE_FINISHED", True
        if guide_phase == "GUIDANCE_CANCELLED":
            return "CANCELLED", "GUIDANCE_CANCELLED", True
        if guide_phase == "GUIDANCE_FAILED":
            return "FAILED", "GUIDANCE_FAILED", True
        return "RUNNING", guide_phase, False

    @staticmethod
    def _next_target_track_id(*, row, guide_phase, target_track_id):
        if target_track_id >= 0:
            return target_track_id
        if guide_phase == "WAIT_TARGET_TRACKING":
            return None
        return row.get("target_track_id")

    @staticmethod
    def _resolved_reason_code(*, guide_phase, reason_code):
        normalized = GuidePhaseSnapshotRepository._normalize_token(reason_code)
        if normalized:
            return normalized
        if guide_phase == "GUIDANCE_FINISHED":
            return "GUIDE_FINISHED"
        if guide_phase == "GUIDANCE_CANCELLED":
            return "GUIDE_CANCELLED"
        if guide_phase == "GUIDANCE_FAILED":
            return "GUIDE_FAILED"
        return "GUIDE_PHASE_SNAPSHOT"

    @staticmethod
    def _message_for_phase(guide_phase):
        if guide_phase == "GUIDANCE_FINISHED":
            return "안내가 완료되었습니다."
        if guide_phase == "GUIDANCE_CANCELLED":
            return "안내가 취소되었습니다."
        if guide_phase == "GUIDANCE_FAILED":
            return "안내가 실패했습니다."
        return "안내 runtime phase snapshot을 반영했습니다."

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
                result_code="IGNORED",
                result_message="이미 종료된 안내 task입니다.",
                reason_code="TASK_ALREADY_FINISHED",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                phase=row.get("phase"),
                assigned_robot_id=row.get("assigned_robot_id"),
                guide_phase=row.get("guide_phase"),
                target_track_id=row.get("target_track_id"),
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
            return -1

    @staticmethod
    def _normalize_seq(value):
        try:
            normalized = int(str(value).strip())
        except (TypeError, ValueError):
            return 0
        return max(0, normalized)

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
    ):
        return {
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


__all__ = ["GuidePhaseSnapshotRepository"]
