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
WHERE map_id = %s
  AND resource_type = %s
  AND resource_id = %s
  AND reservation_status = 'HELD'
  AND released_at IS NULL
  AND (reserved_until IS NULL OR reserved_until > NOW(3))
ORDER BY created_at ASC
LIMIT 1
FOR UPDATE
