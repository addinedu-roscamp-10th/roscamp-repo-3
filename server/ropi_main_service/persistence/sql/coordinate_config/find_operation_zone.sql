SELECT
    zone_id,
    map_id,
    zone_name,
    zone_type,
    revision,
    is_enabled,
    created_at,
    updated_at
FROM operation_zone
WHERE zone_id = %s
LIMIT 1
