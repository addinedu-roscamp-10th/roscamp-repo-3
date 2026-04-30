SELECT
    t.task_id,
    t.task_type,
    t.task_status,
    t.phase,
    t.assigned_robot_id,
    ptd.patrol_status
FROM task t
LEFT JOIN patrol_task_detail ptd
    ON ptd.task_id = t.task_id
WHERE t.task_id = %s
FOR UPDATE
