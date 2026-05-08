import re

from server.ropi_main_service.application.coordinate_config_formatters import (
    bool_value,
    json_object,
    normalize_optional_text,
    optional_float,
    optional_int,
)


ALLOWED_OPERATION_ZONE_TYPES = {
    "ROOM",
    "ENTRANCE",
    "CORRIDOR",
    "NURSE_STATION",
    "STAFF_STATION",
    "CAREGIVER_ROOM",
    "SUPPLY_STATION",
    "DOCK",
    "RESTRICTED",
    "OTHER",
}
ALLOWED_GOAL_POSE_PURPOSES = {"PICKUP", "DESTINATION", "DOCK"}
ZONE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")


def operation_zone_error(*, result_code, reason_code, result_message):
    return {
        "result_code": result_code,
        "result_message": result_message,
        "reason_code": reason_code,
        "operation_zone": None,
    }


def goal_pose_error(*, result_code, reason_code, result_message):
    return {
        "result_code": result_code,
        "result_message": result_message,
        "reason_code": reason_code,
        "goal_pose": None,
    }


def patrol_area_error(*, result_code, reason_code, result_message):
    return {
        "result_code": result_code,
        "result_message": result_message,
        "reason_code": reason_code,
        "patrol_area": None,
    }


def normalize_operation_zone_input(
    *,
    zone_id,
    zone_name,
    zone_type,
    is_enabled,
):
    normalized_zone_id = normalize_optional_text(zone_id)
    if (
        not normalized_zone_id
        or len(normalized_zone_id) > 100
        or not ZONE_ID_PATTERN.match(normalized_zone_id)
    ):
        return None, operation_zone_error(
            result_code="INVALID_REQUEST",
            reason_code="ZONE_ID_INVALID",
            result_message="zone_id가 유효하지 않습니다.",
        )

    normalized_zone_name = normalize_optional_text(zone_name)
    if not normalized_zone_name or len(normalized_zone_name) > 100:
        return None, operation_zone_error(
            result_code="INVALID_REQUEST",
            reason_code="ZONE_NAME_INVALID",
            result_message="zone_name이 유효하지 않습니다.",
        )

    normalized_zone_type = normalize_optional_text(zone_type)
    if normalized_zone_type:
        normalized_zone_type = normalized_zone_type.upper()
    if (
        not normalized_zone_type
        or len(normalized_zone_type) > 50
        or normalized_zone_type not in ALLOWED_OPERATION_ZONE_TYPES
    ):
        return None, operation_zone_error(
            result_code="INVALID_REQUEST",
            reason_code="ZONE_TYPE_INVALID",
            result_message="zone_type이 유효하지 않습니다.",
        )

    return {
        "zone_id": normalized_zone_id,
        "zone_name": normalized_zone_name,
        "zone_type": normalized_zone_type,
        "is_enabled": bool_value(is_enabled),
    }, None


def normalize_operation_zone_boundary_input(
    *,
    zone_id,
    expected_revision,
    boundary_json,
    active_frame_id,
):
    normalized_zone_id = normalize_optional_text(zone_id)
    if (
        not normalized_zone_id
        or len(normalized_zone_id) > 100
        or not ZONE_ID_PATTERN.match(normalized_zone_id)
    ):
        return None, operation_zone_error(
            result_code="INVALID_REQUEST",
            reason_code="ZONE_ID_INVALID",
            result_message="zone_id가 유효하지 않습니다.",
        )

    revision = optional_int(expected_revision)
    if revision is None or revision < 1:
        return None, operation_zone_error(
            result_code="INVALID_REQUEST",
            reason_code="ZONE_REVISION_CONFLICT",
            result_message="expected_revision이 유효하지 않습니다.",
        )

    if boundary_json is None:
        return {
            "zone_id": normalized_zone_id,
            "expected_revision": revision,
            "boundary_json": None,
        }, None

    boundary = json_object(boundary_json)
    if not boundary:
        return None, operation_zone_error(
            result_code="INVALID_REQUEST",
            reason_code="ZONE_BOUNDARY_INVALID",
            result_message="boundary_json shape이 유효하지 않습니다.",
        )

    boundary_type = normalize_optional_text(boundary.get("type"))
    if boundary_type:
        boundary_type = boundary_type.upper()
    if boundary_type != "POLYGON":
        return None, operation_zone_error(
            result_code="INVALID_REQUEST",
            reason_code="ZONE_BOUNDARY_INVALID",
            result_message="boundary_json.type은 POLYGON이어야 합니다.",
        )

    header = boundary.get("header")
    if not isinstance(header, dict):
        return None, operation_zone_error(
            result_code="INVALID_REQUEST",
            reason_code="ZONE_BOUNDARY_INVALID",
            result_message="boundary_json.header가 유효하지 않습니다.",
        )

    frame_id = normalize_optional_text(header.get("frame_id"))
    if not frame_id:
        return None, operation_zone_error(
            result_code="INVALID_REQUEST",
            reason_code="ZONE_BOUNDARY_INVALID",
            result_message="boundary_json.header.frame_id가 유효하지 않습니다.",
        )
    if frame_id != active_frame_id:
        return None, operation_zone_error(
            result_code="INVALID_REQUEST",
            reason_code="FRAME_ID_MISMATCH",
            result_message="구역 boundary frame_id가 선택 맵 frame과 일치하지 않습니다.",
        )

    raw_vertices = boundary.get("vertices")
    if not isinstance(raw_vertices, list):
        return None, operation_zone_error(
            result_code="INVALID_REQUEST",
            reason_code="ZONE_BOUNDARY_INVALID",
            result_message="boundary_json.vertices가 유효하지 않습니다.",
        )
    if len(raw_vertices) < 3:
        return None, operation_zone_error(
            result_code="INVALID_REQUEST",
            reason_code="ZONE_BOUNDARY_TOO_SHORT",
            result_message="구역 boundary는 최소 세 개 이상의 꼭짓점이 필요합니다.",
        )

    vertices = []
    for vertex in raw_vertices:
        if not isinstance(vertex, dict):
            return None, operation_zone_error(
                result_code="INVALID_REQUEST",
                reason_code="ZONE_BOUNDARY_INVALID",
                result_message="구역 boundary 꼭짓점 shape이 유효하지 않습니다.",
            )
        x = optional_float(vertex.get("x"))
        y = optional_float(vertex.get("y"))
        if x is None or y is None:
            return None, operation_zone_error(
                result_code="INVALID_REQUEST",
                reason_code="ZONE_BOUNDARY_INVALID",
                result_message="구역 boundary 좌표가 유효하지 않습니다.",
            )
        vertices.append({"x": x, "y": y})

    return {
        "zone_id": normalized_zone_id,
        "expected_revision": revision,
        "boundary_json": {
            "type": "POLYGON",
            "header": {"frame_id": frame_id},
            "vertices": vertices,
        },
    }, None


