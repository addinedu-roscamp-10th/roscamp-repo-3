INSERT INTO task_event_log (
    task_id,
    event_name,
    severity,
    component,
    result_code,
    message,
    occurred_at,
    created_at
)
VALUES (
    %s,
    'PATROL_TASK_ACCEPTED',
    'INFO',
    'control_service',
    'ACCEPTED',
    %s,
    NOW(3),
    NOW(3)
)
