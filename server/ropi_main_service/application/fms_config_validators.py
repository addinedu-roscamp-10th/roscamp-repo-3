import re

from server.ropi_main_service.application.formatting import (
    bool_value,
    normalize_optional_text,
    optional_float,
    optional_int,
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


def fms_edge_error(
    *,
    result_code,
    reason_code,
    result_message,
    edge=None,
):
    return {
        "result_code": result_code,
        "result_message": result_message,
        "reason_code": reason_code,
        "edge": edge,
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


def normalize_edge_input(
    *,
    edge_id,
    expected_updated_at=None,
    from_waypoint_id,
    to_waypoint_id,
    is_bidirectional,
    is_enabled,
    traversal_cost=None,
    priority=None,
):
    normalized_edge_id = normalize_optional_text(edge_id)
    if (
        not normalized_edge_id
        or len(normalized_edge_id) > 100
        or not WAYPOINT_ID_PATTERN.match(normalized_edge_id)
    ):
        return None, fms_edge_error(
            result_code="INVALID_REQUEST",
            reason_code="EDGE_ID_INVALID",
            result_message="edge_id가 유효하지 않습니다.",
        )

    normalized_from_waypoint_id = _normalize_waypoint_ref(from_waypoint_id)
    normalized_to_waypoint_id = _normalize_waypoint_ref(to_waypoint_id)
    if not normalized_from_waypoint_id or not normalized_to_waypoint_id:
        return None, fms_edge_error(
            result_code="INVALID_REQUEST",
            reason_code="EDGE_WAYPOINT_ID_INVALID",
            result_message="edge endpoint waypoint_id가 유효하지 않습니다.",
        )
    if normalized_from_waypoint_id == normalized_to_waypoint_id:
        return None, fms_edge_error(
            result_code="INVALID_REQUEST",
            reason_code="EDGE_ENDPOINT_DUPLICATED",
            result_message="from_waypoint_id와 to_waypoint_id는 달라야 합니다.",
        )

    parsed_traversal_cost = optional_float(traversal_cost)
    if traversal_cost not in (None, "") and parsed_traversal_cost is None:
        return None, fms_edge_error(
            result_code="INVALID_REQUEST",
            reason_code="EDGE_COST_INVALID",
            result_message="traversal_cost가 유효하지 않습니다.",
        )

    parsed_priority = optional_int(priority)
    if priority not in (None, "") and parsed_priority is None:
        return None, fms_edge_error(
            result_code="INVALID_REQUEST",
            reason_code="EDGE_PRIORITY_INVALID",
            result_message="priority가 유효하지 않습니다.",
        )

    return {
        "edge_id": normalized_edge_id,
        "expected_updated_at": normalize_optional_text(expected_updated_at),
        "from_waypoint_id": normalized_from_waypoint_id,
        "to_waypoint_id": normalized_to_waypoint_id,
        "is_bidirectional": bool_value(is_bidirectional),
        "traversal_cost": parsed_traversal_cost,
        "priority": parsed_priority,
        "is_enabled": bool_value(is_enabled),
    }, None


def _normalize_waypoint_ref(value):
    normalized = normalize_optional_text(value)
    if (
        not normalized
        or len(normalized) > 100
        or not WAYPOINT_ID_PATTERN.match(normalized)
    ):
        return None
    return normalized


__all__ = [
    "ALLOWED_WAYPOINT_TYPES",
    "fms_edge_error",
    "fms_waypoint_error",
    "normalize_edge_input",
    "normalize_waypoint_input",
]
