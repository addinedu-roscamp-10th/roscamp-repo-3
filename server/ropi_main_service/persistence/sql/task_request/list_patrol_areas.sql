SELECT
    oz.zone_id AS patrol_area_id,
    oz.zone_name AS patrol_area_name,
    oz.revision AS patrol_area_revision,
    oz.default_robot_id AS assigned_robot_id,
    oz.map_id,
    JSON_LENGTH(oz.path_json, '$.poses') AS waypoint_count,
    JSON_UNQUOTE(JSON_EXTRACT(oz.path_json, '$.header.frame_id')) AS path_frame_id,
    oz.path_json
FROM operation_zone oz
JOIN map_profile mp
    ON mp.map_id = oz.map_id
WHERE oz.is_enabled = TRUE
  AND mp.is_active = TRUE
  AND oz.path_json IS NOT NULL
ORDER BY oz.zone_name, oz.zone_id
