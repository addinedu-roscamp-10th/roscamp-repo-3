SELECT
    v.visitor_id,
    v.visitor_name,
    v.relation_name,
    v.member_id,
    m.member_name,
    m.room_no
FROM visitor v
JOIN member m
  ON m.member_id = v.member_id
WHERE v.visitor_id = %s
LIMIT 1
