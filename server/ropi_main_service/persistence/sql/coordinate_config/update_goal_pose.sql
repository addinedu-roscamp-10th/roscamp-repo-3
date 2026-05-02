UPDATE goal_pose
SET
    zone_id = %s,
    purpose = %s,
    pose_x = %s,
    pose_y = %s,
    pose_yaw = %s,
    frame_id = %s,
    is_enabled = %s,
    updated_at = NOW()
WHERE goal_pose_id = %s
  AND map_id = %s
