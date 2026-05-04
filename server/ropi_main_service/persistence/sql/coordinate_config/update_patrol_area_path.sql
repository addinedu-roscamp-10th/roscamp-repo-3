UPDATE patrol_area
SET
    path_json = %s,
    revision = revision + 1,
    updated_at = NOW()
WHERE patrol_area_id = %s
  AND map_id = %s
