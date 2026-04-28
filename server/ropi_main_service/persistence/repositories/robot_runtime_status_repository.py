from server.ropi_main_service.persistence.async_connection import async_execute
from server.ropi_main_service.persistence.sql_loader import load_sql


class RobotRuntimeStatusRepository:
    async def async_upsert_runtime_status(
        self,
        *,
        robot_id,
        robot_kind,
        runtime_state,
        active_task_id=None,
        battery_percent=None,
        pose_x=None,
        pose_y=None,
        pose_yaw=None,
        frame_id=None,
        fault_code=None,
    ):
        await async_execute(
            load_sql("robot_runtime_status/upsert_runtime_status.sql"),
            (
                self._normalize_text(robot_id),
                self._normalize_text(robot_kind),
                self._normalize_text(runtime_state),
                active_task_id,
                battery_percent,
                pose_x,
                pose_y,
                pose_yaw,
                self._normalize_optional_text(frame_id),
                self._normalize_optional_text(fault_code),
            ),
        )

    @staticmethod
    def _normalize_text(value):
        return str(value or "").strip()

    @classmethod
    def _normalize_optional_text(cls, value):
        normalized = cls._normalize_text(value)
        return normalized or None


__all__ = ["RobotRuntimeStatusRepository"]
