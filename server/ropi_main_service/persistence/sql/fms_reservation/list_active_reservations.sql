SELECT
    reservation_id,
    task_id,
    robot_id,
    map_id,
    resource_type,
    resource_id,
    waypoint_id,
    edge_id,
    reservation_status,
    reserved_from,
    reserved_until,
    released_at,
    reason_code,
    created_at,
    updated_at
FROM fms_reservation
WHERE (%s IS NULL OR map_id = %s)
  AND released_at IS NULL
  AND (
      reservation_status = 'WAITING'
      OR (
          reservation_status = 'HELD'
          AND (reserved_until IS NULL OR reserved_until > NOW(3))
      )
  )
ORDER BY map_id ASC, resource_type ASC, resource_id ASC, created_at ASC
