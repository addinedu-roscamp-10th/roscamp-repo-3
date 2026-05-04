INSERT INTO task_event_log (
    task_id,
    event_name,
    severity,
    component,
    robot_id,
    result_code,
    message,
    payload_json,
    occurred_at,
    created_at
)
VALUES (
    %s,
    'GUIDE_TASK_ACCEPTED',
    'INFO',
    'control_service',
    %s,
    'ACCEPTED',
    %s,
    %s,
    NOW(3),
    NOW(3)
)
