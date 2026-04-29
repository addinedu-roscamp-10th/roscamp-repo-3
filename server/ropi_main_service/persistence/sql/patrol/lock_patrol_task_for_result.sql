SELECT
    t.task_id,
    t.task_status,
    t.phase,
    t.assigned_robot_id,
    ptd.patrol_status,
    ptd.waypoint_count,
    ptd.current_waypoint_index
FROM task t
JOIN patrol_task_detail ptd
    ON ptd.task_id = t.task_id
WHERE t.task_id = %s
  AND t.task_type = 'PATROL'
FOR UPDATE
