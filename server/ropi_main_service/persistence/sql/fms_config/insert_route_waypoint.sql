INSERT INTO fms_route_waypoint (
    route_id,
    sequence_no,
    waypoint_id,
    yaw_policy,
    fixed_pose_yaw,
    stop_required,
    dwell_sec,
    created_at,
    updated_at
) VALUES (
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    NOW(),
    NOW()
)
