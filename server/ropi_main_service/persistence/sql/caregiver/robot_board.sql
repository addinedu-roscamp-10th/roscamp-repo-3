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
    t.phase AS current_task_phase,
    t.task_status AS current_task_status,
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
ORDER BY r.robot_id
