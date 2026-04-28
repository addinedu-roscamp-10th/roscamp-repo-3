UPDATE task
SET task_status = 'CANCELLED',
    phase = 'CANCELLED',
    latest_reason_code = %s,
    result_code = %s,
    result_message = %s,
    finished_at = COALESCE(finished_at, NOW(3)),
    updated_at = NOW(3)
WHERE task_id = %s
