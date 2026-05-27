SELECT
    reservation_id,
    task_id,
    robot_id,
    map_id,
    resource_type,
    resource_id,
    waypoint_id,
    edge_id,
    conflict_zone_id,
    reservation_status,
    reserved_from,
    reserved_until,
    released_at,
    reason_code,
    created_at,
    updated_at
FROM fms_reservation
WHERE task_id = %s
  AND robot_id = %s
  AND map_id = %s
  AND resource_type = %s
  AND resource_id = %s
  AND released_at IS NULL
  AND reservation_status IN ('HELD', 'WAITING')
  AND (
      reservation_status = 'WAITING'
      OR reserved_until IS NULL
      OR reserved_until > NOW(3)
  )
ORDER BY
    CASE reservation_status
        WHEN 'HELD' THEN 0
        ELSE 1
    END,
    created_at ASC
LIMIT 1
FOR UPDATE
