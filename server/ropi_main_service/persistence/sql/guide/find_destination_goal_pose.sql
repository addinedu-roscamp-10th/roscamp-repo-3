SELECT
    gp.goal_pose_id,
    gp.map_id,
    gp.zone_id,
    oz.zone_name,
    gp.purpose
FROM goal_pose gp
LEFT JOIN operation_zone oz
  ON oz.zone_id = gp.zone_id
WHERE gp.zone_id = %s
  AND gp.is_enabled = TRUE
  AND gp.purpose IN ('GUIDE_DESTINATION', 'DESTINATION')
ORDER BY FIELD(gp.purpose, 'GUIDE_DESTINATION', 'DESTINATION'), gp.goal_pose_id
LIMIT 1
