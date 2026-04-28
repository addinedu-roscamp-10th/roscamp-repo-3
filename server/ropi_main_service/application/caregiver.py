from server.ropi_main_service.persistence.repositories.caregiver_repository import CaregiverRepository


class CaregiverService:
    def __init__(self):
        self.repo = CaregiverRepository()

    def get_dashboard_summary(self):
        row = self.repo.get_dashboard_summary()

        return {
            "available_robot_count": row["available_robot_count"] if row else 0,
            "waiting_job_count": row["waiting_job_count"] if row else 0,
            "running_job_count": row["running_job_count"] if row else 0,
        }

    def get_robot_board_data(self):
        rows = self.repo.get_robot_board()
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

        flow_data = {
            "READY": [],
            "ASSIGNED": [],
            "RUNNING": [],
            "DONE": [],
        }

        for row in rows:
            event_id = row["event_id"]
            robot_id = row["robot_id"] or "-"
            desc = row["description"] or "-"
            event_type = row["event_type"]

            item_text = f"#{event_id} {desc} / {robot_id}"

            if event_type in ("WAITING", "WAITING_DISPATCH"):
                flow_data["READY"].append(item_text)
            elif event_type in ("READY", "ASSIGNED"):
                flow_data["ASSIGNED"].append(item_text)
            elif event_type == "RUNNING":
                flow_data["RUNNING"].append(item_text)
            else:
                flow_data["DONE"].append(item_text)

        return flow_data


__all__ = ["CaregiverService"]
