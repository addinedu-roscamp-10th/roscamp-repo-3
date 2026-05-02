UPDATE operation_zone
SET
    zone_name = %s,
    zone_type = %s,
    is_enabled = %s,
    revision = revision + 1,
    updated_at = NOW()
WHERE zone_id = %s
  AND map_id = %s
