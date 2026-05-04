from server.ropi_main_service.application.goal_pose import normalize_goal_pose_spec
from server.ropi_main_service.persistence.async_connection import async_fetch_one
from server.ropi_main_service.persistence.connection import fetch_one
from server.ropi_main_service.persistence.sql_loader import load_sql


GUIDE_DRIVING_ALLOWED_PHASES = {
    "WAIT_TARGET_TRACKING",
    "WAIT_REIDENTIFY",
    "GUIDANCE_RUNNING",
}
TERMINAL_GUIDE_STATUSES = {"COMPLETED", "CANCELLED", "FAILED"}


class GuideTaskNavigationRepository:
    def __init__(self, *, fetch_one_func=None, async_fetch_one_func=None):
        self.fetch_one_func = fetch_one_func or fetch_one
        self.async_fetch_one_func = async_fetch_one_func or async_fetch_one

    def get_guide_driving_context(self, *, task_id):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._response(
                result_code="REJECTED",
                result_message="task_id를 확인할 수 없습니다.",
                reason_code="TASK_ID_INVALID",
            )

        row = self.fetch_one_func(
            load_sql("guide/find_guide_driving_context.sql"),
            (numeric_task_id,),
        )
        return self._build_context_response(row, task_id=numeric_task_id)

    async def async_get_guide_driving_context(self, *, task_id):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._response(
                result_code="REJECTED",
                result_message="task_id를 확인할 수 없습니다.",
                reason_code="TASK_ID_INVALID",
            )

        row = await self.async_fetch_one_func(
            load_sql("guide/find_guide_driving_context.sql"),
            (numeric_task_id,),
        )
        return self._build_context_response(row, task_id=numeric_task_id)

    @classmethod
    def _build_context_response(cls, row, *, task_id):
        guard = cls._guard(row, task_id=task_id)
        if guard is not None:
            return guard

        goal_pose_id = str(row.get("destination_goal_pose_id") or "").strip()
        try:
            goal_pose = normalize_goal_pose_spec(
                {
                    "x": row.get("pose_x"),
                    "y": row.get("pose_y"),
                    "yaw": row.get("pose_yaw"),
                    "frame_id": row.get("frame_id") or "map",
                },
                env_name=f"guide_destination_goal_pose[{goal_pose_id}]",
            )
        except Exception as exc:
            return cls._response(
                result_code="REJECTED",
                result_message=f"안내 목적지 좌표가 올바르지 않습니다: {exc}",
                reason_code="GUIDE_DESTINATION_POSE_INVALID",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                phase=row.get("phase"),
                assigned_robot_id=row.get("assigned_robot_id"),
                destination_id=goal_pose_id,
            )

        return cls._response(
            result_code="ACCEPTED",
            result_message="안내 목적지 좌표를 확인했습니다.",
            task_id=row.get("task_id"),
            task_status=row.get("task_status"),
            phase=row.get("phase"),
            assigned_robot_id=row.get("assigned_robot_id"),
            destination_id=goal_pose_id,
            goal_pose=goal_pose,
        )

    @classmethod
    def _guard(cls, row, *, task_id):
        if not row:
            return cls._response(
                result_code="REJECTED",
                result_message="안내 task를 찾을 수 없습니다.",
                reason_code="TASK_NOT_FOUND",
                task_id=task_id,
            )
        if str(row.get("task_type") or "").strip().upper() != "GUIDE":
            return cls._response(
                result_code="REJECTED",
                result_message="안내 task가 아닙니다.",
                reason_code="TASK_TYPE_MISMATCH",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                phase=row.get("phase"),
                assigned_robot_id=row.get("assigned_robot_id"),
            )
        if str(row.get("task_status") or "").strip().upper() in TERMINAL_GUIDE_STATUSES:
            return cls._response(
                result_code="REJECTED",
                result_message="이미 종료된 안내 task입니다.",
                reason_code="TASK_ALREADY_FINISHED",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                phase=row.get("phase"),
                assigned_robot_id=row.get("assigned_robot_id"),
            )
        phase = str(row.get("phase") or "").strip().upper()
        if phase not in GUIDE_DRIVING_ALLOWED_PHASES:
            return cls._response(
                result_code="REJECTED",
                result_message="안내 주행을 시작할 수 없는 상태입니다.",
                reason_code="GUIDE_STATE_MISMATCH",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                phase=row.get("phase"),
                assigned_robot_id=row.get("assigned_robot_id"),
            )
        if not str(row.get("destination_goal_pose_id") or "").strip():
            return cls._response(
                result_code="REJECTED",
                result_message="안내 목적지 좌표가 설정되어 있지 않습니다.",
                reason_code="GUIDE_DESTINATION_NOT_CONFIGURED",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                phase=row.get("phase"),
                assigned_robot_id=row.get("assigned_robot_id"),
            )
        return None

    @staticmethod
    def _parse_task_id(value):
        raw = str(value or "").strip()
        if not raw.isdigit():
            return None
        return int(raw)

    @staticmethod
    def _response(
        *,
        result_code,
        result_message=None,
        reason_code=None,
        task_id=None,
        task_status=None,
        phase=None,
        assigned_robot_id=None,
        destination_id=None,
        goal_pose=None,
    ):
        response = {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "task_id": task_id,
            "task_type": "GUIDE",
            "task_status": task_status,
            "phase": phase,
            "assigned_robot_id": assigned_robot_id,
            "destination_id": destination_id,
        }
        if goal_pose is not None:
            response["goal_pose"] = goal_pose
        return response


__all__ = ["GuideTaskNavigationRepository"]
