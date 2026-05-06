UPDATE fms_waypoint
SET
    display_name = %s,
    waypoint_type = %s,
    pose_x = %s,
    pose_y = %s,
    pose_yaw = %s,
    frame_id = %s,
    snap_group = %s,
    is_enabled = %s,
    updated_at = NOW()
WHERE waypoint_id = %s
  AND map_id = %s
