SELECT
    gp.goal_pose_id AS destination_id,
    COALESCE(oz.zone_name, gp.goal_pose_id) AS destination_name,
    gp.zone_id,
    gp.map_id,
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
  AND gp.purpose = 'DESTINATION'
ORDER BY destination_name, destination_id
