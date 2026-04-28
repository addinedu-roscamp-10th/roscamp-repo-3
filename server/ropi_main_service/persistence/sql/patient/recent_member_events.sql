SELECT
    event_at,
    description,
    event_type_code,
    event_type_name,
    severity
FROM member_event
WHERE member_id = %s
ORDER BY event_at DESC, member_event_id DESC
LIMIT %s
