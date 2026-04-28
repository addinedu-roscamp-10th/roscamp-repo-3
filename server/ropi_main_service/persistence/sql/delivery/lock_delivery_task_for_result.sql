SELECT
    task_id,
    task_status,
    phase,
    assigned_robot_id
FROM task
WHERE task_id = %s
  AND task_type = 'DELIVERY'
FOR UPDATE
