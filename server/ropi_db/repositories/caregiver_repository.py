from server.ropi_db.connection import fetch_all, fetch_one


class CaregiverRepository:
    def get_dashboard_summary(self):
        query = """
            SELECT
                (
                    SELECT COUNT(*)
                    FROM robot
                    WHERE robot_status_name IN ('대기', 'IDLE')
                ) AS available_robot_count,
                (
                    SELECT COUNT(*)
                    FROM robot_event
                    WHERE event_description LIKE '%대기%'
                ) AS waiting_job_count,
                (
                    SELECT COUNT(*)
                    FROM robot
                    WHERE robot_status_name IN ('작업중', 'RUNNING')
                ) AS running_job_count
        """
        return fetch_one(query)

    def get_robot_board(self):
        query = """
            SELECT
                r.robot_id,
                r.robot_type_name,
                r.ip_address AS current_location,
                r.robot_status_name AS robot_status,
                (
                    SELECT re.event_description
                    FROM robot_event re
                    ORDER BY re.event_at DESC
                    LIMIT 1
                ) AS current_task
            FROM robot r
            ORDER BY r.robot_id
        """
        return fetch_all(query)

    def get_timeline(self, limit=20):
        query = """
            SELECT
                DATE_FORMAT(re.event_at, '%%H:%%i:%%s') AS timeline_time,
                re.robot_event_id AS work_id,
                re.robot_event_type AS event_name,
                re.event_description AS detail
            FROM robot_event re
            ORDER BY re.event_at DESC
            LIMIT %s
        """
        return fetch_all(query, (limit,))

    def get_flow_board_events(self, limit=50):
        query = """
            SELECT
                re.robot_event_id,
                re.robot_event_type,
                re.event_description AS description,
                re.event_at AS event_datetime,
                'ROBOT' AS robot_id
            FROM robot_event re
            ORDER BY re.event_at DESC
            LIMIT %s
        """
        return fetch_all(query, (limit,))


__all__ = ["CaregiverRepository"]
