INSERT INTO idempotency_record (
    scope,
    requester_type,
    requester_id,
    idempotency_key,
    request_hash,
    response_json,
    task_id,
    expires_at,
    created_at
)
VALUES (
    %s,
    'CAREGIVER',
    %s,
    %s,
    %s,
    %s,
    %s,
    DATE_ADD(NOW(3), INTERVAL 1 DAY),
    NOW(3)
)
