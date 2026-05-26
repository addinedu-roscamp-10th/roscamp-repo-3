SELECT
    t.task_id,
    t.task_status,
    t.phase,
    t.assigned_robot_id,
    d.drive_status
FROM task t
JOIN drive_task_detail d
    ON d.task_id = t.task_id
WHERE t.task_id = %s
  AND t.task_type = 'DRIVE'
LIMIT 1
