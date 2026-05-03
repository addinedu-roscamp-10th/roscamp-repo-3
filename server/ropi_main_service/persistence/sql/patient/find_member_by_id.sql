SELECT
    member_id,
    member_name,
    room_no,
    admission_date
FROM member
WHERE member_id = %s
LIMIT 1
