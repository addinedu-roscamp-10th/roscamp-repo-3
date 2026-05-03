SELECT
    event_at,
    event_category,
    event_type_code,
    event_name,
    description,
    severity
FROM member_event
WHERE member_id = %s
  AND event_type_code IN ('MEAL_RECORDED', 'MEDICATION_RECORDED', 'FALL_DETECTED')
ORDER BY event_at DESC, member_event_id DESC
LIMIT %s
