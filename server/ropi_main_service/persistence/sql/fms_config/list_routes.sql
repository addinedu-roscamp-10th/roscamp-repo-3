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
WHERE map_id = %s
  AND (%s OR is_enabled = TRUE)
ORDER BY route_scope ASC, route_name ASC, route_id ASC
