UPDATE patrol_area
SET
    patrol_area_name = %s,
    path_json = %s,
    is_enabled = %s,
    revision = revision + 1,
    updated_at = NOW()
WHERE patrol_area_id = %s
  AND map_id = %s
