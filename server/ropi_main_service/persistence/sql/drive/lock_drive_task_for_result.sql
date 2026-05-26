SELECT
    t.task_id,
    t.task_status,
    t.phase,
    t.assigned_robot_id,
    d.drive_status,
    d.waypoint_count,
    d.current_waypoint_index
FROM task t
JOIN drive_task_detail d
    ON d.task_id = t.task_id
WHERE t.task_id = %s
  AND t.task_type = 'DRIVE'
FOR UPDATE
