SELECT
    map_id,
    map_name,
    map_revision,
    git_ref,
    yaml_path,
    pgm_path,
    frame_id,
    is_active,
    created_at,
    updated_at
FROM map_profile
WHERE is_active = TRUE
ORDER BY updated_at DESC, map_id
LIMIT 1
