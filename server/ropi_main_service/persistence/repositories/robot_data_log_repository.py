import json

from server.ropi_main_service.persistence.async_connection import async_execute
from server.ropi_main_service.persistence.connection import get_connection
from server.ropi_main_service.persistence.sql_loader import load_sql


class RobotDataLogRepository:
    def insert_feedback_sample(
        self,
        *,
        robot_id,
        task_id,
        data_type,
        pose_x=None,
        pose_y=None,
        pose_yaw=None,
        battery_percent=None,
        payload=None,
    ):
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    load_sql("robot_data_log/insert_feedback_sample.sql"),
                    self._build_params(
                        robot_id=robot_id,
                        task_id=task_id,
                        data_type=data_type,
                        pose_x=pose_x,
                        pose_y=pose_y,
                        pose_yaw=pose_yaw,
                        battery_percent=battery_percent,
                        payload=payload,
                    ),
                )
        finally:
            conn.close()

    async def async_insert_feedback_sample(
        self,
        *,
        robot_id,
        task_id,
        data_type,
        pose_x=None,
        pose_y=None,
        pose_yaw=None,
        battery_percent=None,
        payload=None,
    ):
        await async_execute(
            load_sql("robot_data_log/insert_feedback_sample.sql"),
            self._build_params(
                robot_id=robot_id,
                task_id=task_id,
                data_type=data_type,
                pose_x=pose_x,
                pose_y=pose_y,
                pose_yaw=pose_yaw,
                battery_percent=battery_percent,
                payload=payload,
            ),
        )

    @staticmethod
    def _build_params(
        *,
        robot_id,
        task_id,
        data_type,
        pose_x,
        pose_y,
        pose_yaw,
        battery_percent,
        payload,
    ):
        return (
            robot_id,
            task_id,
            data_type,
            pose_x,
            pose_y,
            pose_yaw,
            battery_percent,
            json.dumps(payload or {}, ensure_ascii=False),
        )


__all__ = ["RobotDataLogRepository"]
