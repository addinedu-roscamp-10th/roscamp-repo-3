from copy import deepcopy


FIXED_DELIVERY_PINKY_ID = "pinky2"
DEFAULT_FRAME_ID = "map"
ALLOWED_PHASE1_NAV_PHASES = {
    "DELIVERY_PICKUP",
    "DELIVERY_DESTINATION",
}


class GoalPoseNavigationService:
    def __init__(self, action_client=None):
        self.action_client = action_client

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

        return self._get_action_client().send_goal(
            action_name=self._build_action_name(FIXED_DELIVERY_PINKY_ID),
            goal=goal,
        )

    @staticmethod
    def _build_action_name(pinky_id: str) -> str:
        return f"/ropi/control/{pinky_id}/navigate_to_goal"

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

    def _get_action_client(self):
        if self.action_client is None:
            raise RuntimeError("Goal pose action client가 아직 구성되지 않았습니다.")

        return self.action_client
