UPDATE task
SET task_status = 'CANCEL_REQUESTED',
    phase = 'CANCEL_REQUESTED',
    latest_reason_code = %s,
    result_code = %s,
    result_message = %s,
    updated_at = NOW(3)
WHERE task_id = %s
