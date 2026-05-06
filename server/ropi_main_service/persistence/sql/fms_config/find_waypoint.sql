SELECT
    waypoint_id,
    map_id,
    display_name,
    waypoint_type,
    pose_x,
    pose_y,
    pose_yaw,
    frame_id,
    snap_group,
    is_enabled,
    created_at,
    updated_at
FROM fms_waypoint
WHERE waypoint_id = %s
