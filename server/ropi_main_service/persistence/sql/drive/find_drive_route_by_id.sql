SELECT
    r.route_id,
    r.map_id,
    r.route_name,
    r.route_scope,
    r.revision,
    r.is_enabled,
    rw.sequence_no,
    rw.waypoint_id,
    rw.yaw_policy,
    rw.fixed_pose_yaw,
    rw.stop_required,
    rw.dwell_sec,
    w.pose_x,
    w.pose_y,
    w.pose_yaw,
    w.frame_id
FROM fms_route r
JOIN fms_route_waypoint rw ON rw.route_id = r.route_id
JOIN fms_waypoint w ON w.waypoint_id = rw.waypoint_id
WHERE r.route_id = %s
  AND r.map_id = %s
ORDER BY rw.sequence_no ASC
