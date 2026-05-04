SELECT
    visitor_id,
    visitor_name,
    phone_no,
    relation_name,
    member_id
FROM visitor
WHERE phone_no = %s
  AND member_id = %s
  AND visitor_name = %s
  AND relation_name = %s
ORDER BY visitor_id DESC
LIMIT 1
