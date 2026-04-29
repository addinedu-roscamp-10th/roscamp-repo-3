SELECT
    t.task_id,
    t.task_status,
    t.phase,
    t.assigned_robot_id,
    ptd.patrol_status
FROM task t
JOIN patrol_task_detail ptd
    ON ptd.task_id = t.task_id
WHERE t.assigned_robot_id = %s
  AND t.task_type = 'PATROL'
  AND t.task_status = 'RUNNING'
  AND t.phase IN ('FOLLOW_PATROL_PATH', 'WAIT_FALL_RESPONSE')
ORDER BY t.updated_at DESC, t.task_id DESC
LIMIT 1