def normalize_goal_pose_input(
    *,
    goal_pose_id,
    expected_updated_at,
    zone_id,
    purpose,
    pose_x,
    pose_y,
    pose_yaw,
    frame_id,
    is_enabled,
    active_frame_id,
):
    normalized_goal_pose_id = normalize_optional_text(goal_pose_id)
    if (
        not normalized_goal_pose_id
        or len(normalized_goal_pose_id) > 100
        or not ZONE_ID_PATTERN.match(normalized_goal_pose_id)
    ):
        return None, goal_pose_error(
            result_code="INVALID_REQUEST",
            reason_code="GOAL_POSE_ID_INVALID",
            result_message="goal_pose_id가 유효하지 않습니다.",
        )

    normalized_purpose = normalize_optional_text(purpose)
    if normalized_purpose:
        normalized_purpose = normalized_purpose.upper()
    if normalized_purpose not in ALLOWED_GOAL_POSE_PURPOSES:
        return None, goal_pose_error(
            result_code="INVALID_REQUEST",
            reason_code="GOAL_POSE_PURPOSE_INVALID",
            result_message="purpose가 유효하지 않습니다.",
        )

    normalized_frame_id = normalize_optional_text(frame_id)
    if normalized_frame_id != active_frame_id:
        return None, goal_pose_error(
            result_code="INVALID_REQUEST",
            reason_code="FRAME_ID_MISMATCH",
            result_message="frame_id가 선택 맵 frame과 일치하지 않습니다.",
        )

    parsed_pose_x = optional_float(pose_x)
    parsed_pose_y = optional_float(pose_y)
    parsed_pose_yaw = optional_float(pose_yaw)
    if parsed_pose_x is None or parsed_pose_y is None or parsed_pose_yaw is None:
        return None, goal_pose_error(
            result_code="INVALID_REQUEST",
            reason_code="COORDINATE_OUT_OF_MAP_BOUNDS",
            result_message="좌표 값이 유효하지 않습니다.",
        )

    normalized_zone_id = normalize_optional_text(zone_id)
    if normalized_zone_id and (
        len(normalized_zone_id) > 100
        or not ZONE_ID_PATTERN.match(normalized_zone_id)
    ):
        return None, goal_pose_error(
            result_code="INVALID_REQUEST",
            reason_code="ZONE_ID_INVALID",
            result_message="zone_id가 유효하지 않습니다.",
        )

    return {
        "goal_pose_id": normalized_goal_pose_id,
        "expected_updated_at": normalize_optional_text(expected_updated_at),
        "zone_id": normalized_zone_id,
        "purpose": normalized_purpose,
        "pose_x": parsed_pose_x,
        "pose_y": parsed_pose_y,
        "pose_yaw": parsed_pose_yaw,
        "frame_id": normalized_frame_id,
        "is_enabled": bool_value(is_enabled),
    }, None


