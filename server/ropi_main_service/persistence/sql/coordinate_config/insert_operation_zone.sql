INSERT INTO operation_zone (
    zone_id,
    map_id,
    zone_name,
    zone_type,
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
