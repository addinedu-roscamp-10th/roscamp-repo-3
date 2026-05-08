UPDATE operation_zone
SET
    boundary_json = %s,
    revision = revision + 1,
    updated_at = NOW()
WHERE map_id = %s
  AND zone_id = %s
