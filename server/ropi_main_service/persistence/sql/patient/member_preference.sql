SELECT
    preference,
    dislike,
    comment
FROM preference
WHERE member_id = %s
LIMIT 1
