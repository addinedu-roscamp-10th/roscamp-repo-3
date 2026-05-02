SELECT
    goal_pose_id,
    map_id,
    zone_id,
    purpose,
    pose_x,
    pose_y,
    pose_yaw,
    frame_id,
    is_enabled,
    created_at,
    updated_at
FROM goal_pose
WHERE goal_pose_id = %s
  AND map_id = %s
FOR UPDATE
