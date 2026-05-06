from server.ropi_main_service.application.coordinate_config_formatters import (
    format_map_profile,
)
from server.ropi_main_service.application.formatting import (
    bool_value,
    generated_at,
    isoformat,
    normalize_optional_text,
    optional_float,
    optional_int,
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


def format_fms_edge(row):
    return {
        "edge_id": row.get("edge_id"),
        "map_id": row.get("map_id"),
        "from_waypoint_id": row.get("from_waypoint_id"),
        "to_waypoint_id": row.get("to_waypoint_id"),
        "is_bidirectional": bool_value(row.get("is_bidirectional")),
        "traversal_cost": optional_float(row.get("traversal_cost")),
        "priority": optional_int(row.get("priority")),
        "is_enabled": bool_value(row.get("is_enabled")),
        "created_at": isoformat(row.get("created_at")),
        "updated_at": isoformat(row.get("updated_at")),
    }


def format_fms_route(row):
    row = row if isinstance(row, dict) else {}
    return {
        "route_id": row.get("route_id"),
        "map_id": row.get("map_id"),
        "route_name": row.get("route_name"),
        "route_scope": row.get("route_scope"),
        "revision": optional_int(row.get("revision")) or 0,
        "waypoint_sequence": [
            format_fms_route_waypoint(waypoint)
            for waypoint in row.get("waypoint_sequence") or []
            if isinstance(waypoint, dict)
        ],
        "is_enabled": bool_value(row.get("is_enabled")),
        "created_at": isoformat(row.get("created_at")),
        "updated_at": isoformat(row.get("updated_at")),
    }


def format_fms_route_waypoint(row):
    row = row if isinstance(row, dict) else {}
    return {
        "sequence_no": optional_int(row.get("sequence_no")) or 0,
        "waypoint_id": row.get("waypoint_id"),
        "yaw_policy": row.get("yaw_policy") or "AUTO_NEXT",
        "fixed_pose_yaw": optional_float(row.get("fixed_pose_yaw")),
        "stop_required": bool_value(row.get("stop_required", True)),
        "dwell_sec": optional_float(row.get("dwell_sec")),
    }


__all__ = [
    "bool_value",
    "format_fms_edge",
    "format_fms_route",
    "format_fms_route_waypoint",
    "format_fms_waypoint",
    "format_map_profile",
    "generated_at",
]
