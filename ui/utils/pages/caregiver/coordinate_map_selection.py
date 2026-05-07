def normalize_map_profile_rows(map_profiles):
    return [
        row
        for row in map_profiles or []
        if isinstance(row, dict) and map_profile_id(row)
    ]


def map_profile_id(map_profile):
    map_profile = map_profile if isinstance(map_profile, dict) else {}
    return str(map_profile.get("map_id") or "").strip() or None


def map_selector_item_text(map_profile):
    map_id = map_profile_id(map_profile)
    map_name = str(map_profile.get("map_name") or map_id).strip() if map_id else ""
    active_mark = " *" if map_profile.get("is_active") else ""
    return f"{map_name or map_id} ({map_id}){active_mark}"


def empty_coordinate_config_source(*, map_id, map_profiles):
    return {
        "map_profile": {"map_id": str(map_id or "").strip()} if map_id else {},
        "map_profiles": normalize_map_profile_rows(map_profiles),
        "operation_zones": [],
        "goal_poses": [],
        "patrol_areas": [],
        "fms_waypoints": [],
        "fms_edges": [],
        "fms_routes": [],
    }


__all__ = [
    "empty_coordinate_config_source",
    "map_profile_id",
    "map_selector_item_text",
    "normalize_map_profile_rows",
]
