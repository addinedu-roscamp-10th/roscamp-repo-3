SELECT
    CAST(caregiver_id AS CHAR) AS user_id,
    password AS user_password,
    caregiver_name AS user_name
FROM caregiver
WHERE caregiver_id = %s
LIMIT 1
