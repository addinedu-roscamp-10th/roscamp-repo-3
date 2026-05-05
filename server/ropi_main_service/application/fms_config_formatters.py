from server.ropi_main_service.application.coordinate_config_formatters import (
    format_map_profile,
)
from server.ropi_main_service.application.formatting import (
    bool_value,
    generated_at,
    isoformat,
    normalize_optional_text,
    optional_float,
)


def format_fms_waypoint(row):
    return {
        "waypoint_id": row.get("waypoint_id"),
        "map_id": row.get("map_id"),
        "display_name": row.get("display_name"),
        "waypoint_type": row.get("waypoint_type"),
        "pose_x": optional_float(row.get("pose_x")) or 0.0,
        "pose_y": optional_float(row.get("pose_y")) or 0.0,
        "pose_yaw": optional_float(row.get("pose_yaw")) or 0.0,
        "frame_id": row.get("frame_id") or "map",
        "snap_group": normalize_optional_text(row.get("snap_group")),
        "is_enabled": bool_value(row.get("is_enabled")),
        "created_at": isoformat(row.get("created_at")),
        "updated_at": isoformat(row.get("updated_at")),
    }


__all__ = [
    "bool_value",
    "format_fms_waypoint",
    "format_map_profile",
    "generated_at",
]
