from __future__ import annotations

import math


def _optional_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _yaw_from_quaternion(orientation) -> float:
    orientation = orientation if isinstance(orientation, dict) else {}
    try:
        x = float(orientation.get("x", 0.0))
        y = float(orientation.get("y", 0.0))
        z = float(orientation.get("z", 0.0))
        w = float(orientation.get("w", 1.0))
    except (TypeError, ValueError):
        return 0.0

    siny_cosp = 2.0 * ((w * z) + (x * y))
    cosy_cosp = 1.0 - (2.0 * ((y * y) + (z * z)))
    return math.atan2(siny_cosp, cosy_cosp)


def robot_id_from_action_name(action_name):
    parts = str(action_name or "").strip("/").split("/")
    if len(parts) >= 3 and parts[0] == "ropi" and parts[1] in {"control", "arm"}:
        return parts[2] or None
    return None


def normalize_stream_pose(
    pose, *, fallback_map_id=None, fallback_frame_id=None, updated_at=None
):
    if not isinstance(pose, dict):
        return None

    if "x" in pose and "y" in pose:
        x_value = pose.get("x")
        y_value = pose.get("y")
        yaw_value = pose.get("yaw")
        frame_id = pose.get("frame_id")
        map_id = pose.get("map_id")
    else:
        stamped_pose = pose.get("pose")
        if not isinstance(stamped_pose, dict):
            return None
        position = stamped_pose.get("position")
        if not isinstance(position, dict):
            return None
        x_value = position.get("x")
        y_value = position.get("y")
        yaw_value = _yaw_from_quaternion(stamped_pose.get("orientation"))
        header = pose.get("header") if isinstance(pose.get("header"), dict) else {}
        frame_id = header.get("frame_id") or pose.get("frame_id")
        map_id = pose.get("map_id")

    x = _optional_float(x_value)
    y = _optional_float(y_value)
    if x is None or y is None:
        return None

    return {
        "map_id": str(map_id or fallback_map_id or "").strip(),
        "frame_id": str(frame_id or fallback_frame_id or "map"),
        "x": x,
        "y": y,
        "yaw": _optional_float(yaw_value, default=0.0),
        "updated_at": updated_at or pose.get("updated_at"),
    }


__all__ = ["normalize_stream_pose", "robot_id_from_action_name"]
