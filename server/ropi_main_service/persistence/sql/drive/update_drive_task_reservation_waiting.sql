UPDATE task
SET task_status = 'WAITING_DISPATCH',
    phase = 'WAITING_FMS_RESERVATION',
    latest_reason_code = %s,
    result_code = 'WAITING',
    result_message = %s,
    updated_at = NOW(3)
WHERE task_id = %s
