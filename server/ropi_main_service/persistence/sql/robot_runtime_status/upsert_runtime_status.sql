INSERT INTO robot_runtime_status (
    robot_id,
    robot_kind,
    runtime_state,
    active_task_id,
    battery_percent,
    pose_x,
    pose_y,
    pose_yaw,
    frame_id,
    fault_code,
    last_seen_at,
    updated_at
)
VALUES (
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    NOW(3),
    NOW(3)
)
ON DUPLICATE KEY UPDATE
    robot_kind = VALUES(robot_kind),
    runtime_state = VALUES(runtime_state),
    active_task_id = VALUES(active_task_id),
    battery_percent = VALUES(battery_percent),
    pose_x = VALUES(pose_x),
    pose_y = VALUES(pose_y),
    pose_yaw = VALUES(pose_yaw),
    frame_id = VALUES(frame_id),
    fault_code = VALUES(fault_code),
    last_seen_at = VALUES(last_seen_at),
    updated_at = VALUES(updated_at)
