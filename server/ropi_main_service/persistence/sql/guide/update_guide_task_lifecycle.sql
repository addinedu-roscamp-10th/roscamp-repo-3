UPDATE task
SET task_status = %s,
    phase = %s,
    latest_reason_code = %s,
    result_code = %s,
    result_message = %s,
    started_at = CASE
        WHEN %s THEN COALESCE(started_at, NOW(3))
        ELSE started_at
    END,
    finished_at = CASE
        WHEN %s THEN NOW(3)
        ELSE finished_at
    END,
    updated_at = NOW(3)
WHERE task_id = %s
