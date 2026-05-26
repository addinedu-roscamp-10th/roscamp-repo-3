UPDATE drive_task_detail
SET drive_status = %s,
    current_waypoint_index = %s
WHERE task_id = %s
