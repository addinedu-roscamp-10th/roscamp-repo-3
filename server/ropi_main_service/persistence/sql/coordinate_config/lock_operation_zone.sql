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
WHERE zone_id = %s
  AND map_id = %s
FOR UPDATE
