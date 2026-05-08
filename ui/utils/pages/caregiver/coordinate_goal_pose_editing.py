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
    "build_goal_pose_save_payload",
    "build_goal_pose_update_payload",
    "goal_pose_from_save_response",
    "goal_pose_world_point_from_payload",
]
