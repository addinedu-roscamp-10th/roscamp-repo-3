from server.ropi_main_service.persistence.async_connection import async_execute, async_execute_many
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
            self._build_params(
                robot_id=robot_id,
                robot_kind=robot_kind,
                runtime_state=runtime_state,
                active_task_id=active_task_id,
                battery_percent=battery_percent,
                pose_x=pose_x,
                pose_y=pose_y,
                pose_yaw=pose_yaw,
                frame_id=frame_id,
                fault_code=fault_code,
            ),
        )

    async def async_upsert_runtime_statuses(self, statuses):
        statuses = list(statuses or [])
        if not statuses:
            return 0

        return await async_execute_many(
            load_sql("robot_runtime_status/upsert_runtime_status.sql"),
            [
                self._build_params(
                    robot_id=status.get("robot_id"),
                    robot_kind=status.get("robot_kind"),
                    runtime_state=status.get("runtime_state"),
                    active_task_id=status.get("active_task_id"),
                    battery_percent=status.get("battery_percent"),
                    pose_x=status.get("pose_x"),
                    pose_y=status.get("pose_y"),
                    pose_yaw=status.get("pose_yaw"),
                    frame_id=status.get("frame_id"),
                    fault_code=status.get("fault_code"),
                )
                for status in statuses
            ],
        )

    @classmethod
    def _build_params(
        cls,
        *,
        robot_id,
        robot_kind,
        runtime_state,
        active_task_id,
        battery_percent,
        pose_x,
        pose_y,
        pose_yaw,
        frame_id,
        fault_code,
    ):
        return (
            cls._normalize_text(robot_id),
            cls._normalize_text(robot_kind),
            cls._normalize_text(runtime_state),
            active_task_id,
            battery_percent,
            pose_x,
            pose_y,
            pose_yaw,
            cls._normalize_optional_text(frame_id),
            cls._normalize_optional_text(fault_code),
        )

    @staticmethod
    def _normalize_text(value):
        return str(value or "").strip()

    @classmethod
    def _normalize_optional_text(cls, value):
        normalized = cls._normalize_text(value)
        return normalized or None


__all__ = ["RobotRuntimeStatusRepository"]
