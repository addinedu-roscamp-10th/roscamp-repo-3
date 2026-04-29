SELECT
    t.task_id,
    t.assigned_robot_id,
    ptd.frame_id,
    ptd.waypoint_count,
    ptd.path_snapshot_json
FROM task t
JOIN patrol_task_detail ptd
    ON ptd.task_id = t.task_id
WHERE t.task_id = %s
  AND t.task_type = 'PATROL'
LIMIT 1
