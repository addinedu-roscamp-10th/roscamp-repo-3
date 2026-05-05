SELECT
    rw.route_id,
    rw.sequence_no,
    rw.waypoint_id,
    rw.yaw_policy,
    rw.fixed_pose_yaw,
    rw.stop_required,
    rw.dwell_sec,
    rw.created_at,
    rw.updated_at
FROM fms_route_waypoint rw
JOIN fms_route r ON r.route_id = rw.route_id
WHERE r.map_id = %s
  AND (%s OR r.is_enabled = TRUE)
ORDER BY rw.route_id ASC, rw.sequence_no ASC
