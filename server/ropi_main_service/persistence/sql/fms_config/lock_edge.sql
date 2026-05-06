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
WHERE edge_id = %s
FOR UPDATE
