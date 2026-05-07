UPDATE operation_zone
SET
    zone_name = %s,
    zone_type = %s,
    is_enabled = %s,
    revision = revision + 1,
    updated_at = NOW()
WHERE map_id = %s
  AND zone_id = %s
