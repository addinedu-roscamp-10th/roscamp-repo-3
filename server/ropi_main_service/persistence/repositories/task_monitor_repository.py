from server.ropi_main_service.persistence.async_connection import (
    async_fetch_all,
    async_transaction,
)
from server.ropi_main_service.persistence.connection import fetch_all, get_connection


WATERMARK_SQL = """
SELECT COALESCE(MAX(task_event_log_id), 0) AS last_event_seq
FROM task_event_log
"""

TASK_MONITOR_SELECT = """
SELECT
    t.task_id,
    t.task_type,
    t.task_status,
    t.result_code AS task_outcome,
    t.phase,
    t.assigned_robot_id,
    ptd.patrol_area_id,
    pa.patrol_area_name,
    ptd.patrol_area_revision,
    t.latest_reason_code,
    t.created_at AS requested_at,
    t.started_at,
    t.finished_at,
    t.updated_at,
    feedback.robot_data_log_id AS latest_feedback_id,
    feedback.data_type AS latest_feedback_type,
    feedback.payload_json AS latest_feedback_payload_json,
    feedback.pose_x AS latest_feedback_pose_x,
    feedback.pose_y AS latest_feedback_pose_y,
    feedback.pose_yaw AS latest_feedback_pose_yaw,
    NULL AS latest_feedback_frame_id,
    feedback.received_at AS latest_feedback_updated_at,
    rrs.robot_id AS latest_robot_id,
    rrs.runtime_state,
    rrs.battery_percent,
    rrs.pose_x,
    rrs.pose_y,
    rrs.pose_yaw,
    rrs.frame_id,
    rrs.last_seen_at,
    alert.task_event_log_id AS latest_alert_id,
    alert.payload_json AS latest_alert_payload_json,
    alert.occurred_at AS latest_alert_occurred_at
FROM task t
LEFT JOIN patrol_task_detail ptd
    ON ptd.task_id = t.task_id
LEFT JOIN patrol_area pa
    ON pa.patrol_area_id = ptd.patrol_area_id
LEFT JOIN robot_runtime_status rrs
    ON rrs.robot_id = t.assigned_robot_id
LEFT JOIN robot_data_log feedback
    ON feedback.robot_data_log_id = (
        SELECT rdl.robot_data_log_id
        FROM robot_data_log rdl
        WHERE rdl.task_id = t.task_id
        ORDER BY rdl.received_at DESC, rdl.robot_data_log_id DESC
        LIMIT 1
    )
LEFT JOIN task_event_log alert
    ON alert.task_event_log_id = (
        SELECT tel.task_event_log_id
        FROM task_event_log tel
        WHERE tel.task_id = t.task_id
          AND tel.event_name IN ('FALL_ALERT_CREATED', 'ALERT_CREATED')
        ORDER BY tel.occurred_at DESC, tel.task_event_log_id DESC
        LIMIT 1
    )
"""

TASK_MONITOR_ORDER = """
ORDER BY
    CASE
        WHEN t.task_status IN ('COMPLETED', 'CANCELLED', 'FAILED') THEN 1
        ELSE 0
    END,
    t.updated_at DESC,
    t.task_id DESC
LIMIT %s
"""

FALL_EVIDENCE_ALERT_SELECT = """
SELECT
    t.task_id,
    t.task_type,
    t.assigned_robot_id,
    tel.task_event_log_id AS alert_id,
    tel.robot_id,
    tel.payload_json,
    tel.occurred_at
FROM task t
LEFT JOIN task_event_log tel
    ON tel.task_id = t.task_id
   AND tel.event_name IN ('FALL_ALERT_CREATED', 'ALERT_CREATED')
WHERE t.task_id = %s
ORDER BY
    tel.occurred_at DESC,
    tel.task_event_log_id DESC
LIMIT %s
"""


class TaskMonitorRepository:
    def get_task_monitor_snapshot(self, *, task_types=None, statuses=None, limit=100):
        query, params = self._build_task_query(
            task_types=task_types,
            statuses=statuses,
            limit=limit,
        )
        conn = get_connection()
        try:
            conn.begin()
            with conn.cursor() as cursor:
                cursor.execute(WATERMARK_SQL)
                watermark_row = cursor.fetchone() or {}
                cursor.execute(query, params)
                rows = cursor.fetchall() or []
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        return {
            "last_event_seq": int(watermark_row.get("last_event_seq") or 0),
            "tasks": list(rows),
        }

    async def async_get_task_monitor_snapshot(
        self,
        *,
        task_types=None,
        statuses=None,
        limit=100,
    ):
        query, params = self._build_task_query(
            task_types=task_types,
            statuses=statuses,
            limit=limit,
        )
        async with async_transaction() as cursor:
            await cursor.execute(WATERMARK_SQL)
            watermark_row = await cursor.fetchone() or {}
            await cursor.execute(query, params)
            rows = await cursor.fetchall() or []

        return {
            "last_event_seq": int(watermark_row.get("last_event_seq") or 0),
            "tasks": list(rows),
        }

    def get_fall_evidence_alert_candidates(self, *, task_id, limit=20):
        return fetch_all(FALL_EVIDENCE_ALERT_SELECT, (int(task_id), int(limit)))

    async def async_get_fall_evidence_alert_candidates(self, *, task_id, limit=20):
        return await async_fetch_all(
            FALL_EVIDENCE_ALERT_SELECT,
            (int(task_id), int(limit)),
        )

    @classmethod
    def _build_task_query(cls, *, task_types=None, statuses=None, limit=100):
        where_clauses = []
        params = []

        normalized_task_types = cls._normalize_text_tuple(task_types)
        if normalized_task_types:
            where_clauses.append(
                "t.task_type IN ("
                + ", ".join(["%s"] * len(normalized_task_types))
                + ")"
            )
            params.extend(normalized_task_types)

        normalized_statuses = cls._normalize_text_tuple(statuses)
        if normalized_statuses:
            where_clauses.append(
                "t.task_status IN ("
                + ", ".join(["%s"] * len(normalized_statuses))
                + ")"
            )
            params.extend(normalized_statuses)

        query = TASK_MONITOR_SELECT
        if where_clauses:
            query += "\nWHERE " + "\n  AND ".join(where_clauses)
        query += "\n" + TASK_MONITOR_ORDER
        params.append(int(limit))
        return query, tuple(params)

    @staticmethod
    def _normalize_text_tuple(values):
        if values in (None, ""):
            return None
        if isinstance(values, str):
            values = [values]

        normalized = []
        for value in values or []:
            text = str(value or "").strip().upper()
            if text:
                normalized.append(text)
        return tuple(dict.fromkeys(normalized)) or None


__all__ = ["TaskMonitorRepository"]
