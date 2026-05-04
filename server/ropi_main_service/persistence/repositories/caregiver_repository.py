from server.ropi_main_service.persistence.async_connection import async_fetch_all, async_fetch_one
from server.ropi_main_service.persistence.connection import fetch_all, fetch_one
from server.ropi_main_service.persistence.sql_loader import load_sql


class CaregiverRepository:
    def get_dashboard_summary(self):
        return fetch_one(load_sql("caregiver/dashboard_summary.sql"))

    async def async_get_dashboard_summary(self):
        return await async_fetch_one(load_sql("caregiver/dashboard_summary.sql"))

    def get_robot_board(self):
        return fetch_all(load_sql("caregiver/robot_board.sql"))

    async def async_get_robot_board(self):
        return await async_fetch_all(load_sql("caregiver/robot_board.sql"))

    def get_timeline(self, limit=20):
        return fetch_all(load_sql("caregiver/timeline.sql"), (limit,))

    async def async_get_timeline(self, limit=20):
        return await async_fetch_all(load_sql("caregiver/timeline.sql"), (limit,))

    def get_flow_board_events(self, limit=50):
        return fetch_all(load_sql("caregiver/flow_board_events.sql"), (limit,))

    async def async_get_flow_board_events(self, limit=50):
        return await async_fetch_all(load_sql("caregiver/flow_board_events.sql"), (limit,))

    def get_alert_logs(
        self,
        *,
        period_start=None,
        severity=None,
        source_component=None,
        task_id=None,
        robot_id=None,
        event_type=None,
        limit=100,
    ):
        return fetch_all(
            load_sql("caregiver/alert_logs.sql"),
            self._alert_log_params(
                period_start=period_start,
                severity=severity,
                source_component=source_component,
                task_id=task_id,
                robot_id=robot_id,
                event_type=event_type,
                limit=limit,
            ),
        )

    async def async_get_alert_logs(
        self,
        *,
        period_start=None,
        severity=None,
        source_component=None,
        task_id=None,
        robot_id=None,
        event_type=None,
        limit=100,
    ):
        return await async_fetch_all(
            load_sql("caregiver/alert_logs.sql"),
            self._alert_log_params(
                period_start=period_start,
                severity=severity,
                source_component=source_component,
                task_id=task_id,
                robot_id=robot_id,
                event_type=event_type,
                limit=limit,
            ),
        )

    @staticmethod
    def _alert_log_params(
        *,
        period_start,
        severity,
        source_component,
        task_id,
        robot_id,
        event_type,
        limit,
    ):
        return (
            period_start,
            period_start,
            severity,
            severity,
            source_component,
            source_component,
            task_id,
            task_id,
            robot_id,
            robot_id,
            event_type,
            event_type,
            limit,
        )


__all__ = ["CaregiverRepository"]
