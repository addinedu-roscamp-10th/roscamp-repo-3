UPDATE fms_route
SET
    route_name = %s,
    route_scope = %s,
    is_enabled = %s,
    revision = revision + 1,
    updated_at = NOW()
WHERE route_id = %s
  AND map_id = %s
