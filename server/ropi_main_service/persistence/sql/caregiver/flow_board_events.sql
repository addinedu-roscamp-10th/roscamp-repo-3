SELECT
    tel.task_event_log_id AS event_id,
    t.task_id,
    t.task_type,
    t.task_status,
    t.phase,
    COALESCE(tel.message, tel.event_name, t.result_message, t.task_type) AS description,
    COALESCE(tel.occurred_at, t.updated_at, t.created_at) AS event_datetime,
    COALESCE(tel.robot_id, t.assigned_robot_id) AS robot_id
FROM task t
LEFT JOIN task_event_log tel
  ON tel.task_event_log_id = (
      SELECT latest_tel.task_event_log_id
      FROM task_event_log latest_tel
      WHERE latest_tel.task_id = t.task_id
      ORDER BY latest_tel.occurred_at DESC, latest_tel.task_event_log_id DESC
      LIMIT 1
  )
ORDER BY t.updated_at DESC, t.task_id DESC
LIMIT %s
