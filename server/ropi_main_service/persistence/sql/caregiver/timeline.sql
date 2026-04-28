SELECT
    DATE_FORMAT(tel.occurred_at, '%%H:%%i:%%s') AS timeline_time,
    tel.task_event_log_id AS work_id,
    tel.event_name,
    COALESCE(tel.message, tel.reason_code, tel.result_code, '') AS detail
FROM task_event_log tel
ORDER BY tel.occurred_at DESC
LIMIT %s