def normalize_patrol_area_path_input(
    *,
    patrol_area_id,
    expected_revision,
    path_json,
    active_frame_id,
):
    normalized_patrol_area_id, error = _normalize_patrol_area_id(patrol_area_id)
    if error:
        return None, error

    revision = optional_int(expected_revision)
    if revision is None or revision < 1:
        return None, patrol_area_error(
            result_code="INVALID_REQUEST",
            reason_code="PATROL_AREA_REVISION_CONFLICT",
            result_message="expected_revision이 유효하지 않습니다.",
        )

    path, error = _normalize_patrol_path(
        path_json,
        active_frame_id=active_frame_id,
    )
    if error:
        return None, error

    return {
        "patrol_area_id": normalized_patrol_area_id,
        "expected_revision": revision,
        "path_json": path,
    }, None


def normalize_patrol_area_input(
    *,
    patrol_area_id,
    patrol_area_name,
    path_json,
    active_frame_id,
    is_enabled,
    expected_revision=None,
):
    normalized_patrol_area_id, error = _normalize_patrol_area_id(patrol_area_id)
    if error:
        return None, error

    normalized_patrol_area_name = normalize_optional_text(patrol_area_name)
    if not normalized_patrol_area_name or len(normalized_patrol_area_name) > 100:
        return None, patrol_area_error(
            result_code="INVALID_REQUEST",
            reason_code="PATROL_AREA_NAME_INVALID",
            result_message="patrol_area_name이 유효하지 않습니다.",
        )

    path, error = _normalize_patrol_path(
        path_json,
        active_frame_id=active_frame_id,
    )
    if error:
        return None, error

    normalized = {
        "patrol_area_id": normalized_patrol_area_id,
        "patrol_area_name": normalized_patrol_area_name,
        "path_json": path,
        "is_enabled": bool_value(is_enabled),
    }
    if expected_revision is not None:
        revision = optional_int(expected_revision)
        if revision is None or revision < 1:
            return None, patrol_area_error(
                result_code="INVALID_REQUEST",
                reason_code="PATROL_AREA_REVISION_CONFLICT",
                result_message="expected_revision이 유효하지 않습니다.",
            )
        normalized["expected_revision"] = revision
    return normalized, None


def _normalize_patrol_area_id(patrol_area_id):
    normalized_patrol_area_id = normalize_optional_text(patrol_area_id)
    if (
        not normalized_patrol_area_id
        or len(normalized_patrol_area_id) > 100
        or not ZONE_ID_PATTERN.match(normalized_patrol_area_id)
    ):
        return None, patrol_area_error(
            result_code="INVALID_REQUEST",
            reason_code="PATROL_AREA_ID_INVALID",
            result_message="patrol_area_id가 유효하지 않습니다.",
        )
    return normalized_patrol_area_id, None


def _normalize_patrol_path(path_json, *, active_frame_id):
    path = json_object(path_json)
    header = path.get("header")
    if not isinstance(header, dict):
        return None, patrol_area_error(
            result_code="INVALID_REQUEST",
            reason_code="PATROL_PATH_INVALID",
            result_message="path_json.header가 유효하지 않습니다.",
        )

    frame_id = normalize_optional_text(header.get("frame_id"))
    if frame_id != active_frame_id:
        return None, patrol_area_error(
            result_code="INVALID_REQUEST",
            reason_code="FRAME_ID_MISMATCH",
            result_message="순찰 경로 frame_id가 선택 맵 frame과 일치하지 않습니다.",
        )

    raw_poses = path.get("poses")
    if not isinstance(raw_poses, list):
        return None, patrol_area_error(
            result_code="INVALID_REQUEST",
            reason_code="PATROL_PATH_INVALID",
            result_message="path_json.poses가 유효하지 않습니다.",
        )
    if len(raw_poses) < 2:
        return None, patrol_area_error(
            result_code="INVALID_REQUEST",
            reason_code="PATROL_PATH_TOO_SHORT",
            result_message="순찰 경로는 최소 두 개 이상의 waypoint가 필요합니다.",
        )

    poses = []
    for pose in raw_poses:
        if not isinstance(pose, dict):
            return None, patrol_area_error(
                result_code="INVALID_REQUEST",
                reason_code="PATROL_PATH_INVALID",
                result_message="순찰 waypoint shape이 유효하지 않습니다.",
            )
        x = optional_float(pose.get("x"))
        y = optional_float(pose.get("y"))
        yaw = optional_float(pose.get("yaw"))
        if x is None or y is None or yaw is None:
            return None, patrol_area_error(
                result_code="INVALID_REQUEST",
                reason_code="PATROL_PATH_INVALID",
                result_message="순찰 waypoint 좌표가 유효하지 않습니다.",
            )
        poses.append({"x": x, "y": y, "yaw": yaw})

    return {"header": {"frame_id": frame_id}, "poses": poses}, None


__all__ = [
    "ALLOWED_GOAL_POSE_PURPOSES",
    "ALLOWED_OPERATION_ZONE_TYPES",
    "goal_pose_error",
    "normalize_goal_pose_input",
    "normalize_operation_zone_boundary_input",
    "normalize_operation_zone_input",
    "normalize_patrol_area_input",
    "normalize_patrol_area_path_input",
    "operation_zone_error",
    "patrol_area_error",
]
