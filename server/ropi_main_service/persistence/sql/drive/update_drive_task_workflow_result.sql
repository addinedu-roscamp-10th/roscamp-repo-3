UPDATE task
SET task_status = %s,
    phase = %s,
    latest_reason_code = %s,
    result_code = %s,
    result_message = %s,
    started_at = COALESCE(started_at, created_at),
    finished_at = COALESCE(finished_at, NOW(3)),
    updated_at = NOW(3)
WHERE task_id = %s
