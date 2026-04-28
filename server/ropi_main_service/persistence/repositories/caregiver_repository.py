from server.ropi_main_service.persistence.connection import fetch_all, fetch_one


class CaregiverRepository:
    def get_dashboard_summary(self):
        query = """
            SELECT
                (
                    SELECT COUNT(*)
                    FROM robot_runtime_status
                    WHERE runtime_state IN ('IDLE', 'READY')
                ) AS available_robot_count,
                (
                    SELECT COUNT(*)
                    FROM task
                    WHERE task_status IN ('WAITING', 'WAITING_DISPATCH')
                ) AS waiting_job_count,
                (
                    SELECT COUNT(*)
                    FROM task
                    WHERE task_status = 'RUNNING'
                ) AS running_job_count
        """
        return fetch_one(query)

    def get_robot_board(self):
        query = """
            SELECT
                r.robot_id,
                r.robot_type_name,
                COALESCE(
                    CONCAT('x=', ROUND(rrs.pose_x, 2), ', y=', ROUND(rrs.pose_y, 2)),
                    r.ip_address
                ) AS current_location,
                COALESCE(rrs.runtime_state, r.robot_status_name) AS robot_status,
                rrs.battery_percent,
                t.task_id AS current_task_id,
                t.phase AS current_task_phase,
                t.task_status AS current_task_status
            FROM robot r
            LEFT JOIN robot_runtime_status rrs
              ON r.robot_id = rrs.robot_id
            LEFT JOIN task t
              ON rrs.active_task_id = t.task_id
            ORDER BY r.robot_id
        """
        return fetch_all(query)

    def get_timeline(self, limit=20):
        query = """
            SELECT
                DATE_FORMAT(tel.occurred_at, '%%H:%%i:%%s') AS timeline_time,
                tel.task_event_log_id AS work_id,
                tel.event_name,
                COALESCE(tel.message, tel.reason_code, tel.result_code, '') AS detail
            FROM task_event_log tel
            ORDER BY tel.occurred_at DESC
            LIMIT %s
        """
        return fetch_all(query, (limit,))

    def get_flow_board_events(self, limit=50):
        query = """
            SELECT
                tel.task_event_log_id AS event_id,
                t.task_status AS event_type,
                COALESCE(tel.message, tel.event_name) AS description,
                tel.occurred_at AS event_datetime,
                COALESCE(tel.robot_id, t.assigned_robot_id) AS robot_id
            FROM task_event_log tel
            LEFT JOIN task t
              ON tel.task_id = t.task_id
            ORDER BY tel.occurred_at DESC
            LIMIT %s
        """
        return fetch_all(query, (limit,))


__all__ = ["CaregiverRepository"]
