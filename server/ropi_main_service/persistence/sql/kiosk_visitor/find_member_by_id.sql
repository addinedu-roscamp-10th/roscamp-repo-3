SELECT
    member_id,
    member_name,
    room_no
FROM member
WHERE member_id = %s
LIMIT 1
