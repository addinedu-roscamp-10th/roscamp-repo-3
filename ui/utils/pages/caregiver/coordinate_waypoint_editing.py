from dataclasses import dataclass

from ui.utils.pages.caregiver.coordinate_pose_editing import (
    coerce_pose2d,
    delete_index,
    move_index,
    replace_index,
)


@dataclass(frozen=True)
class WaypointEdit:
    waypoints: list
    selected_index: int | None


def append_patrol_waypoint(waypoints, world_pose):
    pose = coerce_pose2d(world_pose)
    if pose is None:
        return None
    next_waypoints = [
        dict(row) if isinstance(row, dict) else row for row in waypoints or []
    ]
    next_waypoints.append(pose)
    return WaypointEdit(
        waypoints=next_waypoints,
        selected_index=len(next_waypoints) - 1,
    )


def replace_selected_patrol_waypoint(waypoints, selected_index, *, x, y, yaw):
    try:
        next_pose = {
            "x": float(x),
            "y": float(y),
            "yaw": float(yaw),
        }
    except (TypeError, ValueError):
        return None

    next_waypoints = replace_index(
        waypoints,
        selected_index,
        next_pose,
    )
    if next_waypoints is None:
        return None
    return WaypointEdit(waypoints=next_waypoints, selected_index=int(selected_index))


def delete_selected_patrol_waypoint(waypoints, selected_index):
    deleted = delete_index(waypoints, selected_index)
    if deleted is None:
        return None
    next_waypoints, next_index = deleted
    return WaypointEdit(waypoints=next_waypoints, selected_index=next_index)


def move_selected_patrol_waypoint(waypoints, selected_index, offset):
    moved = move_index(waypoints, selected_index, offset)
    if moved is None:
        return None
    next_waypoints, next_index = moved
    return WaypointEdit(waypoints=next_waypoints, selected_index=next_index)


def move_selected_patrol_waypoint_to_world(waypoints, selected_index, world_pose):
    current_pose = selected_patrol_waypoint(waypoints, selected_index)
    if current_pose is None:
        return None

    pose = coerce_pose2d(
        world_pose,
        default_yaw=_float_or_default(current_pose.get("yaw")),
    )
    if pose is None:
        return None

    next_waypoints = replace_index(waypoints, selected_index, pose)
    if next_waypoints is None:
        return None
    return WaypointEdit(waypoints=next_waypoints, selected_index=int(selected_index))


def selected_patrol_waypoint(waypoints, selected_index):
    if not _valid_index(waypoints, selected_index):
        return None
    row = waypoints[int(selected_index)]
    return row if isinstance(row, dict) else None


def patrol_waypoint_buttons_state(waypoints, selected_index):
    has_selection = _valid_index(waypoints, selected_index)
    index = int(selected_index) if has_selection else -1
    return {
        "delete": has_selection,
        "up": has_selection and index > 0,
        "down": has_selection and index < len(waypoints or []) - 1,
    }


def patrol_waypoint_table_rows(waypoints):
    return [
        [
            str(row_index + 1),
            _waypoint_number_text(pose.get("x")),
            _waypoint_number_text(pose.get("y")),
            _waypoint_number_text(pose.get("yaw")),
        ]
        for row_index, pose in enumerate(waypoints or [])
        if isinstance(pose, dict)
    ]


def patrol_path_payload_poses(waypoints):
    return [
        {
            "x": _float_or_default(pose.get("x")),
            "y": _float_or_default(pose.get("y")),
            "yaw": _float_or_default(pose.get("yaw")),
        }
        for pose in waypoints or []
        if isinstance(pose, dict)
    ]


def _valid_index(rows, index):
    try:
        index = int(index)
    except (TypeError, ValueError):
        return False
    return 0 <= index < len(rows or [])


def _float_or_default(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _waypoint_number_text(value):
    return f"{_float_or_default(value):.4f}"


__all__ = [
    "WaypointEdit",
    "append_patrol_waypoint",
    "delete_selected_patrol_waypoint",
    "move_selected_patrol_waypoint",
    "move_selected_patrol_waypoint_to_world",
    "patrol_path_payload_poses",
    "patrol_waypoint_buttons_state",
    "patrol_waypoint_table_rows",
    "replace_selected_patrol_waypoint",
    "selected_patrol_waypoint",
]
