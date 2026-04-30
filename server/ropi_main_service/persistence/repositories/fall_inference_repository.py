import json
from datetime import datetime, timezone

from server.ropi_main_service.application.patrol_states import (
    PATROL_STATUS_WAITING_FALL_RESPONSE,
    PHASE_WAIT_FALL_RESPONSE,
    is_waiting_fall_response,
)
from server.ropi_main_service.persistence.async_connection import (
    async_execute,
    async_fetch_one,
    async_transaction,
)
from server.ropi_main_service.persistence.sql_loader import load_sql


FALL_DETECTED_REASON = "FALL_DETECTED"
FALL_RESPONSE_MESSAGE = "낙상 대응 대기 상태로 전환했습니다."


class FallInferenceRepository:
    async def async_get_active_patrol_task_for_robot(self, robot_id):
        normalized_robot_id = self._normalize_optional_text(robot_id)
        if normalized_robot_id is None:
            return None

        return await async_fetch_one(
            load_sql("fall_inference/get_active_patrol_task_for_robot.sql"),
            (normalized_robot_id,),
        )

    async def async_record_ai_inference(
        self,
        *,
        task_id,
        robot_id,
        stream_name,
        result,
        inference_type="FALL_DETECTION",
    ):
        result = result if isinstance(result, dict) else {}
        rowcount = await async_execute(
            load_sql("fall_inference/insert_ai_inference_log.sql"),
            (
                self._parse_optional_task_id(task_id),
                self._normalize_optional_text(robot_id),
                self._normalize_required_text(stream_name),
                self._normalize_optional_text(result.get("frame_id")),
                self._normalize_required_text(inference_type),
                self._optional_float(result.get("confidence")),
                json.dumps(result, ensure_ascii=False),
                self._mysql_datetime(result.get("frame_ts")),
            ),
        )
        return {
            "result_code": "RECORDED",
            "rowcount": rowcount,
        }

    async def async_record_fall_alert_started(
        self,
        *,
        task_id,
        robot_id,
        trigger_result,
        command_response,
    ):
        numeric_task_id = self._parse_optional_task_id(task_id)
        if numeric_task_id is None:
            return {
                "result_code": "REJECTED",
                "reason_code": "TASK_ID_INVALID",
                "result_message": "순찰 task_id가 올바르지 않습니다.",
            }

        async with async_transaction() as cur:
            await cur.execute(
                load_sql("fall_inference/lock_patrol_task_for_fall_alert.sql"),
                (numeric_task_id,),
            )
            row = await cur.fetchone()
            if not row:
                return {
                    "result_code": "REJECTED",
                    "reason_code": "TASK_NOT_FOUND",
                    "result_message": "순찰 task를 찾을 수 없습니다.",
                    "task_id": numeric_task_id,
                }
            if self._is_waiting_fall_response(row):
                return {
                    "result_code": "IGNORED",
                    "reason_code": "FALL_ALERT_ALREADY_ACTIVE",
                    "result_message": "이미 낙상 대응 대기 상태입니다.",
                    "task_id": row.get("task_id"),
                    "task_status": row.get("task_status"),
                    "phase": row.get("phase"),
                    "assigned_robot_id": row.get("assigned_robot_id"),
                    "cancellable": True,
                }

            await cur.execute(
                load_sql("fall_inference/update_task_wait_fall_response.sql"),
                (
                    FALL_DETECTED_REASON,
                    FALL_RESPONSE_MESSAGE,
                    row["task_id"],
                ),
            )
            await cur.execute(
                load_sql("fall_inference/update_patrol_detail_wait_fall_response.sql"),
                (
                    PATROL_STATUS_WAITING_FALL_RESPONSE,
                    row["task_id"],
                ),
            )
            await cur.execute(
                load_sql("fall_inference/insert_fall_alert_history.sql"),
                (
                    row["task_id"],
                    row.get("task_status"),
                    row.get("task_status"),
                    row.get("phase"),
                    FALL_DETECTED_REASON,
                    FALL_RESPONSE_MESSAGE,
                ),
            )
            await cur.execute(
                load_sql("fall_inference/insert_fall_alert_event.sql"),
                (
                    row["task_id"],
                    self._normalize_optional_text(robot_id) or row.get("assigned_robot_id"),
                    "ACCEPTED",
                    FALL_DETECTED_REASON,
                    FALL_RESPONSE_MESSAGE,
                    self._build_event_payload(
                        trigger_result=trigger_result,
                        command_response=command_response,
                    ),
                ),
            )

        return {
            "result_code": "ACCEPTED",
            "result_message": FALL_RESPONSE_MESSAGE,
            "task_id": row.get("task_id"),
            "task_status": row.get("task_status"),
            "phase": PHASE_WAIT_FALL_RESPONSE,
            "assigned_robot_id": row.get("assigned_robot_id"),
            "latest_reason_code": FALL_DETECTED_REASON,
            "cancellable": True,
        }

    @classmethod
    def _build_event_payload(cls, *, trigger_result, command_response):
        return json.dumps(
            {
                "trigger_result": trigger_result or {},
                "command_response": command_response or {},
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _is_waiting_fall_response(row):
        return is_waiting_fall_response(
            phase=row.get("phase"),
            patrol_status=row.get("patrol_status"),
        )

    @staticmethod
    def _parse_optional_task_id(value):
        raw = str(value or "").strip()
        if raw.isdigit():
            return int(raw)
        return None

    @classmethod
    def _normalize_required_text(cls, value):
        normalized = cls._normalize_optional_text(value)
        if normalized is None:
            raise ValueError("required text value is empty.")
        return normalized

    @staticmethod
    def _normalize_optional_text(value):
        normalized = str(value or "").strip()
        return normalized or None

    @staticmethod
    def _optional_float(value):
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _mysql_datetime(cls, value):
        if isinstance(value, datetime):
            dt = value
        else:
            raw = str(value or "").strip()
            if not raw:
                dt = datetime.now(timezone.utc)
            else:
                try:
                    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                except ValueError:
                    dt = datetime.now(timezone.utc)

        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


__all__ = [
    "FALL_DETECTED_REASON",
    "FALL_RESPONSE_MESSAGE",
    "FallInferenceRepository",
]
