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
ORDER BY is_active DESC, map_id
