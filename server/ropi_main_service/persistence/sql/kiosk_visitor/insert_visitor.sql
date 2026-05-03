INSERT INTO visitor (
    password,
    phone_no,
    visitor_name,
    address,
    relation_name,
    member_id,
    created_at,
    updated_at
)
VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
