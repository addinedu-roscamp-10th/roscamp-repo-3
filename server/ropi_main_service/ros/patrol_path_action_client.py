from server.ropi_main_service.ros.action_client_base import BaseRclpyActionClient


class RclpyPatrolPathActionClient(BaseRclpyActionClient):
    @staticmethod
    def _load_default_action_type():
        try:
            from ropi_interface.action import ExecutePatrolPath
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "ropi_interface.action.ExecutePatrolPath 를 불러올 수 없습니다. "
                "ROS workspace를 build/source 했는지 확인하세요."
            ) from exc

        return ExecutePatrolPath

    @classmethod
    def _build_goal_message(cls, action_type, goal):
        goal_msg = action_type.Goal()
        goal_msg.task_id = str(goal.get("task_id") or "")
        goal_msg.timeout_sec = int(goal.get("timeout_sec") or 0)
        goal_msg.path = cls._build_path_message(goal.get("path") or {})
        return goal_msg

    @classmethod
    def _build_path_message(cls, path_payload):
        try:
            from geometry_msgs.msg import PoseStamped
            from nav_msgs.msg import Path
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "nav_msgs.msg.Path 또는 geometry_msgs.msg.PoseStamped 를 불러올 수 없습니다. "
                "ROS workspace를 build/source 했는지 확인하세요."
            ) from exc

        path_msg = Path()
        cls._assign_attributes(path_msg.header, path_payload.get("header") or {})
        path_msg.poses = []
        for pose_payload in path_payload.get("poses") or []:
            pose_msg = PoseStamped()
            cls._assign_attributes(pose_msg, pose_payload)
            path_msg.poses.append(pose_msg)
        return path_msg


__all__ = ["RclpyPatrolPathActionClient"]
