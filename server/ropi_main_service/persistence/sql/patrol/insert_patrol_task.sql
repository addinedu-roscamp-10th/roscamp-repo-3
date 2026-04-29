INSERT INTO task (
    task_type,
    request_id,
    idempotency_key,
    requester_type,
    requester_id,
    priority,
    task_status,
    phase,
    assigned_robot_id,
    map_id,
    created_at,
    updated_at
)
VALUES (
    'PATROL',
    %s,
    %s,
    'CAREGIVER',
    %s,
    %s,
    'WAITING_DISPATCH',
    'REQUESTED',
    %s,
    %s,
    NOW(3),
    NOW(3)
)
