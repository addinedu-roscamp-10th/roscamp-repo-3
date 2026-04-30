import asyncio
import json
from datetime import date, datetime, timezone

from server.ropi_main_service.persistence.repositories.task_monitor_repository import (
    TaskMonitorRepository,
)


ACTIVE_TASK_STATUSES = (
    "WAITING",
    "WAITING_DISPATCH",
    "READY",
    "ASSIGNED",
    "RUNNING",
    "CANCEL_REQUESTED",
    "CANCELLING",
    "PREEMPTING",
)
TERMINAL_TASK_STATUSES = (
    "COMPLETED",
    "CANCELLED",
    "FAILED",
)
CANCELLABLE_TASK_STATUSES = {
    "WAITING",
    "WAITING_DISPATCH",
    "READY",
    "ASSIGNED",
    "RUNNING",
}


class TaskMonitorService:
    DEFAULT_LIMIT = 100
    MAX_LIMIT = 200
    DEFAULT_RECENT_TERMINAL_LIMIT = 20
    MAX_RECENT_TERMINAL_LIMIT = 100

    def __init__(self, repository=None):
        self.repository = repository or TaskMonitorRepository()

    def get_task_monitor_snapshot(
        self,
        *,
        consumer_id=None,
        task_types=None,
        statuses=None,
        include_recent_terminal=True,
        recent_terminal_limit=DEFAULT_RECENT_TERMINAL_LIMIT,
        limit=DEFAULT_LIMIT,
    ):
        query = self._build_query(
            task_types=task_types,
            statuses=statuses,
            include_recent_terminal=include_recent_terminal,
            recent_terminal_limit=recent_terminal_limit,
            limit=limit,
        )
        snapshot = self.repository.get_task_monitor_snapshot(
            task_types=query["task_types"],
            statuses=query["statuses"],
            limit=query["limit"],
        )
        return self._format_snapshot(
            snapshot=snapshot,
            consumer_id=consumer_id,
            recent_terminal_limit=query["recent_terminal_limit"],
            cap_terminal_tasks=query["cap_terminal_tasks"],
        )

    async def async_get_task_monitor_snapshot(
        self,
        *,
        consumer_id=None,
        task_types=None,
        statuses=None,
        include_recent_terminal=True,
        recent_terminal_limit=DEFAULT_RECENT_TERMINAL_LIMIT,
        limit=DEFAULT_LIMIT,
    ):
        query = self._build_query(
            task_types=task_types,
            statuses=statuses,
            include_recent_terminal=include_recent_terminal,
            recent_terminal_limit=recent_terminal_limit,
            limit=limit,
        )
        async_get_snapshot = getattr(
            self.repository,
            "async_get_task_monitor_snapshot",
            None,
        )
        if async_get_snapshot is not None:
            snapshot = await async_get_snapshot(
                task_types=query["task_types"],
                statuses=query["statuses"],
                limit=query["limit"],
            )
        else:
            snapshot = await asyncio.to_thread(
                self.repository.get_task_monitor_snapshot,
                task_types=query["task_types"],
                statuses=query["statuses"],
                limit=query["limit"],
            )
        return self._format_snapshot(
            snapshot=snapshot,
            consumer_id=consumer_id,
            recent_terminal_limit=query["recent_terminal_limit"],
            cap_terminal_tasks=query["cap_terminal_tasks"],
        )

    @classmethod
    def _build_query(
        cls,
        *,
        task_types,
        statuses,
        include_recent_terminal,
        recent_terminal_limit,
        limit,
    ):
        explicit_statuses = statuses is not None
        normalized_statuses = cls._normalize_text_tuple(statuses)
        normalized_terminal_limit = cls._bounded_int(
            recent_terminal_limit,
            default=cls.DEFAULT_RECENT_TERMINAL_LIMIT,
            minimum=0,
            maximum=cls.MAX_RECENT_TERMINAL_LIMIT,
        )

        if not normalized_statuses:
            normalized_statuses = ACTIVE_TASK_STATUSES
            if include_recent_terminal and normalized_terminal_limit > 0:
                normalized_statuses = normalized_statuses + TERMINAL_TASK_STATUSES

        return {
            "task_types": cls._normalize_text_tuple(task_types),
            "statuses": normalized_statuses,
            "limit": cls._bounded_int(
                limit,
                default=cls.DEFAULT_LIMIT,
                minimum=1,
                maximum=cls.MAX_LIMIT,
            ),
            "recent_terminal_limit": normalized_terminal_limit,
            "cap_terminal_tasks": not explicit_statuses,
        }

    @classmethod
    def _format_snapshot(
        cls,
        *,
        snapshot,
        consumer_id,
        recent_terminal_limit,
        cap_terminal_tasks,
    ):
        snapshot = snapshot if isinstance(snapshot, dict) else {}
        terminal_count = 0
        tasks = []

        for row in snapshot.get("tasks") or []:
            task = cls._format_task(row if isinstance(row, dict) else {})
            if cap_terminal_tasks and task["task_status"] in TERMINAL_TASK_STATUSES:
                if terminal_count >= recent_terminal_limit:
                    continue
                terminal_count += 1
            tasks.append(task)

        return {
            "result_code": "ACCEPTED",
            "result_message": None,
            "consumer_id": str(consumer_id or "").strip() or None,
            "last_event_seq": cls._optional_int(snapshot.get("last_event_seq")) or 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tasks": tasks,
        }

    @classmethod
    def _format_task(cls, row):
        task_status = row.get("task_status") or "UNKNOWN"
        task = {
            "task_id": row.get("task_id"),
            "task_type": row.get("task_type") or "UNKNOWN",
            "task_status": task_status,
            "task_outcome": row.get("task_outcome") or row.get("result_code"),
            "phase": row.get("phase"),
            "assigned_robot_id": row.get("assigned_robot_id"),
            "patrol_area_id": row.get("patrol_area_id"),
            "patrol_area_name": row.get("patrol_area_name"),
            "patrol_area_revision": row.get("patrol_area_revision"),
            "cancellable": task_status in CANCELLABLE_TASK_STATUSES,
            "latest_reason_code": row.get("latest_reason_code"),
            "requested_at": cls._isoformat(row.get("requested_at") or row.get("created_at")),
            "started_at": cls._isoformat(row.get("started_at")),
            "finished_at": cls._isoformat(row.get("finished_at")),
            "updated_at": cls._isoformat(row.get("updated_at")),
            "latest_feedback": cls._format_latest_feedback(row),
            "latest_robot": cls._format_latest_robot(row),
            "latest_alert": cls._format_latest_alert(row),
        }
        return task

    @classmethod
    def _format_latest_feedback(cls, row):
        nested = row.get("latest_feedback")
        if isinstance(nested, dict):
            return {
                "feedback_summary": nested.get("feedback_summary") or nested.get("summary"),
                "pose": nested.get("pose"),
                "updated_at": cls._isoformat(nested.get("updated_at")),
            }

        payload = cls._json_object(row.get("latest_feedback_payload_json"))
        if not payload:
            return None

        pose = payload.get("pose")
        if pose is None:
            pose = cls._pose_from_row(
                row,
                x_key="latest_feedback_pose_x",
                y_key="latest_feedback_pose_y",
                yaw_key="latest_feedback_pose_yaw",
                frame_key="latest_feedback_frame_id",
            )

        return {
            "feedback_summary": cls._build_feedback_summary(
                payload=payload,
                feedback_type=row.get("latest_feedback_type"),
            ),
            "pose": pose,
            "updated_at": cls._isoformat(row.get("latest_feedback_updated_at")),
        }

    @classmethod
    def _format_latest_robot(cls, row):
        nested = row.get("latest_robot")
        if isinstance(nested, dict):
            return {
                "robot_id": nested.get("robot_id"),
                "runtime_state": nested.get("runtime_state"),
                "battery_percent": nested.get("battery_percent"),
                "pose": nested.get("pose"),
                "last_seen_at": cls._isoformat(nested.get("last_seen_at")),
            }

        robot_id = row.get("latest_robot_id") or row.get("assigned_robot_id")
        if not robot_id:
            return None

        return {
            "robot_id": robot_id,
            "runtime_state": row.get("runtime_state"),
            "battery_percent": row.get("battery_percent"),
            "pose": cls._pose_from_row(
                row,
                x_key="pose_x",
                y_key="pose_y",
                yaw_key="pose_yaw",
                frame_key="frame_id",
            ),
            "last_seen_at": cls._isoformat(row.get("last_seen_at")),
        }

    @classmethod
    def _format_latest_alert(cls, row):
        nested = row.get("latest_alert")
        if isinstance(nested, dict):
            alert = dict(nested)
        else:
            payload = cls._json_object(row.get("latest_alert_payload_json"))
            if not payload:
                return None
            alert = dict(payload.get("trigger_result") or payload)
            if "command_response" not in alert and payload.get("command_response"):
                alert["command_response"] = payload.get("command_response")

        alert.setdefault("alert_id", row.get("latest_alert_id"))
        alert.setdefault("occurred_at", cls._isoformat(row.get("latest_alert_occurred_at")))
        return alert

    @classmethod
    def _build_feedback_summary(cls, *, payload, feedback_type):
        if payload.get("feedback_summary"):
            return payload.get("feedback_summary")
        if payload.get("summary"):
            return payload.get("summary")

        nested_payload = (
            payload.get("payload")
            if isinstance(payload.get("payload"), dict)
            else payload
        )
        normalized_type = str(feedback_type or payload.get("feedback_type") or "").strip()
        if normalized_type == "NAVIGATION_FEEDBACK":
            nav_status = nested_payload.get("nav_status") or "NAVIGATION"
            distance = nested_payload.get("distance_remaining_m")
            if distance is None:
                return str(nav_status)
            return f"{nav_status} / 남은 거리 {float(distance):.2f}m"

        if normalized_type == "MANIPULATION_FEEDBACK":
            processed_quantity = nested_payload.get("processed_quantity")
            if processed_quantity is None:
                return "로봇팔 작업 중"
            return f"처리 수량 {processed_quantity}"

        return normalized_type or "ACTION_FEEDBACK"

    @staticmethod
    def _json_object(value):
        if isinstance(value, dict):
            return value
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        if isinstance(value, str):
            try:
                loaded = json.loads(value)
            except json.JSONDecodeError:
                return {}
            return loaded if isinstance(loaded, dict) else {}
        return {}

    @classmethod
    def _pose_from_row(cls, row, *, x_key, y_key, yaw_key, frame_key=None):
        x = row.get(x_key)
        y = row.get(y_key)
        yaw = row.get(yaw_key)
        frame_id = row.get(frame_key) if frame_key else None
        if x is None and y is None and yaw is None and frame_id is None:
            return None

        pose = {
            "x": x,
            "y": y,
            "yaw": yaw,
        }
        if frame_id is not None:
            pose["frame_id"] = frame_id
        return pose

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

    @staticmethod
    def _bounded_int(value, *, default, minimum, maximum):
        try:
            numeric_value = int(value)
        except (TypeError, ValueError):
            numeric_value = default
        return max(minimum, min(maximum, numeric_value))

    @staticmethod
    def _optional_int(value):
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _isoformat(value):
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)


__all__ = [
    "ACTIVE_TASK_STATUSES",
    "TERMINAL_TASK_STATUSES",
    "TaskMonitorService",
]
