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
    current_task.map_id AS current_pose_map_id,
    rrs.pose_x,
    rrs.pose_y,
    rrs.pose_yaw,
    rrs.frame_id,
    current_task.task_id AS current_task_id,
    current_task.task_type AS current_task_type,
    current_task.phase AS current_task_phase,
    current_task.task_status AS current_task_status,
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
LEFT JOIN task runtime_task
  ON rrs.active_task_id = runtime_task.task_id
LEFT JOIN task assigned_drive_task
  ON assigned_drive_task.task_id = (
      SELECT active_drive.task_id
      FROM task active_drive
      WHERE active_drive.assigned_robot_id = r.robot_id
        AND active_drive.task_type = 'DRIVE'
        AND active_drive.task_status IN (
            'WAITING',
            'WAITING_DISPATCH',
            'READY',
            'ASSIGNED',
            'RUNNING',
            'CANCEL_REQUESTED',
            'CANCELLING',
            'PREEMPTING'
        )
      ORDER BY
        CASE active_drive.task_status
            WHEN 'RUNNING' THEN 0
            WHEN 'WAITING_DISPATCH' THEN 1
            WHEN 'ASSIGNED' THEN 2
            WHEN 'READY' THEN 3
            WHEN 'WAITING' THEN 4
            WHEN 'CANCEL_REQUESTED' THEN 5
            WHEN 'CANCELLING' THEN 6
            WHEN 'PREEMPTING' THEN 7
            ELSE 8
        END,
        active_drive.updated_at DESC,
        active_drive.task_id DESC
      LIMIT 1
  )
LEFT JOIN task current_task
  ON current_task.task_id = COALESCE(
      CASE
        WHEN runtime_task.task_status IN (
            'WAITING',
            'WAITING_DISPATCH',
            'READY',
            'ASSIGNED',
            'RUNNING',
            'CANCEL_REQUESTED',
            'CANCELLING',
            'PREEMPTING'
        )
        AND runtime_task.task_type = 'DRIVE'
        THEN runtime_task.task_id
        ELSE NULL
      END,
      assigned_drive_task.task_id,
      runtime_task.task_id
  )
LEFT JOIN drive_task_detail d
  ON d.task_id = COALESCE(
      CASE
        WHEN current_task.task_type = 'DRIVE'
        THEN current_task.task_id
        ELSE NULL
      END,
      assigned_drive_task.task_id
  )
LEFT JOIN fms_route fr
  ON fr.route_id = d.route_id
ORDER BY r.robot_id
