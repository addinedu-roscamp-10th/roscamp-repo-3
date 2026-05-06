SELECT
    route_id,
    map_id,
    route_name,
    route_scope,
    revision,
    is_enabled,
    created_at,
    updated_at
FROM fms_route
WHERE route_id = %s
