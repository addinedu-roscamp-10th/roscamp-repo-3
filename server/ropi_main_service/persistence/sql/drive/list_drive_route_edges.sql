SELECT
    previous.sequence_no AS from_sequence_no,
    edge.edge_id,
    edge.from_waypoint_id,
    edge.to_waypoint_id,
    conflict_zone.conflict_zone_id
FROM task t
JOIN drive_task_detail d
    ON d.task_id = t.task_id
JOIN fms_route_waypoint previous
    ON previous.route_id = d.route_id
JOIN fms_route_waypoint next_waypoint
    ON next_waypoint.route_id = d.route_id
    AND next_waypoint.sequence_no = previous.sequence_no + 1
JOIN fms_edge edge
    ON edge.map_id = t.map_id
    AND (
        (
            edge.from_waypoint_id = previous.waypoint_id
            AND edge.to_waypoint_id = next_waypoint.waypoint_id
        )
        OR (
            edge.is_bidirectional = TRUE
            AND edge.from_waypoint_id = next_waypoint.waypoint_id
            AND edge.to_waypoint_id = previous.waypoint_id
        )
    )
LEFT JOIN fms_edge_conflict_zone edge_conflict_zone
    ON edge_conflict_zone.edge_id = edge.edge_id
    AND edge_conflict_zone.map_id = edge.map_id
LEFT JOIN fms_conflict_zone conflict_zone
    ON conflict_zone.conflict_zone_id = edge_conflict_zone.conflict_zone_id
    AND conflict_zone.map_id = edge.map_id
    AND conflict_zone.is_enabled = TRUE
WHERE t.task_id = %s
  AND t.task_type = 'DRIVE'
ORDER BY previous.sequence_no ASC, edge.edge_id ASC, conflict_zone.conflict_zone_id ASC
