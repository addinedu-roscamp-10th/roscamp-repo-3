SELECT
    patrol_area_id,
    map_id,
    patrol_area_name,
    revision,
    path_json,
    is_enabled,
    created_at,
    updated_at
FROM patrol_area
WHERE patrol_area_id = %s
  AND map_id = %s
FOR UPDATE
