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
WHERE reservation_id = %s
