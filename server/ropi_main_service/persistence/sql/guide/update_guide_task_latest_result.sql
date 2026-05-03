UPDATE task
SET latest_reason_code = %s,
    result_code = %s,
    result_message = %s,
    updated_at = NOW(3)
WHERE task_id = %s
