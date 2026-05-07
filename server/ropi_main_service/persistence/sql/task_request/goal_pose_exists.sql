SELECT 1
FROM goal_pose
WHERE goal_pose_id = %s
  AND map_id = %s
LIMIT 1
