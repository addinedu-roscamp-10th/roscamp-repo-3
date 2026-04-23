from copy import deepcopy

from server.ropi_main_service.ipc.uds_client import UnixDomainSocketCommandClient


FIXED_DELIVERY_PINKY_ID = "pinky2"
DEFAULT_FRAME_ID = "map"
ALLOWED_PHASE1_NAV_PHASES = {
    "DELIVERY_PICKUP",
    "DELIVERY_DESTINATION",
}


class GoalPoseNavigationService:
    def __init__(self, command_client=None):
        self.command_client = command_client or UnixDomainSocketCommandClient()

    def navigate(self, *, task_id, nav_phase, goal_pose, timeout_sec):
        self._validate_request(
            task_id=task_id,
            nav_phase=nav_phase,
            goal_pose=goal_pose,
            timeout_sec=timeout_sec,
        )

        normalized_goal_pose = self._normalize_goal_pose(goal_pose)
        goal = {
            "task_id": task_id,
            "nav_phase": nav_phase,
            "goal_pose": normalized_goal_pose,
            "timeout_sec": timeout_sec,
        }

        return self._get_command_client().send_command(
            "navigate_to_goal",
            {
                "pinky_id": FIXED_DELIVERY_PINKY_ID,
                "goal": goal,
            },
        )

    @staticmethod
    def _normalize_goal_pose(goal_pose):
        normalized_goal_pose = deepcopy(goal_pose)
        header = normalized_goal_pose.setdefault("header", {})
        header.setdefault("stamp", {"sec": 0, "nanosec": 0})

        if not str(header.get("frame_id", "")).strip():
            header["frame_id"] = DEFAULT_FRAME_ID

        return normalized_goal_pose

    @staticmethod
    def _validate_request(*, task_id, nav_phase, goal_pose, timeout_sec):
        if not str(task_id or "").strip():
            raise ValueError("task_id가 필요합니다.")

        if nav_phase not in ALLOWED_PHASE1_NAV_PHASES:
            raise ValueError(f"nav_phase가 1차 구현 범위를 벗어났습니다: {nav_phase}")

        if not isinstance(goal_pose, dict) or not goal_pose:
            raise ValueError("goal_pose가 필요합니다.")

        if int(timeout_sec) <= 0:
            raise ValueError("timeout_sec는 1 이상이어야 합니다.")

    def _get_command_client(self):
        if self.command_client is None:
            raise RuntimeError("ROS service command client가 아직 구성되지 않았습니다.")

        return self.command_client
