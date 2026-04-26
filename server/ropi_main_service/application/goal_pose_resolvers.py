from copy import deepcopy


class FixedGoalPoseResolver:
    def __init__(self, goal_pose: dict | None):
        self.goal_pose = deepcopy(goal_pose) if goal_pose else None

    def __call__(self):
        if self.goal_pose is None:
            return None
        return deepcopy(self.goal_pose)


class MappedGoalPoseResolver:
    def __init__(self, goal_pose_by_key: dict | None):
        self.goal_pose_by_key = {
            str(key): deepcopy(goal_pose)
            for key, goal_pose in (goal_pose_by_key or {}).items()
            if isinstance(goal_pose, dict)
        }

    def __call__(self, key):
        goal_pose = self.goal_pose_by_key.get(str(key))
        if goal_pose is None:
            return None
        return deepcopy(goal_pose)


__all__ = ["FixedGoalPoseResolver", "MappedGoalPoseResolver"]
