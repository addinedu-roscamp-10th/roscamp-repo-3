from dataclasses import dataclass


@dataclass
class GoalPoseEditorController:
    selected_row: dict | None = None
    selected_index: int | None = None
    mode: str | None = None
    dirty: bool = False
    syncing_form: bool = False

    def select(self, row_index, rows):
        row_index = int(row_index)
        row = rows[row_index]
        selected = dict(row if isinstance(row, dict) else {})
        self.selected_row = selected
        self.selected_index = row_index
        self.mode = "edit"
        self.dirty = False
        return selected

    def start_create(self, *, frame_id):
        self.selected_row = None
        self.selected_index = None
        self.mode = "create"
        self.dirty = False
        return {
            "goal_pose_id": "",
            "zone_id": None,
            "purpose": "DESTINATION",
            "pose_x": 0.0,
            "pose_y": 0.0,
            "pose_yaw": 0.0,
            "frame_id": frame_id,
            "is_enabled": True,
        }

    def mark_dirty(self, *, selected_edit_type):
        if self.syncing_form or selected_edit_type != "goal_pose":
            return False
        self.dirty = True
        return True

    def apply_saved_row(self, row):
        self.selected_row = dict(row if isinstance(row, dict) else {})
        self.mode = "edit"
        self.dirty = False

    def clear(self):
        self.selected_row = None
        self.selected_index = None
        self.mode = None
        self.dirty = False
        self.syncing_form = False


def build_goal_pose_update_payload(
    *,
    selected_goal_pose,
    goal_pose_id,
    zone_id,
    purpose,
    pose_x,
    pose_y,
    pose_yaw,
    frame_id,
    is_enabled,
):
    selected = selected_goal_pose if isinstance(selected_goal_pose, dict) else {}
    return {
        "goal_pose_id": str(goal_pose_id or "").strip(),
        "expected_updated_at": selected.get("updated_at"),
        "zone_id": zone_id,
        "purpose": str(purpose or "").strip(),
        "pose_x": _float_or_default(pose_x),
        "pose_y": _float_or_default(pose_y),
        "pose_yaw": _float_or_default(pose_yaw),
        "frame_id": str(frame_id or "").strip(),
        "is_enabled": bool(is_enabled),
    }


def build_goal_pose_save_payload(
    *,
    mode,
    selected_goal_pose,
    goal_pose_id,
    zone_id,
    purpose,
    pose_x,
    pose_y,
    pose_yaw,
    frame_id,
    is_enabled,
):
    payload = build_goal_pose_update_payload(
        selected_goal_pose=selected_goal_pose,
        goal_pose_id=goal_pose_id,
        zone_id=zone_id,
        purpose=purpose,
        pose_x=pose_x,
        pose_y=pose_y,
        pose_yaw=pose_yaw,
        frame_id=frame_id,
        is_enabled=is_enabled,
    )
    if str(mode or "").strip() == "create":
        payload.pop("expected_updated_at", None)
    return payload


def goal_pose_from_save_response(response):
    response = response if isinstance(response, dict) else {}
    goal_pose = response.get("goal_pose")
    return goal_pose if isinstance(goal_pose, dict) else None


def goal_pose_world_point_from_payload(payload):
    payload = payload if isinstance(payload, dict) else {}
    try:
        return {
            "x": float(payload.get("pose_x")),
            "y": float(payload.get("pose_y")),
        }
    except (TypeError, ValueError):
        return None


def _float_or_default(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


__all__ = [
    "GoalPoseEditorController",
    "build_goal_pose_save_payload",
    "build_goal_pose_update_payload",
    "goal_pose_from_save_response",
    "goal_pose_world_point_from_payload",
]
