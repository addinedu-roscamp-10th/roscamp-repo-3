SELECT
    patrol_area_id,
    patrol_area_name,
    revision,
    map_id,
    path_json,
    is_enabled
FROM patrol_area
WHERE patrol_area_id = %s
LIMIT 1
