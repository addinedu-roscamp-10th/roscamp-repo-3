SELECT
    tel.task_event_log_id AS event_id,
    tel.occurred_at,
    tel.severity,
    tel.component AS source_component,
    tel.task_id,
    tel.robot_id,
    tel.event_name AS event_type,
    tel.result_code,
    tel.reason_code,
    tel.message,
    tel.payload_json
FROM task_event_log tel
WHERE (%s IS NULL OR tel.occurred_at >= %s)
  AND (%s IS NULL OR tel.severity = %s)
  AND (%s IS NULL OR tel.component LIKE CONCAT('%%', %s, '%%'))
  AND (%s IS NULL OR tel.task_id = %s)
  AND (%s IS NULL OR tel.robot_id LIKE CONCAT('%%', %s, '%%'))
  AND (%s IS NULL OR tel.event_name LIKE CONCAT('%%', %s, '%%'))
ORDER BY tel.occurred_at DESC, tel.task_event_log_id DESC
LIMIT %s
