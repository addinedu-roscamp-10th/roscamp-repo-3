SELECT
    edge_id,
    map_id,
    from_waypoint_id,
    to_waypoint_id,
    is_bidirectional,
    traversal_cost,
    priority,
    is_enabled,
    created_at,
    updated_at
FROM fms_edge
WHERE map_id = %s
  AND (%s OR is_enabled = TRUE)
ORDER BY edge_id ASC
