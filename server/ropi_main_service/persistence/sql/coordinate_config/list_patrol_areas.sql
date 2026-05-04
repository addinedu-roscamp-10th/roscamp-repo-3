SELECT
    patrol_area_id,
    map_id,
    patrol_area_name,
    revision,
    path_json,
    JSON_LENGTH(path_json, '$.poses') AS waypoint_count,
    JSON_UNQUOTE(JSON_EXTRACT(path_json, '$.header.frame_id')) AS path_frame_id,
    is_enabled,
    created_at,
    updated_at
FROM patrol_area
WHERE map_id = %s
  AND (%s = TRUE OR is_enabled = TRUE)
ORDER BY patrol_area_name, patrol_area_id
