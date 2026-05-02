from server.ropi_main_service.persistence.repositories.caregiver_repository import CaregiverRepository


class CaregiverService:
    CANCELLABLE_TASK_STATUSES = {
        "WAITING",
        "WAITING_DISPATCH",
        "READY",
        "ASSIGNED",
        "RUNNING",
    }

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

    @staticmethod
    def _format_robot_board_data(rows):
        result = []

        for row in rows:
            status = row["robot_status"] or "UNKNOWN"

            if status in ("대기", "IDLE"):
                chip_type = "green"
            elif status in ("충전중", "CHARGING"):
                chip_type = "yellow"
            elif status in ("오류", "ERROR"):
                chip_type = "red"
            else:
                chip_type = "blue"

            result.append({
                "robot_id": row["robot_id"],
                "robot_role": row.get("robot_type_name") or "-",
                "connection_status": status,
                "battery_percent": row.get("battery_percent"),
                "current_location": row["current_location"] or "-",
                "current_task_id": row.get("current_task_id"),
                "last_seen_at": row.get("last_seen_at"),
                "robot_name": row["robot_id"],
                "status": status,
                "zone": row["current_location"] or "-",
                "battery": row.get("battery_percent") if row.get("battery_percent") is not None else "-",
                "current_task": row.get("current_task_phase") or row.get("current_task_status") or "-",
                "chip_type": chip_type,
            })

        return result

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
