SELECT
    member_id,
    member_name,
    room_no
FROM member
WHERE member_name LIKE %s
   OR room_no LIKE %s
ORDER BY member_name
LIMIT %s
