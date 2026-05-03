SELECT
    r.robot_id,
    r.robot_type_name,
    r.robot_manager_name,
    COALESCE(
        CONCAT('x=', ROUND(rrs.pose_x, 2), ', y=', ROUND(rrs.pose_y, 2)),
        r.ip_address
    ) AS current_location,
    COALESCE(rrs.runtime_state, r.robot_status_name) AS robot_status,
    rrs.battery_percent,
    t.task_id AS current_task_id,
    t.phase AS current_task_phase,
    t.task_status AS current_task_status,
    rrs.fault_code,
    rrs.last_seen_at
FROM robot r
LEFT JOIN robot_runtime_status rrs
  ON r.robot_id = rrs.robot_id
LEFT JOIN task t
  ON rrs.active_task_id = t.task_id
ORDER BY r.robot_id
