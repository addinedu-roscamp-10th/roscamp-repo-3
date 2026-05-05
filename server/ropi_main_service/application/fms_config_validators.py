import re

from server.ropi_main_service.application.formatting import (
    bool_value,
    normalize_optional_text,
    optional_float,
)


WAYPOINT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
ALLOWED_WAYPOINT_TYPES = {
    "CORRIDOR",
    "ROOM_ENTRY",
    "DOCK_ENTRY",
    "SUPPLY_ENTRY",
    "WAIT_POINT",
    "INTERSECTION",
    "ELEVATOR_ENTRY",
    "OTHER",
}


def fms_waypoint_error(
    *,
    result_code,
    reason_code,
    result_message,
    waypoint=None,
):
    return {
        "result_code": result_code,
        "result_message": result_message,
        "reason_code": reason_code,
        "waypoint": waypoint,
    }


def normalize_waypoint_input(
    *,
    waypoint_id,
    expected_updated_at=None,
    display_name,
    waypoint_type,
    pose_x,
    pose_y,
    pose_yaw,
    frame_id,
    snap_group=None,
    is_enabled,
    active_frame_id,
):
    normalized_waypoint_id = normalize_optional_text(waypoint_id)
    if (
        not normalized_waypoint_id
        or len(normalized_waypoint_id) > 100
        or not WAYPOINT_ID_PATTERN.match(normalized_waypoint_id)
    ):
        return None, fms_waypoint_error(
            result_code="INVALID_REQUEST",
            reason_code="WAYPOINT_ID_INVALID",
            result_message="waypoint_id가 유효하지 않습니다.",
        )

    normalized_display_name = normalize_optional_text(display_name)
    if not normalized_display_name or len(normalized_display_name) > 100:
        return None, fms_waypoint_error(
            result_code="INVALID_REQUEST",
            reason_code="WAYPOINT_NAME_INVALID",
            result_message="display_name이 유효하지 않습니다.",
        )

    normalized_waypoint_type = normalize_optional_text(waypoint_type)
    if normalized_waypoint_type:
        normalized_waypoint_type = normalized_waypoint_type.upper()
    if normalized_waypoint_type not in ALLOWED_WAYPOINT_TYPES:
        return None, fms_waypoint_error(
            result_code="INVALID_REQUEST",
            reason_code="WAYPOINT_TYPE_INVALID",
            result_message="waypoint_type이 유효하지 않습니다.",
        )

    normalized_frame_id = normalize_optional_text(frame_id)
    if normalized_frame_id != active_frame_id:
        return None, fms_waypoint_error(
            result_code="INVALID_REQUEST",
            reason_code="FRAME_ID_MISMATCH",
            result_message="frame_id가 active map frame과 일치하지 않습니다.",
        )

    parsed_pose_x = optional_float(pose_x)
    parsed_pose_y = optional_float(pose_y)
    parsed_pose_yaw = optional_float(pose_yaw)
    if parsed_pose_x is None or parsed_pose_y is None or parsed_pose_yaw is None:
        return None, fms_waypoint_error(
            result_code="INVALID_REQUEST",
            reason_code="COORDINATE_OUT_OF_MAP_BOUNDS",
            result_message="좌표 값이 유효하지 않습니다.",
        )

    normalized_snap_group = normalize_optional_text(snap_group)
    if normalized_snap_group and len(normalized_snap_group) > 100:
        return None, fms_waypoint_error(
            result_code="INVALID_REQUEST",
            reason_code="SNAP_GROUP_INVALID",
            result_message="snap_group이 유효하지 않습니다.",
        )

    return {
        "waypoint_id": normalized_waypoint_id,
        "expected_updated_at": normalize_optional_text(expected_updated_at),
        "display_name": normalized_display_name,
        "waypoint_type": normalized_waypoint_type,
        "pose_x": parsed_pose_x,
        "pose_y": parsed_pose_y,
        "pose_yaw": parsed_pose_yaw,
        "frame_id": normalized_frame_id,
        "snap_group": normalized_snap_group,
        "is_enabled": bool_value(is_enabled),
    }, None


__all__ = [
    "ALLOWED_WAYPOINT_TYPES",
    "fms_waypoint_error",
    "normalize_waypoint_input",
]
