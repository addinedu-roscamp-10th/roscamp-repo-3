SELECT
    route_id,
    sequence_no,
    waypoint_id,
    yaw_policy,
    fixed_pose_yaw,
    stop_required,
    dwell_sec,
    created_at,
    updated_at
FROM fms_route_waypoint
WHERE route_id = %s
ORDER BY sequence_no ASC
