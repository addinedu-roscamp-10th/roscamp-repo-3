SELECT
    t.task_id,
    t.task_status,
    t.phase,
    t.assigned_robot_id,
    t.map_id,
    d.route_id,
    d.route_revision,
    d.drive_status,
    d.frame_id,
    d.waypoint_count,
    d.current_waypoint_index,
    d.path_snapshot_json
FROM task t
JOIN drive_task_detail d
    ON d.task_id = t.task_id
WHERE t.task_id = %s
  AND t.task_type = 'DRIVE'
