import json
from datetime import datetime, time, timedelta

from server.ropi_main_service.persistence.repositories.caregiver_repository import CaregiverRepository


class CaregiverService:
    CANCELLABLE_TASK_STATUSES = {
        "WAITING",
        "WAITING_DISPATCH",
        "READY",
        "ASSIGNED",
        "RUNNING",
    }
    DELIVERY_COMPOSITION = [
        {"label": "Delivery Mobile Robot", "value": "pinky2"},
        {"label": "Pickup Arm Robot", "value": "jetcobot1"},
        {"label": "Destination Arm Robot", "value": "jetcobot2"},
        {"label": "ROS adapter arm_id", "value": "arm1 / arm2"},
    ]

    def __init__(self, repository=None):
        self.repo = repository or CaregiverRepository()

    def get_dashboard_summary(self):
        row = self.repo.get_dashboard_summary()
        return self._format_dashboard_summary(row)

    async def async_get_dashboard_summary(self):
        row = await self.repo.async_get_dashboard_summary()
        return self._format_dashboard_summary(row)

    @staticmethod
    def _format_dashboard_summary(row):
        return {
            "available_robot_count": row["available_robot_count"] if row else 0,
            "total_robot_count": row.get("total_robot_count", 0) if row else 0,
            "waiting_job_count": row["waiting_job_count"] if row else 0,
            "running_job_count": row["running_job_count"] if row else 0,
            "warning_error_count": row.get("warning_error_count", 0) if row else 0,
        }

    def get_robot_board_data(self):
        rows = self.repo.get_robot_board()
        return self._format_robot_board_data(rows)

    async def async_get_robot_board_data(self):
        rows = await self.repo.async_get_robot_board()
        return self._format_robot_board_data(rows)

    def get_robot_status_bundle(self):
        return self._format_robot_status_bundle(self.get_robot_board_data())

    async def async_get_robot_status_bundle(self):
        return self._format_robot_status_bundle(await self.async_get_robot_board_data())

    def get_alert_log_bundle(
        self,
        *,
        period="LAST_24_HOURS",
        severity=None,
        source_component=None,
        task_id=None,
        robot_id=None,
        event_type=None,
        limit=100,
    ):
        rows = self.repo.get_alert_logs(
            period_start=self._alert_log_period_start(period),
            severity=self._clean_filter(severity),
            source_component=self._clean_filter(source_component),
            task_id=self._clean_filter(task_id),
            robot_id=self._clean_filter(robot_id),
            event_type=self._clean_filter(event_type),
            limit=self._alert_log_limit(limit),
        )
        return self._format_alert_log_bundle(rows)

    async def async_get_alert_log_bundle(
        self,
        *,
        period="LAST_24_HOURS",
        severity=None,
        source_component=None,
        task_id=None,
        robot_id=None,
        event_type=None,
        limit=100,
    ):
        rows = await self.repo.async_get_alert_logs(
            period_start=self._alert_log_period_start(period),
            severity=self._clean_filter(severity),
            source_component=self._clean_filter(source_component),
            task_id=self._clean_filter(task_id),
            robot_id=self._clean_filter(robot_id),
            event_type=self._clean_filter(event_type),
            limit=self._alert_log_limit(limit),
        )
        return self._format_alert_log_bundle(rows)

    @staticmethod
    def _format_robot_board_data(rows):
        result = []

        for row in rows:
            status = row["robot_status"] or "UNKNOWN"
            connection_status = CaregiverService._connection_status(row, status)

            if connection_status == "ONLINE":
                chip_type = "green"
            elif connection_status == "DEGRADED":
                chip_type = "yellow"
            else:
                chip_type = "red"

            current_phase = row.get("current_task_phase") or row.get("current_task_status")

            result.append({
                "robot_id": row["robot_id"],
                "display_name": CaregiverService._display_name(row),
                "robot_type": CaregiverService._robot_type(row),
                "scenario_role": CaregiverService._scenario_role(row),
                "robot_role": row.get("robot_type_name") or "-",
                "connection_status": connection_status,
                "runtime_state": status,
                "battery_percent": row.get("battery_percent"),
                "current_location": row.get("current_location") or "-",
                "current_task_id": row.get("current_task_id"),
                "current_phase": current_phase,
                "last_seen_at": row.get("last_seen_at"),
                "fault_code": row.get("fault_code"),
                "robot_name": row["robot_id"],
                "status": connection_status,
                "zone": row.get("current_location") or "-",
                "battery": row.get("battery_percent") if row.get("battery_percent") is not None else "-",
                "current_task": current_phase or "-",
                "chip_type": chip_type,
            })

        return result

    @classmethod
    def _format_robot_status_bundle(cls, robots):
        robots = list(robots or [])
        summary = {
            "total_robot_count": len(robots),
            "online_robot_count": sum(
                1 for robot in robots if robot.get("connection_status") == "ONLINE"
            ),
            "offline_robot_count": sum(
                1 for robot in robots if robot.get("connection_status") == "OFFLINE"
            ),
            "caution_robot_count": sum(
                1 for robot in robots if robot.get("connection_status") == "DEGRADED"
            ),
        }
        return {
            "summary": summary,
            "robots": robots,
            "delivery_composition": list(cls.DELIVERY_COMPOSITION),
        }

    @classmethod
    def _format_alert_log_bundle(cls, rows):
        events = [cls._format_alert_log_event(row) for row in rows or []]
        summary = {
            "total_event_count": len(events),
            "info_count": sum(1 for event in events if event["severity"] == "INFO"),
            "warning_count": sum(
                1 for event in events if event["severity"] == "WARNING"
            ),
            "error_count": sum(1 for event in events if event["severity"] == "ERROR"),
            "critical_count": sum(
                1 for event in events if event["severity"] == "CRITICAL"
            ),
        }
        return {
            "summary": summary,
            "events": events,
        }

    @classmethod
    def _format_alert_log_event(cls, row):
        return {
            "event_id": row.get("event_id"),
            "occurred_at": cls._isoformat(row.get("occurred_at")),
            "severity": row.get("severity") or "INFO",
            "source_component": row.get("source_component") or "-",
            "task_id": row.get("task_id"),
            "robot_id": row.get("robot_id"),
            "event_type": row.get("event_type") or "-",
            "result_code": row.get("result_code"),
            "reason_code": row.get("reason_code"),
            "message": row.get("message") or "",
            "payload": cls._json_object(row.get("payload_json")),
        }

    @staticmethod
    def _alert_log_period_start(period):
        normalized = str(period or "LAST_24_HOURS").strip().upper()
        now = datetime.now()
        if normalized == "ALL":
            return None
        if normalized == "LAST_1_HOUR":
            return now - timedelta(hours=1)
        if normalized == "TODAY":
            return datetime.combine(now.date(), time.min)
        return now - timedelta(hours=24)

    @staticmethod
    def _alert_log_limit(limit):
        try:
            value = int(limit)
        except (TypeError, ValueError):
            value = 100
        return max(1, min(value, 200))

    @staticmethod
    def _clean_filter(value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _json_object(value):
        if isinstance(value, dict):
            return value
        if not value:
            return {}
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _isoformat(value):
        if value is None:
            return ""
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _connection_status(row, runtime_state):
        if not row.get("last_seen_at"):
            return "OFFLINE"
        if row.get("fault_code"):
            return "DEGRADED"
        normalized = str(runtime_state or "").upper()
        if normalized in {"ERROR", "FAULT", "DEGRADED"}:
            return "DEGRADED"
        if normalized in {"OFFLINE", "DISCONNECTED"}:
            return "OFFLINE"
        return "ONLINE"

    @staticmethod
    def _display_name(row):
        robot_id = row.get("robot_id")
        if robot_id == "pinky1":
            return "안내 로봇"
        if robot_id == "pinky2":
            return "운반 로봇"
        if robot_id == "pinky3":
            return "순찰 로봇"
        if robot_id == "jetcobot1":
            return "픽업 로봇팔"
        if robot_id == "jetcobot2":
            return "목적지 로봇팔"
        return row.get("robot_manager_name") or robot_id or "-"

    @staticmethod
    def _robot_type(row):
        robot_id = str(row.get("robot_id") or "").lower()
        robot_type_name = str(row.get("robot_type_name") or "").lower()
        if robot_id.startswith("jetcobot") or "jetcobot" in robot_type_name:
            return "ARM"
        return "MOBILE"

    @staticmethod
    def _scenario_role(row):
        robot_id = row.get("robot_id")
        if robot_id == "pinky1":
            return "GUIDE"
        if robot_id == "pinky2":
            return "DELIVERY"
        if robot_id == "pinky3":
            return "PATROL"
        if robot_id == "jetcobot1":
            return "PICKUP_ARM"
        if robot_id == "jetcobot2":
            return "DESTINATION_ARM"
        return "-"

    def get_timeline_data(self):
        rows = self.repo.get_timeline(limit=30)
        return self._format_timeline_data(rows)

    async def async_get_timeline_data(self):
        rows = await self.repo.async_get_timeline(limit=30)
        return self._format_timeline_data(rows)

    @staticmethod
    def _format_timeline_data(rows):
        return [
            [
                row["timeline_time"] or "",
                str(row["work_id"] or ""),
                row["event_name"] or "",
                row["detail"] or "",
            ]
            for row in rows
        ]

    def get_flow_board_data(self):
        rows = self.repo.get_flow_board_events(limit=50)
        return self._format_flow_board_data(rows)

    async def async_get_flow_board_data(self):
        rows = await self.repo.async_get_flow_board_events(limit=50)
        return self._format_flow_board_data(rows)

    @staticmethod
    def _format_flow_board_data(rows):
        flow_data = {
            "READY": [],
            "ASSIGNED": [],
            "RUNNING": [],
            "DONE": [],
        }

        for row in rows:
            task = CaregiverService._format_flow_task(row)

            if task["task_status"] in ("WAITING", "WAITING_DISPATCH"):
                flow_data["READY"].append(task)
            elif task["task_status"] in ("READY", "ASSIGNED"):
                flow_data["ASSIGNED"].append(task)
            elif task["task_status"] in ("RUNNING", "CANCEL_REQUESTED"):
                flow_data["RUNNING"].append(task)
            else:
                flow_data["DONE"].append(task)

        return flow_data

    @staticmethod
    def _format_flow_task(row):
        task_id = row.get("task_id")
        task_status = row.get("task_status") or row.get("event_type") or "UNKNOWN"
        robot_id = row.get("robot_id") or "-"
        description = row.get("description") or "-"

        return {
            "event_id": row.get("event_id"),
            "task_id": task_id,
            "task_type": row.get("task_type") or "UNKNOWN",
            "task_status": task_status,
            "phase": row.get("phase"),
            "robot_id": robot_id,
            "description": description,
            "display_text": f"#{task_id or row.get('event_id') or '-'} {description} / {robot_id}",
            "cancellable": task_status in CaregiverService.CANCELLABLE_TASK_STATUSES,
        }


__all__ = ["CaregiverService"]
