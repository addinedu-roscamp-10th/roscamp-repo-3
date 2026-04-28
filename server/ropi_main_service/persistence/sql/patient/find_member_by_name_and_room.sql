SELECT
    member_id,
    member_name,
    room_no,
    admission_date
FROM member
WHERE member_name = %s
  AND room_no = %s
LIMIT 1
