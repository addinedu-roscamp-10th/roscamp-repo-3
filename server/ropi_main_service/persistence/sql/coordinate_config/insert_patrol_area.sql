INSERT INTO patrol_area (
    patrol_area_id,
    map_id,
    patrol_area_name,
    path_json,
    is_enabled,
    created_at,
    updated_at
) VALUES (
    %s,
    %s,
    %s,
    %s,
    %s,
    NOW(),
    NOW()
)
