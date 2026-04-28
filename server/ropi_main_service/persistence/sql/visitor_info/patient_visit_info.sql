SELECT
    m.member_name AS name,
    m.room_no AS room,
    MAX(CASE WHEN e.event_type_code = 'MEAL_RECORDED' THEN e.event_name END) AS meal_status,
    MAX(CASE WHEN e.event_type_code = 'MEDICATION_RECORDED' THEN e.event_name END) AS medication_status,
    MAX(CASE WHEN e.event_type_code = 'FALL_DETECTED' THEN e.event_name END) AS fall_risk
FROM member m
LEFT JOIN member_event e
  ON m.member_id = e.member_id
WHERE m.member_name LIKE %s
   OR m.room_no LIKE %s
GROUP BY m.member_id, m.member_name, m.room_no
ORDER BY m.member_name
LIMIT 1
