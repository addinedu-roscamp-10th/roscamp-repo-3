UPDATE patrol_task_detail
SET patrol_status = %s,
    current_waypoint_index = %s
WHERE task_id = %s
