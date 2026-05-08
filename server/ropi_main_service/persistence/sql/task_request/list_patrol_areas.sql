SELECT
    pa.patrol_area_id,
    pa.patrol_area_name,
    pa.revision AS patrol_area_revision,
    pa.map_id,
    JSON_LENGTH(pa.path_json, '$.poses') AS waypoint_count,
    JSON_UNQUOTE(JSON_EXTRACT(pa.path_json, '$.header.frame_id')) AS path_frame_id,
    pa.path_json
FROM patrol_area pa
JOIN map_profile mp
    ON mp.map_id = pa.map_id
WHERE pa.is_enabled = TRUE
  AND pa.map_id = %s
ORDER BY pa.patrol_area_name, pa.patrol_area_id
