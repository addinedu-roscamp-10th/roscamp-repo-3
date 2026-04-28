INSERT INTO member_event (
    member_id,
    event_type_code,
    event_type_name,
    event_category,
    severity,
    event_name,
    description,
    event_at,
    created_at,
    updated_at
)
VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), NOW())
