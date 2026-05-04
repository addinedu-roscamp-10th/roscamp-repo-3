INSERT INTO kiosk_staff_call_log (
    idempotency_key,
    request_hash,
    call_type,
    description,
    visitor_id,
    member_id,
    kiosk_id,
    created_at
) VALUES (
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    NOW(3)
)
