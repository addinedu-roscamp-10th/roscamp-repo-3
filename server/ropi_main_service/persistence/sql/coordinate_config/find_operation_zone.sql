SELECT
    zone_id,
    map_id,
    zone_name,
    zone_type,
    revision,
    boundary_json,
    is_enabled,
    created_at,
    updated_at
FROM operation_zone
WHERE map_id = %s
  AND zone_id = %s
LIMIT 1
