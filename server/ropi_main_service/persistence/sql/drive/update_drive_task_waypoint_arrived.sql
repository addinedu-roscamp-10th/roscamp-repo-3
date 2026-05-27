UPDATE drive_task_detail
SET drive_status = 'MOVING',
    current_waypoint_index = %s
WHERE task_id = %s
