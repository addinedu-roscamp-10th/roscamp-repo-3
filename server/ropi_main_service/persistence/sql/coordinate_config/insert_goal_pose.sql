INSERT INTO goal_pose (
    goal_pose_id,
    map_id,
    zone_id,
    purpose,
    pose_x,
    pose_y,
    pose_yaw,
    frame_id,
    is_enabled,
    created_at,
    updated_at
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
