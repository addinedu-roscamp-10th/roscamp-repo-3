SELECT
    gp.goal_pose_id,
    gp.map_id,
    gp.zone_id,
    oz.zone_name,
    gp.purpose,
    gp.pose_x,
    gp.pose_y,
    gp.pose_yaw,
    gp.frame_id
FROM goal_pose gp
JOIN map_profile mp
    ON mp.map_id = gp.map_id
LEFT JOIN operation_zone oz
    ON oz.map_id = gp.map_id
   AND oz.zone_id = gp.zone_id
WHERE gp.is_enabled = TRUE
  AND gp.map_id = %s
  AND gp.purpose IN ('PICKUP', 'DESTINATION', 'DOCK')
ORDER BY FIELD(gp.purpose, 'PICKUP', 'DESTINATION', 'DOCK'), gp.goal_pose_id
