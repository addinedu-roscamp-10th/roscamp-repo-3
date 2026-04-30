INSERT INTO task_event_log (
    task_id,
    event_name,
    severity,
    component,
    robot_id,
    result_code,
    reason_code,
    message,
    payload_json,
    occurred_at,
    created_at
)
VALUES (
    %s,
    'FALL_ALERT_CREATED',
    'CRITICAL',
    'control_service',
    %s,
    %s,
    %s,
    %s,
    %s,
    NOW(3),
    NOW(3)
)
