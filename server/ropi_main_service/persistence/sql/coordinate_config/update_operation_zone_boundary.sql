UPDATE operation_zone
SET
    boundary_json = %s,
    revision = revision + 1,
    updated_at = NOW()
WHERE zone_id = %s
  AND map_id = %s
