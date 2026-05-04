SELECT
    goal_pose_id,
    map_id
FROM goal_pose
WHERE zone_id = %s
  AND is_enabled = TRUE
  AND purpose IN ('GUIDE_DESTINATION', 'DESTINATION')
ORDER BY FIELD(purpose, 'GUIDE_DESTINATION', 'DESTINATION'), goal_pose_id
LIMIT 1
