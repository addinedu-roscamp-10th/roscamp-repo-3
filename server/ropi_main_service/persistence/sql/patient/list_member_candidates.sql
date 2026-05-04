SELECT
    member_id,
    member_name,
    room_no,
    admission_date
FROM member
WHERE (%s = '' OR member_name LIKE CONCAT('%%', %s, '%%'))
  AND (%s = '' OR room_no LIKE CONCAT('%%', %s, '%%'))
ORDER BY member_name ASC, room_no ASC, member_id ASC
LIMIT %s
