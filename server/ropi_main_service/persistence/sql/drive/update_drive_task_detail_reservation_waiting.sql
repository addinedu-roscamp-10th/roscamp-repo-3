UPDATE drive_task_detail
SET drive_status = 'WAITING_FMS_RESERVATION'
WHERE task_id = %s
