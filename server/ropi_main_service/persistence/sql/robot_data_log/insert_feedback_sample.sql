INSERT INTO robot_data_log (
    robot_id,
    task_id,
    data_type,
    pose_x,
    pose_y,
    pose_yaw,
    battery_percent,
    payload_json,
    sampled_at,
    received_at,
    created_at
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
    NULL,
    NOW(3),
    NOW(3)
)
