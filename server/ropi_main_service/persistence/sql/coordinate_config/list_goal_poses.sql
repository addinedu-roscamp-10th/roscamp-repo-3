SELECT
    gp.goal_pose_id,
    gp.map_id,
    gp.zone_id,
    oz.zone_name,
    gp.purpose,
    gp.pose_x,
    gp.pose_y,
    gp.pose_yaw,
    gp.frame_id,
    gp.is_enabled,
    gp.created_at,
    gp.updated_at
FROM goal_pose gp
LEFT JOIN operation_zone oz
    ON oz.map_id = gp.map_id
   AND oz.zone_id = gp.zone_id
WHERE gp.map_id = %s
  AND (%s = TRUE OR gp.is_enabled = TRUE)
ORDER BY
    FIELD(gp.purpose, 'PICKUP', 'DESTINATION', 'DOCK'),
    gp.goal_pose_id
