SELECT
    visitor_id AS user_id,
    password AS user_password,
    visitor_name AS user_name
FROM visitor
WHERE visitor_id = %s
LIMIT 1
