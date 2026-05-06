INSERT INTO fms_route (
    route_id,
    map_id,
    route_name,
    route_scope,
    revision,
    is_enabled,
    created_at,
    updated_at
) VALUES (
    %s,
    %s,
    %s,
    %s,
    1,
    %s,
    NOW(),
    NOW()
)
