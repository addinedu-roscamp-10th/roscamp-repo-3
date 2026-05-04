SELECT
    task_id,
    task_type,
    task_status,
    phase,
    assigned_robot_id
FROM task
WHERE task_id = %s
LIMIT 1
