UPDATE task
SET task_status = 'RUNNING',
    phase = 'FOLLOW_PATROL_PATH',
    latest_reason_code = NULL,
    result_code = %s,
    result_message = %s,
    updated_at = NOW(3)
WHERE task_id = %s
