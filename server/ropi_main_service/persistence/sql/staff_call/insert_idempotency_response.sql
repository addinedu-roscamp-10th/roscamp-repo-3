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
) VALUES (
    %s,
    'KIOSK',
    %s,
    %s,
    %s,
    %s,
    NULL,
    DATE_ADD(NOW(3), INTERVAL 1 DAY),
    NOW(3)
)
