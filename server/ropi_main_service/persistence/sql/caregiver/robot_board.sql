SELECT
    r.robot_id,
    r.robot_type_name,
    r.robot_manager_name,
    CASE
        WHEN rrs.pose_x IS NOT NULL AND rrs.pose_y IS NOT NULL
            THEN CONCAT('좌표 x=', ROUND(rrs.pose_x, 2), ', y=', ROUND(rrs.pose_y, 2))
        ELSE NULL
    END AS current_location,
    COALESCE(rrs.runtime_state, r.robot_status_name) AS robot_status,
    rrs.battery_percent,
    t.map_id AS current_pose_map_id,
    rrs.pose_x,
    rrs.pose_y,
    rrs.pose_yaw,
    rrs.frame_id,
    t.task_id AS current_task_id,
    t.task_type AS current_task_type,
    t.phase AS current_task_phase,
    t.task_status AS current_task_status,
    d.route_id AS drive_route_id,
    fr.route_name AS drive_route_name,
    d.route_revision AS drive_route_revision,
    d.drive_status,
    d.frame_id AS drive_frame_id,
    d.waypoint_count AS drive_waypoint_count,
    d.current_waypoint_index AS drive_current_waypoint_index,
    d.path_snapshot_json AS drive_path_snapshot_json,
    rrs.fault_code,
    rrs.last_seen_at,
    CASE
        WHEN rrs.last_seen_at IS NULL THEN NULL
        ELSE TIMESTAMPDIFF(SECOND, rrs.last_seen_at, NOW(3))
    END AS last_seen_age_sec
FROM robot r
LEFT JOIN robot_runtime_status rrs
  ON r.robot_id = rrs.robot_id
LEFT JOIN task t
  ON rrs.active_task_id = t.task_id
LEFT JOIN drive_task_detail d
  ON d.task_id = t.task_id
 AND t.task_type = 'DRIVE'
LEFT JOIN fms_route fr
  ON fr.route_id = d.route_id
ORDER BY r.robot_id
