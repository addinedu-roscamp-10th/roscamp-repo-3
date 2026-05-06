UPDATE fms_edge
SET
    from_waypoint_id = %s,
    to_waypoint_id = %s,
    is_bidirectional = %s,
    traversal_cost = %s,
    priority = %s,
    is_enabled = %s,
    updated_at = NOW()
WHERE edge_id = %s
  AND map_id = %s
