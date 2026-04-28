SELECT
    tel.task_event_log_id AS event_id,
    t.task_status AS event_type,
    COALESCE(tel.message, tel.event_name) AS description,
    tel.occurred_at AS event_datetime,
    COALESCE(tel.robot_id, t.assigned_robot_id) AS robot_id
FROM task_event_log tel
LEFT JOIN task t
  ON tel.task_id = t.task_id
ORDER BY tel.occurred_at DESC
LIMIT %s
